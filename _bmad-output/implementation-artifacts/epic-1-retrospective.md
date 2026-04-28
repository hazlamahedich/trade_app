# Epic 1 Retrospective: Project Foundation & Data Access

**Date**: 2026-04-28  
**Status**: DONE  
**Stories**: 11/11 complete  
**Tests**: 600 passing, 0 failing, 3 intentionally skipped  

---

## What Went Well

- **ATDD-first approach paid off.** Stories 1.1–1.4 had 36 red-phase ATDD tests written before implementation. Unskipping them caught real issues (path resolution, missing APIs, version mismatches) that would have been missed with only unit tests.
- **Decimal convention established early.** `DecimalStr` type alias with `PlainSerializer` ensures all financial values serialize consistently. Applied across `BacktestConfig`, `RiskConfig`, `ExecutionConfig`.
- **Error taxonomy is clean.** `QTAError` → `DataError`/`ComputationError`/`ConfigurationError`/`BoundaryViolationError` hierarchy with HTTP status mapping works well for the web layer.
- **Structured logging with structlog** provides correlation IDs and JSON output out of the box.
- **HTMX/Preact bridge** is functional — dynamic port allocation, DOM-polling waits, and zero-tolerance leak detection make E2E tests reliable.

## What Could Be Improved

- **ATDD tests drifted from implementation.** Several ATDD tests (Stories 1.1–1.3) made assumptions that didn't match reality:
  - Expected `env_prefix="QTA_"` but config uses no prefix
  - Expected `get_api_key()` to exist but only `SecretsConfig.get_secret_value()` did
  - Expected `setup_logging()` but only `configure_logging()` existed
  - Hardcoded Python 3.11 when project uses 3.12
  - Better approach: write ATDD tests closer to implementation, or implement the expected APIs
- **`mypy --strict` has 12 pre-existing errors.** These are in `DataConfig` missing args, backtest engine arg types, and `twelvedata.py` date assignment. Should be addressed before Epic 2.
- **Fragile `parents[N]` path resolution.** Multiple test files used `Path(__file__).resolve().parents[N]` with hardcoded indices that break if directory structure changes. Fixed with `pyproject.toml`-based discovery where possible.
- **Signal dtype confusion.** `SmaCross.generate_signals` returned `int8` while Protocol specified `float`. Resolved to `float64` to support future ML continuous signals, but the mismatch should have been caught earlier.

## Deferred Items Resolved

| Item | Resolution |
|------|-----------|
| `SmaCross` int8 dtype | Changed to float64 |
| `_synthetic_ohlcv(n=0)` crash | Added guard returning empty DataFrame |
| `assert_no_lookahead_bias` vacuous pass | Added non-trivial signal assertion |
| `_scan_imports` regex false positives | Rewritten with AST parsing |
| `SignalBatch` empty batch | Explicit empty guard added |
| `quality_mask` naming | Renamed to `error_mask` |
| `get_data_freshness` location | Moved to `data/storage.py` |
| NULL OHLC/volume template crash | Added `is not none` guards |
| Hardcoded SQL `interval='1d'` | Parameterized with query param |
| Hardcoded port 8199 | Dynamic port allocation via `_find_free_port()` |
| urlopen response leak | Closed with `contextlib.closing()` |
| Fragile `parents[3]` path | `pyproject.toml`-based root discovery |
| `wait_for_timeout` flakiness | DOM polling with `_wait_for_island_stable()` |
| Leak tolerance +2 | Tightened to zero tolerance |
| `SignalModel.confidence` | Changed to `float \| None` with range constraint |
| `DecimalStr` in schemas | Applied to `BacktestConfig`, `RiskConfig`, `ExecutionConfig` |
| `get_db()` no guard | Added None check with RuntimeError |
| `to_error_response` missing fields | Added `correlation_id` and `details` |
| Hypothesis tests for signals | Added `test_signal_properties.py` |
| `setup_logging` missing | Added as alias for `configure_logging` |
| `quantize` missing | Added to `types.py` |
| `get_api_key` missing | Added to `secrets.py` |

## Deferred Items Remaining (Low Risk)

- **W2**: `SignalBatch.strategy_name` could use `Literal` type — premature with only one strategy
- **W3**: `AppContainer.config` as read-only — over-engineering for current needs
- **W4**: Sphinx-style `:param:` annotations on Protocol docs — cosmetic
- **Schema migration**: Checksums for additive migrations, rollback enforcement, orphaned table detection — all low-risk design choices
- **Bootstrap caching**: `bootstrap()` called per invocation — acceptable for CLI/Streamlit patterns
- **`mypy --strict`**: 12 pre-existing errors to address in hardening pass

## Metrics

| Metric | Value |
|--------|-------|
| Stories completed | 11/11 |
| Unit/ATDD/Property tests passing | 600 |
| Intentionally skipped | 3 |
| Lint errors | 0 |
| Format issues | 0 |
| Mypy errors (pre-existing) | 12 |
| Deferred items resolved | 22 |
| Deferred items remaining | 6 |

## Recommendations for Epic 2

1. **Write ATDD tests after architecture decisions** — avoid speculative ATDD that assumes APIs that don't exist
2. **Address `mypy --strict` errors** before adding new code — debt compounds
3. **Use `quantize()` and `DecimalStr`** consistently for all new financial fields
4. **Use `pyproject.toml`-based root discovery** for all new test files — not `parents[N]`
5. **Signal dtype is `float`** — all strategies must return `float64` Series, not `int`
