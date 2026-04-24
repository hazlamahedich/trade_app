# Deferred Work

## Deferred from: code review of story-1.1 (2026-04-25)

- Cache gap detection missing: `_range_covered` checks only min/max, not continuity. Internal gaps in cached data are served silently. `cache.py:48-53`
- MLflow `_INITIALIZED` global flag prevents switching experiments after first use. `mlflow_utils.py:33`
- Floating-point noise in strategy returns (`-1e-17`) inflates win-rate denominator in `compute_metrics`. `metrics.py:47`
- No file locking on Parquet cache — concurrent writes can corrupt cache files. `cache.py:44`
- `pct_change().fillna(0.0)` on first bar masks bad/NaN price data silently. `engine.py:67`

## Deferred from: code review of 1-2-core-type-system-error-taxonomy.md (2026-04-26)

- to_error_response discards correlation_id/details — ErrorDetail schema lacks fields for these; design decision deferred to API error handling stories (1.9+). `errors.py:34`
- DecimalStr defined but unused in schemas — will be needed when schemas have Decimal fields in later stories. `types.py:37`
- Timestamp type alias extra scope — useful but not in AC1 list; not harmful to keep. `types.py:27`
- Schemas have no Decimal fields using PlainSerializer — AC3 requirement untestable until schemas have Decimal fields in later stories. `schemas.py`
- cache_logger_on_first_use=True prevents runtime reconfiguration — acceptable for production; managed in tests via reset fixture. `logging.py:69`
