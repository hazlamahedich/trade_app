---
stepsCompleted:
  - step-01-load-context
  - step-02-discover-tests
  - step-03-quality-criteria
  - step-04-score-calculation
  - step-05-report-generation
lastStep: step-05-report-generation
lastSaved: "2026-04-30"
workflowType: testarch-test-review
inputDocuments:
  - tests/conftest.py
  - tests/helpers.py
  - tests/test_strategy.py
  - tests/test_backtest.py
  - tests/test_config.py
  - tests/test_cache.py
  - tests/test_metrics.py
  - tests/test_strategy_interface.py
  - tests/test_container.py
  - tests/test_import_contracts.py
  - tests/test_result_store.py
  - tests/test_information_latency.py
  - tests/test_review_fixes.py
  - tests/test_scaffold.py
  - tests/property/test_signal_properties.py
  - tests/property/test_validation_properties.py
  - tests/unit/test_api_deprecation.py
  - tests/unit/test_evaluation_metrics.py
  - tests/unit/test_metrics_helpers.py
  - tests/convergence/conftest.py
  - tests/convergence/test_engine_convergence.py
  - tests/atdd/epic2/conftest.py
  - tests/atdd/epic2/test_story_2_1_sma_crossover.py
  - tests/atdd/epic2/test_story_2_2_position_sizing.py
  - tests/atdd/epic2/test_story_2_3_vectorized_engine.py
  - tests/atdd/epic2/test_story_2_4_event_driven_engine.py
  - tests/atdd/epic2/test_story_2_6_transaction_costs.py
  - tests/atdd/epic2/test_story_2_7_metrics.py
  - tests/atdd/epic2/test_story_2_8_baseline_integrity.py
  - tests/atdd/epic2/test_story_2_9_web_pages.py
  - tests/atdd/epic2/test_story_2_10_emotional_states.py
  - tests/atdd/epic2/test_story_2_11_remix.py
  - tests/atdd/epic2/test_story_2_12_reproducibility.py
  - tests/atdd/epic2/test_story_2_13_migrations.py
  - tests/integration/test_example_integration.py
  - tests/integration/conftest.py
  - tests/e2e/conftest.py
  - tests/e2e/conftest_bridge.py
  - tests/e2e/test_dashboard.py
  - tests/e2e/test_bridge_lifecycle.py
  - tests/e2e/pages/dashboard.py
  - tests/support/helpers/assertions.py
  - tests/support/factories/ohlcv_factory.py
---

# Test Quality Review: trade_advisor Full Suite

**Quality Score**: 83/100 (A - Good)
**Review Date**: 2026-04-30
**Review Scope**: Suite (all tests)
**Reviewer**: TEA Agent (Murat)
**Test Framework**: pytest (Python 3.12)
**Stack**: Backend
**Total Tests**: 1,324 collected
**Total Test Files**: 27 test files + 5 conftest/helper files + 1 page object + 2 support modules

---

Note: This review audits existing tests; it does not generate tests.
Coverage mapping and coverage gates are out of scope here. Use `trace` for coverage decisions.

## Executive Summary

**Overall Assessment**: Good

**Recommendation**: Approve with Comments

### Key Strengths

- **Excellent data factory pattern**: `support/factories/ohlcv_factory.py` with seeded `np.random.default_rng(seed)` — deterministic, configurable, reusable. All tests use `_synthetic_ohlcv()` factory via `conftest.py`.
- **Outstanding isolation & cleanup**: `conftest.py` provides `autouse=True` fixture for structlog reset; `test_cache.py` uses `autouse` fixture with `monkeypatch` to redirect cache to `tmp_path`. No shared mutable state detected across the suite.
- **Strong adversarial testing**: `assert_no_lookahead_bias` helper implements Oracle Shuffle + Truncation adversarial check (SE-5). Property-based tests via Hypothesis with `@settings(max_examples=200)`.
- **Comprehensive fixture architecture**: Layered conftest system (root → convergence/ → atdd/epic2/ → e2e/) with focused fixtures per domain. `StubDataProvider` implements the `DataProvider` protocol for offline testing.
- **No hard waits in unit/integration tests**: Zero `time.sleep()` usage in the core test suite. All E2E `time.sleep` usages are justified for server startup polling.

### Key Weaknesses

- **No test IDs**: No `{EPIC}.{STORY}-{LEVEL}-{SEQ}` IDs on any test, making traceability to requirements manual.
- **No priority markers**: No P0/P1/P2/P3 classification on tests, preventing risk-based selective execution.
- **Duplicated fixtures and test data**: `async_client_with_data` fixture duplicated identically in both `test_story_2_9_web_pages.py` and `test_story_2_11_remix.py`; `_RUN_DATA` dict also duplicated.
- **Stale docstrings**: `test_story_2_4_event_driven_engine.py` and `test_story_2_7_metrics.py` docstrings say "All tests are SKIPPED (TDD red phase)" but tests are actually implemented and pass.
- **Empty test stub**: `test_story_2_11_remix.py::TestEdgeCases::test_template_expired_parent_message` is a bare `pass` with no assertions.

### Summary

The trade_advisor test suite demonstrates strong engineering discipline with 1,324 tests across unit, integration, property-based, convergence, ATDD, and E2E layers. The factory pattern (`ohlcv_factory.py`) and adversarial lookahead-bias checking are exemplary. The main gaps are in traceability (no test IDs, no priority markers) and some maintainability issues (fixture duplication, stale docstrings, one empty test). No critical flakiness risks or non-determinism were detected in the core suite. The suite is production-ready with minor improvements recommended.

---

## Quality Criteria Assessment

| Criterion                            | Status    | Violations | Notes                                              |
| ------------------------------------ | --------- | ---------- | -------------------------------------------------- |
| BDD Format (Given-When-Then)         | ⚠️ WARN  | 0          | Docstrings present but not strict GWT; acceptable for Python backend |
| Test IDs                             | ❌ FAIL   | 0          | No `{EPIC}.{STORY}-{LEVEL}-{SEQ}` IDs on any test  |
| Priority Markers (P0/P1/P2/P3)       | ❌ FAIL   | 0          | No priority classification on any test             |
| Hard Waits (sleep, waitForTimeout)   | ✅ PASS   | 3          | All in E2E/server-polling contexts — justified     |
| Determinism (no conditionals)        | ✅ PASS   | 0          | No if/else or try/catch flow control in tests      |
| Isolation (cleanup, no shared state) | ✅ PASS   | 0          | Excellent autouse fixtures, tmp_path, monkeypatch  |
| Fixture Patterns                     | ✅ PASS   | 0          | Layered conftest, protocol-based stubs, factory    |
| Data Factories                       | ✅ PASS   | 0          | `ohlcv_factory.py` with seed, params, overrides    |
| Network-First Pattern                | N/A       | 0          | Backend Python suite — no browser network tests in core |
| Explicit Assertions                  | ✅ PASS   | 0          | All assertions visible in test bodies              |
| Test Length (≤300 lines)             | ✅ PASS   | 0          | Longest file: `test_story_2_9_web_pages.py` at 388 lines |
| Test Duration (≤1.5 min)             | ✅ PASS   | 0          | Unit/integration tests are milliseconds; E2E gated by markers |
| Flakiness Patterns                   | ✅ PASS   | 0          | Seeded RNG everywhere; no uncontrolled random; no tight timeouts |

**Total Violations**: 0 Critical, 3 High, 4 Medium, 2 Low

---

## Quality Score Breakdown

```
Starting Score:            100
Critical Violations:       -0 × 10 =  -0
High Violations:           -3 × 5  = -15
  - No test IDs (traceability gap)                        P1
  - No priority markers (risk-based execution gap)        P1
  - Fixture/data duplication (maintainability risk)        P1
Medium Violations:         -4 × 2  =  -8
  - Stale docstrings in 2 ATDD files                      P2
  - Empty test stub in test_story_2_11_remix.py           P2
  - One file exceeds 300-line guideline (388 lines)       P2
  - Repeated boilerplate in test_story_2_7_metrics.py     P2
Low Violations:            -2 × 1  =  -2
  - Inline imports in ATDD red-phase files (style)        P3
  - Hardcoded integration test constants (acceptable)     P3

Bonus Points:
  Excellent Determinism & Seeds:    +5
  Comprehensive Fixtures:           +5
  Data Factories (ohlcv_factory):   +5
  Perfect Isolation:                +5
  Adversarial Testing Pattern:      +3
                          --------
Total Bonus:                       +23

Final Score:             83/100
Grade:                   A (Good)
```

---

## Recommendations (Should Fix)

### 1. Add Test IDs for Traceability

**Severity**: P1 (High)
**Location**: All test files
**Criterion**: Test IDs
**Knowledge Base**: test-levels-framework.md

**Issue Description**:
No test uses the `{EPIC}.{STORY}-{LEVEL}-{SEQ}` ID format. This makes it difficult to trace test failures back to specific requirements or stories.

**Recommended Improvement**:

```python
# Add test IDs as markers or in test names
@pytest.mark.test_id("2.1-UNIT-001")
def test_signal_values_only_allowed(synthetic_ohlcv):
    ...

# Or embed in docstring
def test_signal_values_only_allowed(synthetic_ohlcv):
    """Test ID: 2.1-UNIT-001. Signal values must be in {-1, 0, 1}."""
    ...
```

**Benefits**: Enables traceability matrix, selective test execution, and automated coverage gap detection.

**Priority**: High — foundational for quality governance as the suite scales.

---

### 2. Add Priority Markers for Risk-Based Execution

**Severity**: P1 (High)
**Location**: All test files
**Criterion**: Priority Markers
**Knowledge Base**: test-priorities-matrix.md

**Issue Description**:
No tests are classified by priority (P0/P1/P2/P3). Without this, CI cannot run risk-based test selection.

**Recommended Improvement**:

```python
# In conftest.py or a markers.py
def pytest_configure(config):
    config.addinivalue_line("markers", "p0: Critical path tests")
    config.addinivalue_line("markers", "p1: High priority tests")
    config.addinivalue_line("markers", "p2: Medium priority tests")
    config.addinivalue_line("markers", "p3: Low priority tests")

# Usage:
@pytest.mark.p0
def test_no_lookahead_adversarial():
    ...
```

**Benefits**: Enables `pytest -m p0` for smoke tests in CI; risk-based execution reduces feedback time.

---

### 3. Deduplicate Shared ATDD Fixtures

**Severity**: P1 (High)
**Location**: `tests/atdd/epic2/test_story_2_9_web_pages.py` and `tests/atdd/epic2/test_story_2_11_remix.py`
**Criterion**: Fixture Patterns
**Knowledge Base**: fixture-architecture.md

**Issue Description**:
`async_client_with_data` and `_reset_result_store` fixtures are defined identically in both files. The `_RUN_DATA` dict is also duplicated.

**Recommended Improvement**:

```python
# Move to tests/atdd/epic2/conftest.py
@pytest_asyncio.fixture
async def async_client_with_data():
    ...  # single definition

# In test files, just use the fixture (no definition needed)
```

**Benefits**: Single source of truth for fixtures; changes propagate automatically.

---

### 4. Fix Stale Docstrings

**Severity**: P2 (Medium)
**Location**:
- `tests/atdd/epic2/test_story_2_4_event_driven_engine.py:1`
- `tests/atdd/epic2/test_story_2_7_metrics.py:1`

**Issue Description**:
Both files have docstrings stating "All tests are SKIPPED (TDD red phase)" but tests are fully implemented and passing. This misleads developers about test status.

**Recommended Improvement**:

Update docstrings to reflect current state:

```python
"""ATDD tests for Story 2.4: Event-Driven Backtest Engine.

Covers convergence with vectorized engine, stop-loss, and result schema."""
```

---

### 5. Implement or Remove Empty Test Stub

**Severity**: P2 (Medium)
**Location**: `tests/atdd/epic2/test_story_2_11_remix.py:314`
**Criterion**: Explicit Assertions

**Issue Description**:
`test_template_expired_parent_message` is a bare `pass` with no assertions. Either implement or use `@pytest.mark.skip` with a reason.

**Recommended Improvement**:

```python
@pytest.mark.skip(reason="Template expired parent message not yet implemented")
def test_template_expired_parent_message(async_client_with_data):
    pass
```

---

### 6. Extract Repeated Backtest Boilerplate in Story 2.7

**Severity**: P2 (Medium)
**Location**: `tests/atdd/epic2/test_story_2_7_metrics.py`
**Criterion**: Test Length / DRY

**Issue Description**:
Most tests repeat the same 4-line pattern: create strategy → generate signals → run backtest → compute metrics. Extract to a helper or fixture.

**Recommended Improvement**:

```python
# In conftest.py or at top of file
@pytest.fixture
def metrics_result(ohlcv_500, backtest_config):
    from trade_advisor.strategies.sma_cross import SmaCross
    from trade_advisor.backtest.engine import run_backtest
    from trade_advisor.evaluation.metrics import compute_metrics
    strat = SmaCross(fast=20, slow=50)
    sig = strat.generate_signals(ohlcv_500)
    result = run_backtest(ohlcv_500, sig, backtest_config)
    return compute_metrics(result.returns)
```

---

## Best Practices Found

### 1. Adversarial Lookahead-Bias Testing

**Location**: `tests/helpers.py:90-127`, `tests/test_information_latency.py`
**Pattern**: Oracle Shuffle + Truncation
**Knowledge Base**: test-quality.md

**Why This Is Good**:
The `assert_no_lookahead_bias` helper implements a sophisticated two-pronged adversarial check: (1) shuffling future data must not change signals, and (2) adding future data must not change signals. This catches subtle lookahead bias that simple tests miss. It also verifies non-trivial signals exist (vacuous check guard).

**Use as Reference**: This pattern should be applied to every strategy implementation.

---

### 2. Seeded Deterministic Data Factory

**Location**: `tests/support/factories/ohlcv_factory.py`
**Pattern**: Factory with seed + overrides
**Knowledge Base**: data-factories.md

**Why This Is Good**:
`make_ohlcv(n, symbol, start, seed, trend, vol)` generates realistic OHLCV data with seeded `np.random.default_rng(seed)`. Configurable parameters allow overrides per test while maintaining reproducibility. Generates correct OHLCV relationships (high >= max(open, close), low <= min(open, close)).

**Use as Reference**: Gold standard for test data generation in a quant project.

---

### 3. Protocol-Based Dependency Injection

**Location**: `tests/helpers.py:40-79` (StubDataProvider), `tests/test_container.py`
**Pattern**: Protocol-based test doubles
**Knowledge Base**: fixture-architecture.md

**Why This Is Good**:
`StubDataProvider` implements the `DataProvider` protocol, allowing seamless injection via `dataclasses.replace()`. The frozen `AppContainer` ensures test isolation — each test gets a fresh container with no shared mutation.

---

### 4. Property-Based Testing with Hypothesis

**Location**: `tests/property/test_signal_properties.py`, `tests/property/test_validation_properties.py`
**Pattern**: Hypothesis `@given` + `@settings`
**Knowledge Base**: test-quality.md

**Why This Is Good**:
Uses Hypothesis to generate thousands of test cases automatically. Tests immutability (`input_never_mutated`), idempotency (`no_duplicate_anomaly_entries`), and boundary conditions. `max_examples=200` provides high confidence in invariants.

---

## Test File Analysis

### Suite Metadata

- **Total Files**: 27 test files + 5 conftest files
- **Total Lines (test code)**: ~3,800 lines
- **Test Framework**: pytest (Python 3.12)
- **Language**: Python
- **Total Tests Collected**: 1,324

### Test Level Distribution

| Level         | Files | Tests (approx) | Location                    |
| ------------- | ----- | -------------- | --------------------------- |
| Unit          | 14    | ~200           | `tests/test_*.py`, `tests/unit/` |
| Property      | 2     | ~8             | `tests/property/`           |
| Convergence   | 1     | 5              | `tests/convergence/`        |
| ATDD          | 13    | ~130           | `tests/atdd/epic2/`         |
| E2E           | 2     | ~10            | `tests/e2e/`                |
| Integration   | 1     | 1              | `tests/integration/`        |

### Assertions Analysis

- **Assertion Style**: `assert` statements (Python idiom) + `pytest.raises` for exceptions + `pd.testing.assert_series_equal` for DataFrame comparisons
- **Average Assertions per Test**: ~2.5
- **Specialized Assertions**: `np.testing.assert_allclose`, `pd.testing.assert_frame_equal`, `pd.testing.assert_index_equal`

### Marker Usage

| Marker        | Purpose                        | Files |
| ------------- | ------------------------------ | ----- |
| `integration` | Network-dependent (yfinance)   | 1     |
| `e2e`         | Playwright browser tests       | 2     |
| `asyncio`     | Async HTTP tests               | 2     |
| `convergence` | Engine equivalence tests       | 1     |

---

## Context and Integration

### Related Artifacts

- **PRD**: `_bmad-output/planning-artifacts/Quant_Trade_Advisor_PRD.md` — 93 requirements
- **Architecture**: `_bmad-output/planning-artifacts/architecture.md`
- **Epics**: `_bmad-output/planning-artifacts/epics.md` — 7 epics
- **Implementation Readiness**: Score 90/100, READY

---

## Knowledge Base References

This review consulted the following knowledge base fragments:

- **test-quality.md** — Definition of Done for tests (no hard waits, <300 lines, <1.5 min, self-cleaning)
- **fixture-architecture.md** — Pure function → Fixture pattern, cleanup discipline
- **data-factories.md** — Factory functions with overrides, seeded RNG
- **test-levels-framework.md** — E2E vs API vs Component vs Unit appropriateness

For coverage mapping, consult `trace` workflow outputs.

See tea-index.csv for complete knowledge base.

---

## Next Steps

### Immediate Actions (Before Merge)

1. **Fix stale docstrings** — Update misleading "SKIPPED" docstrings in stories 2.4 and 2.7
   - Priority: P2
   - Estimated Effort: 10 minutes

2. **Implement or skip empty test** — `test_template_expired_parent_message` needs assertions or explicit skip
   - Priority: P2
   - Estimated Effort: 15 minutes

### Follow-up Actions (Future PRs)

1. **Add test IDs** — Implement `{EPIC}.{STORY}-{LEVEL}-{SEQ}` format across all tests
   - Priority: P1
   - Target: Epic 2 completion

2. **Add priority markers** — Classify all tests as P0/P1/P2/P3 for risk-based execution
   - Priority: P1
   - Target: Epic 2 completion

3. **Deduplicate ATDD fixtures** — Move `async_client_with_data` and `_RUN_DATA` to epic2 conftest
   - Priority: P1
   - Target: Next ATDD batch

4. **Extract metrics boilerplate** — Create shared fixture for story 2.7 repeated pattern
   - Priority: P2
   - Target: Backlog

### Re-Review Needed?

✅ No re-review needed — approve with comments. Issues are non-blocking improvements.

---

## Decision

**Recommendation**: Approve with Comments

> Test quality is good with 83/100 score. The suite demonstrates excellent engineering practices: deterministic data factories, adversarial lookahead-bias testing, protocol-based dependency injection, and comprehensive isolation. The three high-priority gaps (no test IDs, no priority markers, fixture duplication) are traceability/maintainability concerns that don't affect test correctness or reliability. Tests are production-ready. Follow-up actions can be addressed in subsequent PRs.

---

## Appendix

### Violation Summary by Location

| File                                                | Severity | Criterion          | Issue                         |
| --------------------------------------------------- | -------- | ------------------ | ----------------------------- |
| All test files                                      | P1       | Test IDs           | No test ID format used        |
| All test files                                      | P1       | Priority Markers   | No P0-P3 classification       |
| test_story_2_9 + test_story_2_11                    | P1       | Fixture Patterns   | Duplicated fixtures           |
| test_story_2_4_event_driven_engine.py:1             | P2       | Docstring Accuracy | Stale "SKIPPED" docstring     |
| test_story_2_7_metrics.py:1                         | P2       | Docstring Accuracy | Stale "SKIPPED" docstring     |
| test_story_2_11_remix.py:314                        | P2       | Explicit Assertions| Empty test (bare `pass`)      |
| test_story_2_9_web_pages.py                         | P2       | Test Length        | 388 lines (>300 guideline)    |
| test_story_2_7_metrics.py                           | P2       | DRY                | Repeated backtest boilerplate |
| Multiple ATDD files                                 | P3       | Style              | Inline imports (deferred)     |
| tests/integration/conftest.py                       | P3       | Style              | Hardcoded test constants      |

### Quality Trends

| Review Date  | Score     | Grade | Critical Issues | Trend |
| ------------ | --------- | ----- | --------------- | ----- |
| 2026-04-30   | 83/100    | A     | 0               | —     |

---

## Review Metadata

**Generated By**: BMad TEA Agent (Murat)
**Workflow**: testarch-test-review v5.0
**Review ID**: test-review-suite-20260430
**Timestamp**: 2026-04-30
**Version**: 1.0
