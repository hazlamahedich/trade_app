# Deferred Work

## Deferred from: code review of 1-7-data-explorer-web-page.md (2026-04-27)

- Redundant pagination validation in `data.py:145-148` — dead code, harmless. FastAPI `Query(ge=1)` already enforces constraints.
- Static files mount at import time in `main.py:39` — `if _static_dir.exists()` runs once at module load. If directory is created later, mount is skipped for process lifetime.
- SQL hardcodes `interval = '1d'` in `data.py:38,50` — symbol detail and corp action queries only check '1d' interval. Data at other intervals is invisible.
- `symbol_detail.html` crashes on NULL OHLC/volume — template applies format filters unconditionally. Schema declares NOT NULL, but no runtime guard.
- `YahooProvider` deferred import inside `fetch_symbol` handler — intentional: avoids import-time network dependency.
- `get_db()` has no guard for missing `app.state.db` — lifespan context manager guarantees the attribute exists. If lifespan fails, the app doesn't start.
- `fetch_symbol` TOCTOU race on concurrent fetches — `DataRepository.store` reads then writes across two lock acquisitions. RW lock serializes individual operations but not the read-then-write sequence.
- Existing test fixtures (`ohlcv_with_nan`, `ohlcv_with_duplicates`, etc.) missing `symbol`, `interval`, `source` columns — pre-existing divergence from schema contract. Not introduced by Story 1.7.
