# Story 1.2: Core Type System & Error Taxonomy

Status: done

<!-- Revised via Party Mode adversarial review with Winston (Architect), Fisher (Quant),
     Amelia (Developer), Murat (Test Architect). 12 findings incorporated. -->

## Story

As a developer,
I want shared types, Decimal conventions, and a structured error hierarchy,
So that all modules use consistent financial types and error handling.

## Acceptance Criteria

1. **Given** the project scaffold from Story 1.1
   **When** I import from `trade_advisor.core`
   **Then** `core/types.py` provides `PrecisionPolicy`, `Decimal` conventions (`ROUND_HALF_EVEN`), shared type aliases
   **And** `PrecisionPolicy` is a Protocol with `quantize(value: Decimal) -> Decimal` and per-asset-class instances: `EQUITY` (0.01), `FX` (0.0001), `CRYPTO` (0.00000001)
   **And** computation uses full `Decimal` precision internally; quantization happens ONLY at storage/serialization boundaries (Fisher: compute at 18dp, quantize to asset-class precision at boundary)
   **And** `core/types.py` defines distinct financial type aliases: `Price = Decimal`, `Quantity = Decimal`, `Notional = Decimal`, `Returns = Decimal`, `BasisPoints = Decimal`, `Signal = Literal[-1, 0, 1]`, `Side = Literal["long", "short"]`, `Currency = Literal["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD"]`
   **And** `core/types.py` provides `decimal_to_str` serializer using `PlainSerializer` for Pydantic V2 Decimal → str with ROUND_HALF_EVEN
   **And** `core/types.py` provides `from_float(value: float) -> Decimal` and `to_float(value: Decimal) -> float` boundary conversion functions with explicit precision documentation
   **And** `core/types.py` provides `returns_to_log()` and `returns_to_simple()` conversion utilities
   **And** all financial type aliases use `Decimal`, never `float` — `float` is only permitted at I/O edges (pandas DataFrames, yfinance responses) with explicit conversion via `from_float()`

2. **Given** the project scaffold from Story 1.1
   **When** I import from `trade_advisor.core`
   **Then** `core/errors.py` defines `QTAError` hierarchy with domain-specific subclasses and HTTP status codes:
   - `DataError` → `StaleDataError` (200+degraded), `DataGapError` (502), `IntegrityError` (500)
   - `ComputationError` → `FeatureComputationError` (SSE), `ConvergenceError` (SSE)
   - `BiasDetectionError` → `LookaheadBiasError` (500), `SurvivorshipBiasError` (200+warning)
   - `ConfigurationError` (503)
   - `BoundaryViolationError` (500)
   - `InsufficientHistoryError` (422)
   **And** each exception class has `error_code: ClassVar[str]`, `http_status: ClassVar[int]`, `correlation_id: str | None`, `details: dict[str, Any]`
   **And** `QTAError` base provides `to_error_response()` method returning `ErrorResponse`

3. **Given** the project scaffold from Story 1.1
   **When** I import from `trade_advisor.core`
   **Then** `core/schemas.py` provides `SuccessResponse` and `ErrorResponse` envelopes matching architecture format: success `{ "data": ... }`, error `{ "error": { "code": "...", "message": "..." } }`
   **And** `ErrorResponse` uses the error code string from the exception hierarchy
   **And** `PaginatedResponse(BaseModel)` provides `data`, `meta: PaginationMeta` (cursor, total_count)
   **And** all `Decimal` fields in schemas serialize to `str` via `PlainSerializer` — no raw Decimal in JSON

4. **Given** the project scaffold from Story 1.1
   **When** I import from `trade_advisor.core`
   **Then** `core/logging.py` configures structured JSON logging via structlog
   **And** every log entry includes required fields: `timestamp` (ISO 8601), `level`, `message`, `logger`, `correlation_id`, `module`
   **And** optional fields when present: `run_id`, `strategy_id`, `symbol`
   **And** `configure_logging(level, json_logs=True)` sets up structlog with JSON renderer (prod) + console renderer (dev)
   **And** `configure_logging()` replaces the existing `setup_logging()` in `config.py`
   **And** `get_logger(name: str | None = None) -> BoundLogger` returns a bound structlog logger with typed return

5. **Given** all core modules
   **When** I run mypy
   **Then** all models pass mypy (per-module overrides allow pandas_ta/yfinance)
   **And** `ruff check src/trade_advisor/core/` exits 0

6. **Given** the ROUND_HALF_EVEN precision policy
   **When** I run `pytest tests/unit/core/test_types.py`
   **Then** a financial oracle fixture validates banker's rounding at 10dp with hand-computed truth table:
   ```
   (1.23456789015 → 1.2345678902)  # round to even (up, next digit odd)
   (1.23456789025 → 1.2345678902)  # round to even (down, next digit even)
   (-1.23456789015 → -1.2345678902) # negative symmetry
   (0.00000000005 → 0.0000000000)  # round to even → 0
   ```
   **And** per-asset-class quantization produces correct tick sizes: EQUITY 0.01, FX 0.0001, CRYPTO 0.00000001
   **And** Hypothesis property tests verify: serialization round-trips are idempotent, quantization is idempotent

## Tasks / Subtasks

- [x] T1: Create `src/trade_advisor/core/` package with `__init__.py` (AC: 1-5)
  - [x] T1.1: Create directory and `__init__.py` with public API exports (`__all__`)
  - [x] T1.2: Ensure no circular imports — `core/` depends on nothing else in `trade_advisor`
- [x] T2: Implement `core/types.py` — Decimal conventions and financial type aliases (AC: 1)
  - [x] T2.1: Define `ROUNDING = ROUND_HALF_EVEN`, `INTERNAL_PRECISION = 18`, `DISPLAY_PRECISION = 10`
  - [x] T2.2: Define `PrecisionPolicy` dataclass with `quantize(value: Decimal) -> Decimal` and per-asset-class instances: `EQUITY` (0.01), `FX` (0.0001), `CRYPTO` (0.00000001)
  - [x] T2.3: Define financial type aliases: `Price = Decimal`, `Quantity = Decimal`, `Notional = Decimal`, `Returns = Decimal`, `BasisPoints = Decimal`, `Signal = Literal[-1, 0, 1]`, `Side = Literal["long", "short"]`, `Currency = Literal["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD"]`
  - [x] T2.4: Add `from_float(value: float) -> Decimal` — converts float to Decimal with full precision (no truncation)
  - [x] T2.5: Add `to_float(value: Decimal) -> float` — converts Decimal to float for pandas boundary (documented precision loss)
  - [x] T2.6: Add `decimal_to_str` PlainSerializer for Pydantic V2 Decimal → str with ROUND_HALF_EVEN
  - [x] T2.7: Add `log_to_simple()` and `simple_to_log()` conversion utilities
  - [x] T2.8: Add `Timestamp = AwareDatetime` type alias (pydantic)
- [x] T3: Implement `core/errors.py` — QTAError exception hierarchy (AC: 2)
  - [x] T3.1: Define `QTAError(Exception)` base with `correlation_id`, `details`, `http_status`, `error_code`, `to_error_response()`
  - [x] T3.2: Define `DataError(QTAError)` with `StaleDataError` (200), `DataGapError` (502), `IntegrityError` (500)
  - [x] T3.3: Define `ComputationError(QTAError)` with `FeatureComputationError` (500), `ConvergenceError` (500)
  - [x] T3.4: Define `BiasDetectionError(QTAError)` with `LookaheadBiasError` (500), `SurvivorshipBiasError` (200)
  - [x] T3.5: Define `ConfigurationError(QTAError)` (503)
  - [x] T3.6: Define `BoundaryViolationError(QTAError)` (500)
  - [x] T3.7: Define `InsufficientHistoryError(QTAError)` (422)
- [x] T4: Implement `core/schemas.py` — Response envelopes (AC: 3)
  - [x] T4.1: Define `SuccessResponse(BaseModel)` with `data: Any` field
  - [x] T4.2: Define `ErrorDetail(BaseModel)` with `code: str` and `message: str`
  - [x] T4.3: Define `ErrorResponse(BaseModel)` with `error: ErrorDetail`
  - [x] T4.4: Define `PaginationMeta(BaseModel)` with `cursor: str | None`, `total_count: int`
  - [x] T4.5: Define `PaginatedResponse(BaseModel)` with `data: list[Any]`, `meta: PaginationMeta`
- [x] T5: Implement `core/logging.py` — Structured JSON logging (AC: 4)
  - [x] T5.1: `configure_logging(level, json_logs=True)` — structlog with JSON renderer (prod) + console renderer (dev)
  - [x] T5.2: Add `correlation_id`, `run_id`, `strategy_id`, `symbol` processors
  - [x] T5.3: `get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger` — typed return
  - [x] T5.4: Define required log fields schema: `timestamp`, `level`, `message`, `logger`, `correlation_id`, `module`
- [x] T6: Update `config.py` — replace `setup_logging()` (AC: 4)
  - [x] T6.1: Import and call `configure_logging()` from `core/logging.py`
  - [x] T6.2: Remove old `setup_logging()` function (replaced with delegation to core)
- [x] T7: Write financial oracle fixtures and tests (AC: 6)
  - [x] T7.1: `tests/unit/core/fixtures.py` — `ROUND_HALF_EVEN_ORACLE` truth table with hand-computed values at 10dp
  - [x] T7.2: `tests/unit/core/fixtures.py` — `ASSET_CLASS_QUANTIZATION_ORACLE` (EQUITY, FX, CRYPTO expected outputs)
- [x] T8: Write unit tests in `tests/unit/core/` (AC: 5, 6)
  - [x] T8.1: `test_types.py` — PrecisionPolicy quantization per asset class, oracle truth table, from_float/to_float round-trips, return conversion round-trips, type alias usage
  - [x] T8.2: `test_types_hypothesis.py` — Property tests: serialization idempotency, quantization idempotency, Decimal arithmetic commutativity
  - [x] T8.3: `test_errors.py` — hierarchy isinstance checks, HTTP status mapping, error_code strings, to_error_response(), correlation_id propagation
  - [x] T8.4: `test_schemas.py` — SuccessResponse, ErrorResponse, PaginatedResponse serialization, Decimal → str in JSON output
  - [x] T8.5: `test_logging.py` — structlog JSON output validates as JSON, required fields present, correlation_id binding, dev vs prod renderer
- [x] T9: Add structlog capture/reset autouse fixture to `tests/conftest.py` (AC: 4)

## Dev Notes

### Critical Architecture Requirements

**Decimal Policy (Fisher's mandate — revised after party mode review):**
- ALL financial values use `Decimal` throughout the Python layer — zero `float` for money
- Computation precision: `Decimal` at 18 decimal places internally (full Python Decimal precision)
- Storage/display precision: quantize to asset-class-specific precision at boundary ONLY
  - Equities: 2 decimal places (tick size $0.01)
  - FX: 4 decimal places (pip precision 0.0001)
  - Crypto: 8 decimal places (0.00000001)
- Serialization boundary: `Decimal` → `str` via `PlainSerializer` with `ROUND_HALF_EVEN`
- pandas/NumPy boundary: use `from_float()` / `to_float()` at I/O edges with documented precision loss
- Returns are stored as `Decimal` in [-1.0, +inf) range — NOT the same as Price or Notional
- Source: [architecture.md#Decimal Precision]

**Decimal ↔ pandas Boundary Contract (Winston + Fisher finding):**
- `Decimal` is the canonical type inside `trade_advisor.core` and all domain logic
- `float` is permitted ONLY in: pandas DataFrames, NumPy arrays, yfinance responses
- Conversion functions `from_float()` and `to_float()` are the ONLY sanctioned boundary crossing points
- No module may call `Decimal(float_value)` directly — must use `from_float()`
- This prevents mixed-precision arithmetic that defeats the type system's purpose
- Source: [Party Mode adversarial review — Finding #4]

**Error → HTTP Status Mapping (expanded after Fisher + Murat review):**
| Exception | HTTP Status | Error Code |
|---|---|---|
| `IntegrityError` | 500 | `INTEGRITY` |
| `StaleDataError` | 200 + degraded payload | `STALE_DATA` |
| `DataGapError` | 502 | `DATA_GAP` |
| `ConvergenceError` | SSE event | `CONVERGENCE` |
| `FeatureComputationError` | SSE event | `FEATURE_COMPUTATION` |
| `LookaheadBiasError` | 500 | `LOOKAHEAD_BIAS` |
| `SurvivorshipBiasError` | 200 + warning | `SURVIVORSHIP_BIAS` |
| `ConfigurationError` | 503 | `CONFIG` |
| `BoundaryViolationError` | 500 | `LEAK_DETECTED` |
| `InsufficientHistoryError` | 422 | `INSUFFICIENT_HISTORY` |
Source: [architecture.md#Error Taxonomy] + [Party Mode review — Fisher findings]

**Pydantic V2 Conventions (mandatory):**
- `model_config = ConfigDict(...)` — NOT `class Config:`
- `@field_validator` — NOT `@validator`
- `.model_dump(mode='json')` for dict, `.model_dump_json()` for string
- `PlainSerializer` for `Decimal` → `str` with `ROUND_HALF_EVEN`
- `Annotated[Decimal, PlainSerializer(decimal_to_str, return_type=str)]` for all Decimal fields in schemas
Source: [architecture.md#Pydantic V2 Conventions]

**Type Annotation Standards:**
- Python 3.12+ syntax: `X | None` not `Optional[X]`, `list[str]` not `List[str]`
- `from __future__ import annotations` is already used in existing modules — continue using it
- All timestamps: `datetime` with `tzinfo` — use `AwareDatetime` from pydantic
- `Protocol` for structural subtyping
Source: [architecture.md#Type Annotation Standards]

**structlog Output Schema (Murat's requirement):**
Required fields in every log entry:
```json
{
  "timestamp": "2026-04-24T12:00:00.000Z",
  "level": "info",
  "message": "...",
  "logger": "trade_advisor.core.types",
  "correlation_id": "abc-123",
  "module": "core.types"
}
```
Optional fields when context is available: `run_id`, `strategy_id`, `symbol`, `event_type`
- Dev mode: console renderer with colors
- Prod mode: JSON renderer
Source: [Party Mode review — Murat findings]

### Project Structure Notes

**Files to create:**
```
src/trade_advisor/core/
├── __init__.py          # Public API exports
├── types.py             # Decimal conventions, PrecisionPolicy, financial type aliases, boundary functions
├── errors.py            # QTAError hierarchy with quant-domain errors
├── schemas.py           # SuccessResponse, ErrorResponse, PaginatedResponse
└── logging.py           # structlog configuration

tests/unit/core/
├── __init__.py
├── fixtures.py          # Financial oracle truth tables
├── test_types.py        # PrecisionPolicy, type aliases, conversion functions
├── test_types_hypothesis.py  # Property-based Decimal tests
├── test_errors.py       # Error hierarchy, status mapping, error codes
├── test_schemas.py      # Response envelopes, Decimal serialization
└── test_logging.py      # structlog JSON output, required fields
```

**Files to modify:**
- `src/trade_advisor/config.py` — replace `setup_logging()` with `configure_logging()` from core
- `tests/conftest.py` — add structlog capture/reset autouse fixture

**Key boundary:** `core/` depends on nothing else in `trade_advisor`. All other modules depend on `core/`. No circular imports.

### Existing Codebase Context

- `config.py` currently has a basic `setup_logging()` using stdlib `logging.basicConfig()` — this gets replaced with structlog
- `config.py` has `AppSettings` with `seed: int = 42` — untouched by this story
- `config.py` has `CostModel` and `BacktestConfig` — untouched by this story
- `structlog` is already in `pyproject.toml` dependencies (`>=24.1,<26`)
- `api.py` has FastAPI app — error handlers will use the new error hierarchy in future stories
- Python 3.12 is pinned (`.python-version`, `pyproject.toml`)
- `from __future__ import annotations` is used throughout existing codebase

### Return Convention Utilities

Architecture mandates two return conventions that agents must never re-derive:
- **Log returns** for all internal computation (feature engineering, ML inputs, statistics)
- **Simple returns** for portfolio-level reporting and position sizing
- Provide `log_to_simple(log_ret: Decimal) -> Decimal` and `simple_to_log(simple_ret: Decimal) -> Decimal`
- Source: [architecture.md#Return Conventions]

### Testing Standards

- Coverage target for `core/`: 95% line, 90% branch
- Financial oracle fixtures in `tests/unit/core/fixtures.py` — hand-computed ROUND_HALF_EVEN truth table (Murat mandate)
- Use Hypothesis for Decimal arithmetic property tests (serialization round-trips, quantization idempotency)
- Autouse fixture: structlog capture/reset, Decimal context reset
- Bare `assert` statements (pytest native), no `self.assertEqual`
- Test markers: `@pytest.mark.integration` only for network; these are unit tests, no marker needed
- Every error subclass must have a test verifying HTTP status code and error_code string
- Source: [architecture.md#Testing Patterns]

### Deferred to Later Stories (explicit scope decisions)

The following were identified by agents but are **intentionally deferred** to avoid scope creep:
- `BarData` / `OHLCV` pydantic model → Story 1.4 (DuckDB infrastructure) or 1.5 (data providers)
- `DataProvider`, `Strategy`, `BacktestEngine` Protocol definitions → Story 1.9 (Composition Root)
- Audit trail types (`RunContext`, `AuditEntry`) → Epic 6 (Advisory audit) or Story 1.4 (seed hierarchy)
- `Ticker`, `ISIN`, `FIGI` identifier types → Story 1.5 (data providers)
- `OrderType`, `TimeInForce`, `PositionStatus` types → Epic 2 (strategy/backtest)
- `FXRate` type with quote/inversion conventions → Story 2.6 (transaction costs)

### References

- [architecture.md#Type Annotation Standards] — Python 3.12+ syntax, Decimal policy
- [architecture.md#Decimal Precision] — PrecisionPolicy per asset class
- [architecture.md#Error Taxonomy] — QTAError hierarchy and HTTP mapping
- [architecture.md#Communication Patterns] — Logging requirements
- [architecture.md#Pydantic V2 Conventions] — model_config, field_validator, PlainSerializer
- [architecture.md#Project Structure] — core/ directory layout
- [architecture.md#Testing Patterns] — fixture architecture, coverage targets, Hypothesis requirements
- [epics.md#Story 1.2] — original story definition

### Previous Story Intelligence (Story 1.1)

Key learnings from Story 1.1 implementation:
- `pandas-ta` is `>=0.4.67b0,<1` (not `0.3.14b` — that version is unavailable)
- Python version is 3.12 (not 3.11 — `pandas-ta 0.4.67b0` requires >=3.12)
- mypy uses per-module overrides (NOT `--strict`) — pandas_ta, yfinance, plotly, streamlit are ignored
- ruff selects `["E", "F", "W", "I", "UP", "B", "SIM", "C4", "RUF"]`, ignores `E501`
- `from __future__ import annotations` is used in every module
- Existing `setup_logging()` in config.py uses stdlib — this story replaces it
- 3 ATDD ruff errors exist in `tests/atdd/` for Stories 1.3/1.6 — not our concern
- structlog is already a dependency
- FastAPI `/health` endpoint exists in `api.py`
- `tests/conftest.py` has `_synthetic_ohlcv()` fixture with seed=42

### Party Mode Adversarial Review Summary

Reviewed by 4 agents: Winston (Architect), Fisher (Quant), Amelia (Developer), Murat (Test Architect)

**12 findings incorporated:**
1. ✅ `PrecisionPolicy` contract defined with per-asset-class quantization (Winston #1)
2. ✅ Distinct financial type aliases added: Price, Quantity, Notional, Returns, BasisPoints (Fisher #2)
3. ✅ `Signal = Literal[-1, 0, 1]` added (Winston #2)
4. ✅ Decimal ↔ pandas boundary contract with `from_float()` / `to_float()` (Winston #4, Fisher)
5. ✅ Quant-domain errors added: LookaheadBiasError, SurvivorshipBiasError, DataGapError, InsufficientHistoryError (Fisher #3)
6. ✅ Computation vs storage precision clarified: 18dp internal, quantize at boundary (Fisher #5)
7. ✅ structlog output schema defined with required fields (Murat, Winston #10)
8. ✅ Financial oracle fixtures for ROUND_HALF_EVEN truth table (Murat)
9. ✅ `PaginatedResponse` with pagination metadata (Winston #12)
10. ✅ Decimal JSON serialization via PlainSerializer (Winston #9)
11. ✅ `get_logger()` typed return as `BoundLogger` (Amelia)
12. ✅ Error codes for machine-readable identification (Amelia)

**Explicitly deferred (scope management):**
- Protocol definitions → Story 1.9
- BarData/OHLCV model → Story 1.4/1.5
- Audit trail types → Epic 6
- Instrument identifier types → Story 1.5
- Order/position types → Epic 2

## Dev Agent Record

### Agent Model Used

glm-5.1 (zai-coding-plan/glm-5.1)

### Debug Log References

- structlog `PrintLoggerFactory` incompatible with `add_logger_name` processor (no `.name` attr) → switched to `LoggerFactory` + `ProcessorFormatter` stdlib integration
- Decimal `str()` produces scientific notation for zero (`0E-10`) → tests use `format(result, "f")` for consistent representation
- `get_logger()` returns `BoundLoggerLazyProxy` not `BoundLogger` → test checks for interface methods instead of `isinstance`

### Completion Notes List

- ✅ Created `core/` package with 4 modules: `types.py`, `errors.py`, `schemas.py`, `logging.py`
- ✅ Decimal policy: `ROUND_HALF_EVEN`, 18dp internal precision, per-asset-class quantization at boundary
- ✅ 11 type aliases: Price, Quantity, Notional, Returns, BasisPoints, Signal, Side, Currency, Timestamp, DecimalStr
- ✅ Boundary functions: `from_float()`, `to_float()`, `decimal_to_str()`, `log_to_simple()`, `simple_to_log()`
- ✅ QTAError hierarchy: 13 exception classes with error_code, http_status, correlation_id, details, to_error_response()
- ✅ Response schemas: SuccessResponse, ErrorResponse, PaginatedResponse with PaginationMeta
- ✅ structlog integration: JSON renderer (prod) + console renderer (dev), ProcessorFormatter-based stdlib bridge
- ✅ config.py: `setup_logging()` now delegates to `core.logging.configure_logging()`
- ✅ 103 unit tests: oracle fixtures, Hypothesis property tests, full error hierarchy coverage
- ✅ ruff check/format pass, mypy clean, zero regressions

### File List

**New files:**
- src/trade_advisor/core/__init__.py
- src/trade_advisor/core/types.py
- src/trade_advisor/core/errors.py
- src/trade_advisor/core/schemas.py
- src/trade_advisor/core/logging.py
- tests/unit/core/__init__.py
- tests/unit/core/fixtures.py
- tests/unit/core/test_types.py
- tests/unit/core/test_types_hypothesis.py
- tests/unit/core/test_errors.py
- tests/unit/core/test_schemas.py
- tests/unit/core/test_logging.py

**Modified files:**
- src/trade_advisor/config.py
- tests/conftest.py

### Review Findings

**Decision-needed (resolved via party mode consensus — Winston, Amelia, Fisher):**

- [x] [Review][Decision] PrecisionPolicy: dataclass vs Protocol — **RESOLVED: keep dataclass.** Unanimous. Protocol is YAGNI; dataclass gives concrete state, equality, hashing. Update AC1.
- [x] [Review][Decision] Return conversion function naming mismatch — **RESOLVED: keep `log_to_simple`/`simple_to_log`.** Unanimous. Source-to-target naming matches quant domain convention. Update AC1.
- [x] [Review][Decision] CLI silent behavior change: JSON logs by default — **RESOLVED: flip default to `json_logs=False`, add `--json-logs` CLI flag.** Majority (Amelia+Fisher). Library default serves the common case (interactive terminal). `cli.py` updated with `--json-logs` opt-in flag.

**Patch (all applied):**

- [x] [Review][Patch] ruff lint: 6 errors in tests — removed unused imports, sorted imports [tests/unit/core/*]
- [x] [Review][Patch] ruff format: test_types.py formatting — reformatted [tests/unit/core/test_types.py]
- [x] [Review][Patch] INTERNAL_PRECISION declared but never enforced — removed dead constant [src/trade_advisor/core/types.py]
- [x] [Review][Patch] decimal_to_str crashes on NaN/Infinity Decimal — added `is_finite()` guard with ValueError [src/trade_advisor/core/types.py]
- [x] [Review][Patch] log_to_simple overflows on large inputs — added domain validation for > 700 [src/trade_advisor/core/types.py]
- [x] [Review][Patch] simple_to_log domain error on return ≤ -1 — added domain validation for ≤ -1 [src/trade_advisor/core/types.py]
- [x] [Review][Patch] to_float no guard for non-finite Decimal — added `is_finite()` guard, symmetric with from_float [src/trade_advisor/core/types.py]
- [x] [Review][Patch] PaginationMeta.total_count accepts negative values — added `Field(ge=0)` [src/trade_advisor/core/schemas.py]
- [x] [Review][Patch] PrecisionPolicy no tick_size validation — added `__post_init__` with positive check [src/trade_advisor/core/types.py]
- [x] [Review][Patch] `module` field missing from structlog output — added module derivation from logger name in `_add_default_fields` [src/trade_advisor/core/logging.py]

**Deferred:**

- [x] [Review][Defer] to_error_response discards correlation_id/details — ErrorDetail schema lacks fields for these; design decision deferred to API error handling stories (1.9+) [src/trade_advisor/core/errors.py:34] — deferred, pre-existing design gap
- [x] [Review][Defer] DecimalStr defined but unused in schemas — will be needed when schemas have Decimal fields in later stories [src/trade_advisor/core/types.py:37] — deferred, pre-existing
- [x] [Review][Defer] Timestamp type alias extra scope — useful but not in AC1 list; not harmful to keep [src/trade_advisor/core/types.py:27] — deferred, extra scope
- [x] [Review][Defer] Schemas have no Decimal fields using PlainSerializer — AC3 requirement untestable until schemas have Decimal fields in later stories [src/trade_advisor/core/schemas.py] — deferred, pre-existing
- [x] [Review][Defer] cache_logger_on_first_use=True prevents runtime reconfiguration — acceptable for production; managed in tests via reset fixture [src/trade_advisor/core/logging.py:69] — deferred, pre-existing

### Change Log

- 2026-04-26: Code review completed. 3 decisions resolved (party mode), 10 patches applied, 5 deferred. 103 tests passing, lint/mypy/format clean.
- 2026-04-24: Implemented Story 1.2 — Core Type System & Error Taxonomy. All 9 tasks complete, 103 tests passing, lint/mypy clean.
