# Deferred Work

## Deferred from: code review of story-1.1 (2026-04-25)

- Cache gap detection missing: `_range_covered` checks only min/max, not continuity. Internal gaps in cached data are served silently. `cache.py:48-53`
- MLflow `_INITIALIZED` global flag prevents switching experiments after first use. `mlflow_utils.py:33`
- Floating-point noise in strategy returns (`-1e-17`) inflates win-rate denominator in `compute_metrics`. `metrics.py:47`
- No file locking on Parquet cache — concurrent writes can corrupt cache files. `cache.py:44`
- `pct_change().fillna(0.0)` on first bar masks bad/NaN price data silently. `engine.py:67`
