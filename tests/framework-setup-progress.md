---
stepsCompleted: ['step-01-preflight', 'step-02-select-framework', 'step-03-scaffold-framework']
lastStep: 'step-03-scaffold-framework'
lastSaved: '2026-04-24'
---

# Test Framework Setup Progress

## Step 1: Preflight

- **Detected stack**: backend (Python 3.11+, no frontend package.json)
- **Existing framework**: pytest already configured with `tests/conftest.py`
- **No E2E framework** detected (no Playwright/Cypress)
- **Architecture docs**: `_bmad-output/planning-artifacts/architecture.md`
- **Existing tests**: `tests/test_*.py`, `tests/atdd/epic1/test_story_*.py`

## Step 2: Framework Selection

- **Backend/unit**: pytest (enhance existing)
- **E2E (Streamlit UI)**: Playwright via `pytest-playwright`
  - Python API keeps whole test stack in one language
  - Handles Streamlit WebSocket reconnection natively
  - Superior CI headless performance

## Step 3: Scaffold

### Directory Structure

```
tests/
├── conftest.py              # root fixtures (existing)
├── unit/                    # pure unit tests (no I/O)
│   ├── conftest.py          # extended fixtures (ohlcv_with_signals, various sizes)
│   └── test_example_enhanced.py
├── integration/             # network-dependent tests
│   ├── conftest.py          # real symbol/date fixtures
│   └── test_example_integration.py
├── e2e/                     # Playwright + Streamlit E2E
│   ├── conftest.py          # streamlit_url + app_page fixtures
│   ├── pages/
│   │   └── dashboard.py     # page object for dashboard UI
│   └── test_dashboard.py    # E2E test cases
├── support/
│   ├── factories/
│   │   └── ohlcv_factory.py # make_ohlcv, make_signals, make_equity
│   └── helpers/
│       └── assertions.py    # assert_no_lookahead_bias, assert_signals_in_range
└── atdd/                    # existing acceptance tests (unchanged)
```

### Config Files

- `playwright.config.py` — Playwright settings (headless, timeouts, screenshots)
- `.env.example` — environment variable template
- `pyproject.toml` updated:
  - Added `pytest-playwright>=0.5` to dev deps
  - Added markers: `e2e`, `slow`
  - Enhanced `integration` marker description

### Key Patterns

- **Page Object Model**: `tests/e2e/pages/dashboard.py` encapsulates Streamlit selectors
- **Factory pattern**: `make_ohlcv()` with seed-based determinism
- **Session-scoped Streamlit**: app process starts once per test session
- **Custom assertions**: `assert_no_lookahead_bias()`, `assert_signals_in_range()`
