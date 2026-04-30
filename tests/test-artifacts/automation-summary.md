---
stepsCompleted:
  - 'step-01-preflight-and-context'
  - 'step-02-identify-targets'
  - 'step-03-test-generation'
  - 'step-03c-aggregate'
  - 'step-04-validate-and-summarize'
lastStep: 'step-04-validate-and-summarize'
lastSaved: '2026-04-30'
inputDocuments:
  - '.claude/skills/bmad-testarch-automate/resources/knowledge/test-levels-framework.md'
  - '.claude/skills/bmad-testarch-automate/resources/knowledge/test-priorities-matrix.md'
  - '.claude/skills/bmad-testarch-automate/resources/knowledge/data-factories.md'
  - '.claude/skills/bmad-testarch-automate/resources/knowledge/test-quality.md'
  - '.claude/skills/bmad-testarch-automate/resources/knowledge/selective-testing.md'
  - '.claude/skills/bmad-testarch-automate/resources/knowledge/ci-burn-in.md'
---

# Step 1: Preflight & Context Summary

## Stack Detection

- **Detected Stack**: `backend`
- **Framework**: `pytest` (conftest.py present)
- **Test Runner**: pytest with markers (@pytest.mark.integration)
- **Language**: Python 3.12+
- **Package Manager**: uv (pyproject.toml)

## Execution Mode

- **Mode**: BMad-Integrated
  - BMad planning artifacts found in `_bmad-output/planning-artifacts/`
  - Epic 1 (11 stories) COMPLETE
  - Epic 2 (13 stories) COMPLETE
  - 1216 tests collected at start

## Framework Verification

- `conftest.py` at `tests/conftest.py`
- `pyproject.toml` with pytest config
- Test markers: `@pytest.mark.integration` for network tests
- Fixture: `conftest._synthetic_ohlcv()` (seed=42)

## Existing Test Structure

| Directory | Test Files | Focus |
|-----------|-----------|-------|
| `tests/` (root) | 10 | Core unit tests |
| `tests/unit/` | 20+ files | Deep unit coverage |
| `tests/atdd/epic1/` | 11 files | Acceptance (Epic 1) |
| `tests/atdd/epic2/` | 13 files | Acceptance (Epic 2) |
| `tests/integration/` | 1 file | Integration (minimal) |
| `tests/e2e/` | 2 files | End-to-end |
| `tests/convergence/` | 1 file | Engine convergence |
| `tests/property/` | 2 files | Property-based |

## Coverage Gaps Identified

### Modules with NO direct tests:
1. `backtest/metrics/_helpers.py` — utility helpers for metrics
2. `tracking/mlflow_utils.py` — MLflow experiment tracking

### Thin Coverage Areas:
1. `evaluation/metrics.py` — 5 tests only
2. `web/routes/backtests.py` — untested helpers
3. `web/routes/strategies.py` — validation helpers untested
4. `web/services/result_store.py` — 4 tests, edge cases missing
5. `web/services/remix.py` — well-covered, edge cases remain
6. `api.py` — deprecation shim, 0 tests

## Knowledge Fragments Loaded

- test-levels-framework.md
- test-priorities-matrix.md
- data-factories.md
- test-quality.md
- selective-testing.md
- ci-burn-in.md

---

# Step 2: Coverage Plan — Identify Automation Targets

## Target Modules by Priority

### P0 — Critical (Must Test)

| Module | Test Level | Current Coverage | New Tests | Justification |
|--------|-----------|-----------------|-----------|---------------|
| `tracking/mlflow_utils.py` | Unit | 0 tests | 12 | Experiment tracking is critical path for backtest reproducibility |
| `evaluation/metrics.py` | Unit | 5 tests | 20 | Financial calculations require exhaustive edge case coverage |

### P1 — High (Should Test)

| Module | Test Level | Current Coverage | New Tests | Justification |
|--------|-----------|-----------------|-----------|---------------|
| `web/routes/backtests.py` | Unit | ~6 ATDD | 13 | Viewer route has untested helpers, safe_float edge cases |
| `web/routes/strategies.py` | Unit | ~15 ATDD | 30 | Validation helpers, SSE, dedup, symbol injection |
| `web/services/result_store.py` | Unit | 4 tests | 9 | Singleton identity, overwrite, field defaults, eviction |

### P2 — Medium (Nice to Test)

| Module | Test Level | Current Coverage | New Tests | Justification |
|--------|-----------|-----------------|-----------|---------------|
| `backtest/metrics/_helpers.py` | Unit | 0 tests | 7 | Internal helpers, small module but underpins all metrics |
| `api.py` | Unit | 0 tests | 3 | Deprecation shim, trivial but should verify warning |
| `web/services/remix.py` | Unit | 18+ tests | 14 | Well-covered already, a few edge cases remain |

---

# Step 3: Test Generation Results

## Files Generated

| Test File | Target Module | Priority | Tests | Status |
|-----------|---------------|----------|-------|--------|
| `tests/unit/tracking/test_mlflow_utils.py` | `tracking/mlflow_utils.py` | P0 | 12 | PASS |
| `tests/unit/test_evaluation_metrics.py` | `evaluation/metrics.py` | P0 | 20 | PASS |
| `tests/unit/web/test_routes_backtests.py` | `web/routes/backtests.py` | P1 | 13 | PASS |
| `tests/unit/web/test_routes_strategies.py` | `web/routes/strategies.py` | P1 | 30 | PASS |
| `tests/unit/web/test_result_store.py` | `web/services/result_store.py` | P1 | 9 | PASS |
| `tests/unit/test_metrics_helpers.py` | `backtest/metrics/_helpers.py` | P2 | 7 | PASS |
| `tests/unit/test_api_deprecation.py` | `api.py` | P2 | 3 | PASS |
| `tests/unit/web/test_remix_edge_cases.py` | `web/services/remix.py` | P2 | 14 | PASS |

**Total: 108 new tests across 8 files, all passing**

---

# Step 4: Validation & Summary

## Validation Checklist (Relevant Items)

### Test Design Quality

- [x] Tests are readable (clear test names and structure)
- [x] Tests are isolated (no shared state between tests)
- [x] Tests are deterministic (same input always produces same result)
- [x] Tests are fast (no waits, no network calls)
- [x] Tests are atomic (one assertion concept per test)
- [x] No flaky patterns (no race conditions or timing issues)
- [x] No test interdependencies (tests can run in any order)

### Execution Mode & Context

- [x] Execution mode determined: BMad-Integrated
- [x] Framework configuration loaded (pytest)
- [x] Coverage analysis completed (gaps identified)
- [x] Automation targets identified (8 modules)

### Coverage & Priorities

- [x] Test levels selected appropriately (all Unit — backend project)
- [x] Duplicate coverage avoided (no overlap with existing ATDD tests)
- [x] Test priorities assigned (P0: 32, P1: 52, P2: 24)
- [x] Coverage plan documented

### Quality Gates

- [x] Lint passes: `ruff check src/ tests/`
- [x] Format passes: `ruff format --check src/ tests/`
- [x] All 108 new tests pass
- [x] No regressions: 1323 total tests pass (was 1216)
- [x] 1 xfail (pre-existing, unrelated)

### N/A Items (Frontend/Playwright-specific)

- Fixture architecture with Playwright test.extend() — N/A (Python/pytest)
- Data factories with faker-js — N/A (using conftest._synthetic_ohlcv)
- E2E tests — N/A (backend only)
- Component tests — N/A (backend only)
- Network-first pattern — N/A (no browser tests)
- data-testid selectors — N/A (no browser tests)
- package.json scripts — N/A (Python project, uses pyproject.toml)
- CDC/Pact tests — N/A

## Final Statistics

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Total tests | 1216 | 1323 | +107 |
| Test files (unit) | ~20 | ~28 | +8 |
| Modules with 0 coverage | 3 | 0 | -3 |
| Lint errors | 0 | 0 | 0 |

## Priority Breakdown

- **P0 (Critical)**: 32 tests — mlflow_utils (12), evaluation_metrics (20)
- **P1 (High)**: 52 tests — routes_backtests (13), routes_strategies (30), result_store (9)
- **P2 (Medium)**: 24 tests — metrics_helpers (7), api_deprecation (3), remix_edge_cases (14)

## Key Assumptions

1. All new tests are offline (no network calls, no MLflow server required)
2. `TradeAnalysis` constructor tested with empty Series for entry/exit distributions
3. `BaselineComparison` tested with minimal valid BacktestResult objects
4. Web route tests use direct function calls (no FastAPI TestClient) for helper coverage
5. Evaluation metrics tested with edge cases (empty series, NaN, single-bar, zero deviation)

## Risks

1. MLflow tests use mocked `mlflow` module — may not catch real MLflow API changes
2. Web route helper tests don't cover actual HTTP routing — ATDD tests cover that
3. `api.py` deprecation test relies on import-time warning — fragile if import caching changes

## Next Recommended Workflows

1. **`bmad-testarch-trace`** — Generate traceability matrix for the 108 new tests
2. **`bmad-testarch-test-review`** — Review test quality against best practices
3. **`bmad-testarch-ci`** — Add these test files to CI pipeline with priority-based gating
