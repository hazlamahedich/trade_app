# MT5 Bridge Integration Plan — DWX Connect

> **Status**: Planned  
> **Created**: 2026-04-29  
> **Scope**: Separate from main PRD — optional module activated by config  
> **Bridge**: [DWX Connect](https://github.com/darwinex/dwxconnect) (file-based, BSD-3, zero pip deps)  
> **Platform**: macOS native MT5 app + Python

---

## 1. Executive Summary

Integrate **DWX Connect** into `trade_advisor` as a new `execution/` module, supporting:

- **Market data ingestion** — MT5 as an alternative data source (forex, CFDs)
- **Paper trading** — forward-test strategies on demo accounts
- **Live execution** — automated order execution from trade_advisor signals

The bridge uses the existing `ExecutionRouter` Protocol (backtest/execution.py:73) — the same code path for backtest and live, as the architecture was explicitly designed for (architecture.md line 1526).

---

## 2. Why DWX Connect

| Criteria | DWX Connect | mt5linux (RPyC) | Official MetaTrader5 pip |
|---|---|---|---|
| **macOS support** | Yes (native MT5 app) | Requires Wine/Docker | Windows only |
| **Extra pip deps** | Zero | RPyC + Wine stack | Windows only |
| **MT5 + MT4** | Both | MT5 only | MT5 only |
| **Broker lock-in** | None (any MT5 broker) | None | None |
| **Communication** | File I/O (simple) | RPyC (network) | Shared memory |
| **Latency** | ~5ms polling | ~1-2ms RPyC | ~0ms (native) |
| **Setup complexity** | Low (EA + config path) | Medium (Wine/Docker) | N/A on Mac |
| **License** | BSD-3 | MIT | MIT |
| **Maintenance** | Active (221 stars) | Active (176 stars) | Active (MetaQuotes) |

DWX Connect is the simplest option for macOS: install the native MT5 app, drop in the EA, point trade_advisor at the files directory. No Wine, no Docker, no extra dependencies.

---

## 3. Architecture Alignment

### Existing Pieces That Connect Directly

| Existing Piece | Location | How It Connects |
|---|---|---|
| `ExecutionRouter` Protocol | `backtest/execution.py:73` | DWX router implements this Protocol |
| `OrderSpec` / `FillResult` | `backtest/execution.py` | Map directly to DWX `open_order()` |
| `CostEngine` | `backtest/costs.py` | Reused for live cost estimation |
| `SignalModel` / `SignalBatch` | `strategies/schemas.py` | Signals → MT5 orders |
| Position sizing | `strategies/sizing.py` | Already uses Decimal, portable |
| `DataRepository` + DuckDB | `data/storage.py` | MT5 tick/bar data stored here |
| `AppConfig` (Pydantic) | `core/config.py` | New `MT5Config` section |
| CLI (`ta` command) | `cli.py` | New `ta trade` commands |
| SSE events | `web/events.py` | New `ta:trade:*` events |
| `DataProvider` Protocol | `data/providers/base.py` | MT5 provider implements this |
| `RiskConfig` | `core/config.py` | Pre-trade risk gates read from this |

### Architecture Quote

> "OrderSpec type + ExecutionRouter Protocol — same code path for backtest and live"  
> — architecture.md line 1526

---

## 4. New Module Structure

```
src/trade_advisor/
├── execution/                          # NEW MODULE
│   ├── __init__.py                     # Public API: MT5Bridge, MT5ExecutionRouter
│   ├── mt5_bridge.py                   # DWX Connect client wrapper
│   ├── mt5_router.py                   # ExecutionRouter impl → MT5 orders
│   ├── mt5_data_source.py             # DataProvider impl → MT5 market data
│   ├── mt5_config.py                  # MT5Config pydantic model
│   ├── order_translator.py            # Signal → OrderSpec → DWX order dict
│   ├── position_manager.py            # Track open positions, reconcile with MT5
│   ├── risk_gates.py                  # Pre-trade risk checks
│   └── _dwx/                          # Vendored DWX Connect client (BSD-3)
│       ├── __init__.py
│       └── dwx_client.py              # DWX Connect Python client
│
├── data/providers/
│   ├── ...existing...
│   └── mt5.py                          # NEW: MT5Provider(DataProvider)
│
├── backtest/execution.py               # MODIFIED: no changes needed (Protocol fits)
├── core/config.py                      # MODIFIED: add mt5: MT5Config | None = None
├── cli.py                              # MODIFIED: add `ta trade` command group
├── web/routes/
│   └── trading.py                      # NEW: live trading web routes
└── web/events.py                       # MODIFIED: add ta:trade:* events
```

---

## 5. Implementation Phases

### Phase A: Foundation (Bridge + Config + Data)

#### Story A1: MT5 Configuration Model

**File**: `execution/mt5_config.py`

```python
class MT5Config(BaseModel):
    enabled: bool = False
    mt5_files_dir: Path = Path(".")
    poll_interval_ms: int = 5
    max_orders: int = 10
    max_lot_size: float = 1.0
    lot_size_digits: int = 2
    mode: Literal["demo", "live"] = "demo"
    magic_number: int = 123456
    slippage_points: int = 10
```

**Changes**:
- Add `mt5: MT5Config | None = None` to `AppConfig` in `core/config.py`
- Add `mt5_password` support to `core/secrets.py` (stored in keyring)

#### Story A2: DWX Connect Client Wrapper

**File**: `execution/mt5_bridge.py`

- `MT5Bridge` class wrapping the vendored DWX Connect client
- Lifecycle: `connect() → subscribe → trade → disconnect`
- Callbacks: `on_tick()`, `on_bar_data()`, `on_historic_data()`, `on_order_event()`, `on_message()`
- Health: `is_connected()`, `ping()`
- Reconnection: exponential backoff with max retries
- Thread safety: file I/O operations serialized with `threading.Lock`

**Vendored**: Copy DWX Connect's `dwx_client.py` into `execution/_dwx/` (BSD-3 license)

#### Story A3: MT5 Data Provider

**File**: `data/providers/mt5.py`

- `MT5Provider(DataProvider)` implementation
- `fetch(symbol, interval, start, end)` → canonical OHLCV DataFrame (10 columns, matching existing schema)
- `check_connectivity()` → ping MT5 bridge
- Streams tick data → aggregates to OHLCV bars
- Stores in existing Parquet cache + DuckDB via `DataRepository`
- CLI: `ta fetch EURUSD --source mt5`
- Registers with `ProviderRegistry` as `"mt5"`

---

### Phase B: Execution Layer

#### Story B1: Order Translator

**File**: `execution/order_translator.py`

- `translate_signal(signal: SignalModel, sizing_config) -> OrderSpec`
  - `signal > 0 → "buy"`, `< 0 → "sell"`, `== 0 → flat/close`
- `order_to_dwx(order: OrderSpec, symbol: str) -> dict`
  - Maps to DWX `open_order()` format
- `dwx_to_fill(dwx_response: dict) -> FillResult`
  - Maps DWX response back to `FillResult`
- Decimal boundary: uses `from_float()`/`to_float()` per `core/types.py` conventions

#### Story B2: MT5 Execution Router

**File**: `execution/mt5_router.py`

```python
class MT5ExecutionRouter:
    """ExecutionRouter implementation that routes orders to MT5 via DWX Connect."""

    def submit(self, order: OrderSpec, bar: pd.Series) -> FillResult | None:
        # Translate OrderSpec → DWX order dict
        # Call bridge.open_order()
        # Map response → FillResult
```

- Implements `ExecutionRouter` Protocol (structural typing — no inheritance needed)
- Supports: market, limit, stop orders
- Error mapping: MT5 error codes → `QTAError` hierarchy

#### Story B3: Position Manager

**File**: `execution/position_manager.py`

- Tracks open positions by: ticket, symbol, strategy, magic number
- Reconciles with MT5 on startup (DWX `open_orders` dict)
- Real-time P&L calculation using `Decimal`
- Position limits: max per symbol, per strategy, total
- Orphan detection: positions in MT5 not in local state → alert

#### Story B4: Pre-Trade Risk Gates

**File**: `execution/risk_gates.py`

```python
class RiskGate(Protocol):
    def check(self, order: OrderSpec, positions: dict, account: dict) -> bool: ...

class MaxPositionSize(RiskGate): ...
class MaxDrawdown(RiskGate): ...
class DailyLossLimit(RiskGate): ...
class MaxOpenOrders(RiskGate): ...
class MaxLotSize(RiskGate): ...
```

- All read from existing `RiskConfig` in `core/config.py`
- Chain of responsibility pattern: all gates must pass for order to proceed
- Logging: every gate pass/fail logged via structlog

---

### Phase C: CLI + Web Interface

#### Story C1: CLI Trading Commands

**New command group `ta trade`**:

```bash
ta trade status                           # MT5 connection status, account info
ta trade signal SPY --strategy sma_cross  # Generate signal (dry-run, no execution)
ta trade start SPY --strategy sma_cross --paper   # Start paper trading loop
ta trade start SPY --strategy sma_cross --live     # Start live trading (needs confirmation)
ta trade stop                             # Gracefully shutdown
ta trade stop --close-all                 # Shutdown + close all positions
ta trade positions                        # List open positions with P&L
ta trade history --last 7d               # Show trade history
```

Flags:
- `--dry-run` on all commands: shows what would happen without executing
- `--live` requires interactive confirmation (type "I UNDERSTAND THE RISKS")
- `--strategy` selects from registered strategies
- `--magic` override magic number for this session

#### Story C2: Web Trading Routes

**File**: `web/routes/trading.py`

| Route | Method | Purpose |
|---|---|---|
| `/trading/status` | GET | MT5 connection status, account info |
| `/trading/positions` | GET | Open positions with live P&L |
| `/trading/start` | POST | Start trading strategy |
| `/trading/stop` | POST | Stop trading |
| `/trading/history` | GET | Trade history with filters |
| `/trading/signal/{symbol}` | GET | Current signal (dry-run) |

SSE streams (new events in `web/events.py`):
- `ta:trade:tick` — real-time price updates
- `ta:trade:order_filled` — order execution notifications
- `ta:trade:position_changed` — position updates
- `ta:trade:risk_alert` — risk gate triggers

#### Story C3: Dashboard Trading Panel

Add trading panel to Streamlit dashboard (`ui/app.py`):
- Connection status indicator (green/red dot)
- Account info sidebar: balance, equity, margin, free margin
- Live positions table with real-time P&L
- Start/stop strategy controls with strategy selector
- Real-time equity curve overlay on backtest results
- Trade history table with filters

---

### Phase D: Polish + Testing

#### Story D1: MT5 EA Setup Guide

Document step-by-step macOS setup:

1. Download MT5 Mac app from https://www.metatrader5.com/en/download
2. Open broker demo account (any MT5 broker)
3. Open MT5 → File → Open Data Folder
4. Copy `dwx_server_mt5.mq5` into `MQL5/Experts/`
5. Open in MetaEditor → Compile (F7)
6. Restart MT5 → drag EA onto chart
7. Configure EA inputs: `MaximumOrders`, `MaximumLotSize`, etc.
8. Note the `MQL5/Files/` path for trade_advisor config
9. Run `ta config set-key mt5_files_dir` with the path
10. Test: `ta trade status` should show connected

macOS `MQL5/Files/` path is typically:
```
/Users/<username>/Library/Application Support/MetaTrader 5/Bottles/metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Files
```

#### Story D2: Integration Tests

```python
# tests/integration/test_mt5_bridge.py
@pytest.mark.integration
@pytest.mark.skipif(not mt5_available(), reason="MT5 not connected")
class TestMT5Bridge:
    def test_connect_disconnect(self): ...
    def test_subscribe_tick_data(self): ...
    def test_fetch_historic_data(self): ...
    def test_open_close_order(self): ...

# tests/unit/test_order_translator.py
class TestOrderTranslator:
    def test_buy_signal_to_order(self): ...
    def test_sell_signal_to_order(self): ...
    def test_flat_signal_closes_position(self): ...
    def test_decimal_precision(self): ...

# tests/unit/test_mt5_router.py
class TestMT5ExecutionRouter:
    def test_market_order_filled(self): ...
    def test_limit_order_pending(self): ...
    def test_rejected_order_returns_none(self): ...

# tests/unit/test_risk_gates.py
class TestRiskGates:
    def test_max_position_size_passes(self): ...
    def test_max_position_size_blocks(self): ...
    def test_max_drawdown_gate(self): ...
    def test_daily_loss_limit(self): ...

# tests/unit/test_position_manager.py
class TestPositionManager:
    def test_reconcile_on_startup(self): ...
    def test_orphan_detection(self): ...
    def test_pnl_calculation_decimal(self): ...
```

---

## 6. Dependencies

### No Additional pip Dependencies

DWX Connect is file-based. Zero extra packages needed. The vendored client uses only stdlib (`os`, `json`, `time`, `threading`).

```toml
# pyproject.toml — no changes needed for runtime deps
# Optional: add an extras group for documentation
[project.optional-dependencies]
mt5-dev = [
    # Future: if we add direct MT5 API support for Windows users
    "MetaTrader5>=5.0.45; sys_platform == 'win32'",
]
```

### Vendored Dependencies

```
execution/_dwx/dwx_client.py    # From https://github.com/darwinex/dwxconnect/blob/main/python/dwx_client.py
execution/_dwx/LICENSE           # BSD-3-Clause (Darwinex)
```

---

## 7. Configuration

### Environment Variables (.env)

```bash
# MT5 Bridge Configuration
TA_MT5__ENABLED=false
TA_MT5__MT5_FILES_DIR=/Users/you/Library/Application Support/MetaTrader 5/Bottles/metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Files
TA_MT5__MODE=demo
TA_MT5__POLL_INTERVAL_MS=5
TA_MT5__MAX_ORDERS=10
TA_MT5__MAX_LOT_SIZE=0.1
TA_MT5__LOT_SIZE_DIGITS=2
TA_MT5__MAGIC_NUMBER=123456
TA_MT5__SLIPPAGE_POINTS=10
```

### YAML Config

```yaml
mt5:
  enabled: false
  mt5_files_dir: "/Users/you/Library/Application Support/MetaTrader 5/Bottles/metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Files"
  mode: demo
  poll_interval_ms: 5
  max_orders: 10
  max_lot_size: 0.1
  lot_size_digits: 2
  magic_number: 123456
  slippage_points: 10
```

---

## 8. Risk Safeguards

| Safeguard | Implementation |
|---|---|
| **Default disabled** | `mt5.enabled = false` — must be explicitly turned on |
| **Demo-first** | `mode = "demo"` is default; `live` requires explicit config change |
| **Interactive confirmation** | `ta trade start --live` requires typing confirmation string |
| **Risk gates** | Every order passes through `RiskGate` chain before submission |
| **Kill switch** | `ta trade stop --close-all` immediately closes everything |
| **Position reconciliation** | On startup, reconciles with MT5 to detect orphaned positions |
| **Audit trail** | Every order, fill, rejection logged via structlog |
| **Lot size cap** | `max_lot_size` in config, enforced server-side by EA |
| **Order cap** | `max_orders` in config, enforced server-side by EA |
| **Slippage protection** | `slippage_points` in config, passed to EA |

---

## 9. Data Flow

### Signal to Trade Flow

```
Strategy.generate_signals(ohlcv)
         ↓
    SignalModel (signal: +1.0, symbol: "EURUSD", confidence: 0.8)
         ↓
    OrderTranslator.translate_signal(signal, sizing_config)
         ↓
    OrderSpec(side="buy", order_type="market", quantity=0.01)
         ↓
    RiskGate chain (all must pass)
         ↓
    MT5ExecutionRouter.submit(order, bar)
         ↓
    OrderTranslator.order_to_dwx(order, symbol)
         ↓
    MT5Bridge → DWX Connect → file write → MT5 EA reads → executes
         ↓
    MT5 EA writes response → DWX Connect reads → MT5Bridge callback
         ↓
    OrderTranslator.dwx_to_fill(response) → FillResult
         ↓
    PositionManager.update(fill)
         ↓
    structlog audit entry
```

### Market Data Flow

```
MT5 EA polls broker for prices (every MILLISECOND_TIMER ms)
         ↓
    EA writes tick data to MQL5/Files/
         ↓
    DWX Connect client reads file (every poll_interval_ms)
         ↓
    MT5Bridge.on_tick(symbol, bid, ask) callback
         ↓
    MT5Provider aggregates ticks → OHLCV bars
         ↓
    DataRepository.upsert(bar_data) → DuckDB
         ↓
    Also stored in Parquet cache via cache.py
```

---

## 10. Broker Selection Notes

This plan is **broker-agnostic**. DWX Connect works with any broker that supports MT5. When choosing a broker, consider:

| Broker | Regulation | Demo Available | MT5 Support | Notes |
|---|---|---|---|---|
| IC Markets | CySEC, ASIC | Yes | Yes | Popular for algo trading, low spreads |
| Pepperstone | FCA, ASIC | Yes | Yes | Fast execution, good API support |
| OANDA | FCA, CFTC | Yes | Yes | Also has REST API as alternative |
| Darwinex | FCA | Yes | Yes | DWX Connect built for their platform |
| FXCM | FCA | Yes | Yes | Good for forex |

Recommendation: Start with a **demo account** from any of the above. All offer free MT5 demo accounts with virtual funds.

---

## 11. Future Considerations

- **Multi-strategy support** — Multiple strategies trading simultaneously via different magic numbers
- **Walk-forward live** — Connect walk-forward validation to paper trading for continuous validation
- **Alerts/advisories** — PRD scope: generate trading advisories without auto-execution
- **Performance comparison** — Overlay live results on backtest results for degradation detection
- **Broker API fallback** — If MT5 is unavailable, fall back to broker REST API (OANDA, Alpaca)
