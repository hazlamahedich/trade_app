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
