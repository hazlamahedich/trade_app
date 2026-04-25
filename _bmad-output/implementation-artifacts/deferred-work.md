# Deferred Work Items

Source: Story 1.3 code review (2026-04-26)

These items were identified during code review but are **pre-existing issues** not introduced by Story 1.3. They are deferred to future stories or a dedicated cleanup sprint.

## Deferred Items

### DEF-1: Import-time `mkdir` in shim `config.py`

- **File:** `src/trade_advisor/config.py` (shim)
- **Issue:** Lines 18-19 create directories at import time (`mkdir(parents=True, exist_ok=True)`)
- **Impact:** Any test or module that imports `config.py` triggers filesystem I/O
- **Deferral reason:** Pre-existing; shim will be removed once all consumers migrate to `core/config.py`
- **Target:** Story 1.9 (Composition Root) or when shim is deprecated

### DEF-2: Pre-existing mypy errors in `engine.py`

- **File:** `src/trade_advisor/backtest/engine.py`
- **Lines:** 127, 141
- **Issue:** `float()` called on pandas scalar results — mypy sees `Series | float` ambiguity
- **Deferral reason:** Pre-existing; not introduced by Story 1.3
- **Target:** Story 2.3 (Vectorized Backtest Engine) or type-narrowing pass

### DEF-3: `load_config()` env-file encoding hardcoded to UTF-8

- **File:** `src/trade_advisor/core/config.py`
- **Issue:** `env_file_encoding="utf-8"` is hardcoded in `SettingsConfigDict`
- **Deferral reason:** UTF-8 is the de facto standard; no user has requested alternate encoding
- **Target:** If internationalization requirement arises

### DEF-4: `keyring` backend pinning only covers macOS

- **File:** `src/trade_advisor/core/secrets.py`
- **Issue:** Backend pinning only handles `sys.platform == "darwin"`; Linux and Windows use auto-detection
- **Deferral reason:** Current target platform is macOS (Apple Silicon M1 Max per AGENTS.md)
- **Target:** Cross-platform support story (if needed)

### DEF-5: `SecretsConfig` field names hardcoded in `cli.py`

- **File:** `src/trade_advisor/cli.py`
- **Issue:** `set-key` validates against a hardcoded set of key names rather than introspecting `SecretsConfig`
- **Deferral reason:** Only 3 secret fields currently; hardcoded set is explicit and clear
- **Target:** When secret fields grow or become dynamic

### DEF-6: No config hot-reload mechanism

- **File:** `src/trade_advisor/core/config.py`
- **Issue:** Config is loaded once at startup; no file-watcher or reload signal
- **Deferral reason:** Config is frozen by design; hot-reload would violate immutability contract
- **Target:** If live-reload requirement arises (unlikely for frozen config)

### DEF-7: `format_config_error()` does not localize messages

- **File:** `src/trade_advisor/core/config.py`
- **Issue:** Error messages are English-only strings
- **Deferral reason:** No localization requirement in current PRD
- **Target:** If i18n requirement is added

## Deferred from: code review of 1-5-data-provider-interface-yahoo-finance (2026-04-25)

### DEF-8: `_PER_MINUTE_CREDIT_LIMIT` constant unused

- **File:** `src/trade_advisor/data/providers/twelvedata.py`
- **Issue:** `_PER_MINUTE_CREDIT_LIMIT = 8` is defined but never referenced; no per-minute rate limiting implemented
- **Target:** If per-minute rate limiting is needed (Epic 2+)

### DEF-9: New `httpx.AsyncClient` created per request — no connection reuse

- **File:** `src/trade_advisor/data/providers/twelvedata.py`
- **Issue:** Each `fetch()` and `check_connectivity()` call creates a new `httpx.AsyncClient` with its own connection pool
- **Target:** Epic 2+ when batch fetching across many symbols makes connection reuse worthwhile

### DEF-10: `check_connectivity` burns TwelveData API credit on health checks

- **File:** `src/trade_advisor/data/providers/twelvedata.py`
- **Issue:** Connectivity probe uses the `/price` endpoint which consumes a daily credit; automated health checks would deplete the 800/day budget
- **Target:** If health-check loops are added (dashboard/monitoring stories)

### DEF-11: Pandas Timestamp nanosecond precision vs DuckDB microsecond

- **File:** `src/trade_advisor/data/storage.py`
- **Issue:** Pandas Timestamp has nanosecond precision by default; DuckDB TIMESTAMPTZ uses microsecond. Potential for silent truncation or duplicate PKs on INSERT OR REPLACE
- **Target:** Epic 5 when sub-microsecond timestamp accuracy matters

## Deferred from: re-review of 1-5-data-provider-interface-yahoo-finance (2026-04-25)

### DEF-12: Orphaned transaction if ROLLBACK also fails in _execute_many

- **File:** `src/trade_advisor/infra/db.py:297-306`
- **Issue:** If COMMIT fails and the subsequent ROLLBACK also fails (suppressed by contextlib.suppress), the connection remains inside an active transaction. Next _execute_many call will fail with "cannot start a transaction within a transaction"
- **Target:** If multi-layer transaction recovery becomes a concern (unlikely for single-process DuckDB)

### DEF-13: store() assumes single symbol/interval per DataFrame

- **File:** `src/trade_advisor/data/storage.py:140-141`
- **Issue:** _get_existing_adj_close takes df["symbol"].iloc[0] only — multi-symbol DFs would get wrong adj_close lookups
- **Target:** If store() ever receives multi-symbol DataFrames (currently always called per-provider per-symbol)

### DEF-14: Timestamp timezone mismatch may silently skip adj_close protection

- **File:** `src/trade_advisor/data/storage.py:142`
- **Issue:** If timestamps are naive datetime objects, IN(?) comparison against TIMESTAMPTZ column may return zero matches, bypassing adj_close protection
- **Target:** If any provider produces naive timestamps (current providers guarantee UTC-aware)

### DEF-15: Partial batch upsert — no cross-batch rollback

- **File:** `src/trade_advisor/data/storage.py:121-124`
- **Issue:** Each 1000-row batch is its own transaction. Failure on Nth batch leaves batches 1..N-1 committed
- **Target:** If whole-operation atomicity is required (current design trades simplicity for partial-write tolerance)

### DEF-16: incoming_source semantic mismatch in data_sources upsert

- **File:** `src/trade_advisor/data/storage.py:130`
- **Issue:** incoming_source (from df["source"]) is stored as provider_type, conflating data source name with provider classification
- **Target:** Story 1.7+ when data_sources table semantics are formalized

### DEF-17: Row tuple reconstruction fragile to column reordering

- **File:** `src/trade_advisor/data/storage.py:108-119`
- **Issue:** Hardcoded positional indices (row[0]..row[9]) for adj_close overwrite would break silently if _OHLCV_INSERT_COLUMNS order changes
- **Target:** If column order changes or a more maintainable approach is needed

## Deferred from: code review of 1-6-data-validation-anomaly-detection (2026-04-25)

### DEF-18: `get_data_freshness` architecturally misplaced in validation module

- **File:** `src/trade_advisor/data/validation.py`
- **Issue:** `get_data_freshness()` is a data-access function living in the validation module; breaks single-responsibility
- **Target:** Extract to `data/freshness.py` when function grows beyond thin wrapper (per Dev Note §6)

### DEF-19: `quality_mask` semantics confusing (True=error, not True=good)

- **File:** `src/trade_advisor/data/validation.py`
- **Issue:** `quality_mask` boolean Series uses True to mark ERROR rows, but the name implies True=good quality
- **Target:** Rename to `error_mask` in refactor sprint; current name matches ATDD test expectations
