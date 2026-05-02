---
stepsCompleted:
  - step-01-preflight-and-context
  - step-02-generation-mode
  - step-03-test-strategy
  - step-04-generate-tests
  - step-04c-aggregate
lastStep: step-04c-aggregate
lastSaved: "2026-05-02"
storyId: "4"
storyKey: "epic4"
storyFile: "_bmad-output/planning-artifacts/epics.md#epic-4"
atddChecklistPath: "tests/atdd/epic4/atdd-checklist-epic4.md"
generatedTestFiles:
  - tests/atdd/epic4/__init__.py
  - tests/atdd/epic4/conftest.py
  - tests/atdd/epic4/test_story_4_1_walkforward_engine.py
  - tests/atdd/epic4/test_story_4_2_hyperparameter_search.py
  - tests/atdd/epic4/test_story_4_3_oos_frozen_params.py
  - tests/atdd/epic4/test_story_4_4_oos_stitching_efficiency.py
  - tests/atdd/epic4/test_story_4_5_deflated_sharpe.py
  - tests/atdd/epic4/test_story_4_6_wf_results_web.py
inputDocuments:
  - "_bmad-output/planning-artifacts/epics.md"
  - "_bmad-output/planning-artifacts/architecture.md"
  - "src/trade_advisor/backtest/engine.py"
  - "src/trade_advisor/backtest/protocols.py"
  - "src/trade_advisor/core/config.py"
  - "tests/conftest.py"
  - "tests/atdd/epic3/conftest.py"
  - "tests/atdd/epic3/test_story_3_1_experiment_list.py"
---

# ATDD Checklist — Epic 4: Walk-Forward Validation & Honest Evaluation

## Story Summary

| Story | Description | Tests | P0 | P1 | P2 | Status |
|-------|-------------|-------|----|----|-----|--------|
| 4.1 | Walk-Forward Engine (Rolling & Anchored) | 11 | 4 | 5 | 2 | RED |
| 4.2 | IS Hyperparameter Search with Pruning | 7 | 3 | 2 | 2 | RED |
| 4.3 | OOS Evaluation with Frozen Params | 6 | 3 | 2 | 1 | RED |
| 4.4 | OOS Stitching & Efficiency Ratio | 9 | 5 | 2 | 2 | RED |
| 4.5 | Deflated Sharpe Ratio | 9 | 4 | 2 | 3 | RED |
| 4.6 | WF Results Web Page | 7 | 3 | 2 | 2 | RED |
| **Total** | | **49** | **22** | **15** | **12** | |

## Stack Detection

- **Detected**: `backend` (pyproject.toml, Python 3.12+, no frontend framework deps)
- **Test framework**: pytest + pytest-asyncio
- **Generation mode**: AI generation (backend — no browser recording needed)

## FR Coverage

| FR | Story | Test IDs |
|----|-------|----------|
| WFO-1 | 4.1 | 4.1-ATDD-001, 4.1-ATDD-002, 4.1-ATDD-003, 4.1-ATDD-005 |
| WFO-2 | 4.2 | 4.2-ATDD-001, 4.2-ATDD-002, 4.2-ATDD-003 |
| WFO-3 | 4.3 | 4.3-ATDD-001, 4.3-ATDD-002, 4.3-ATDD-003 |
| WFO-4 | 4.4 | 4.4-ATDD-001 |
| WFO-5 | 4.4 | 4.4-ATDD-002, 4.4-ATDD-003, 4.4-ATDD-004, 4.4-ATDD-005 |
| WFO-6 | 4.5 | 4.5-ATDD-001, 4.5-ATDD-002, 4.5-ATDD-003 |
| BT-8 | 4.4 | 4.4-ATDD-007, 4.4-ATDD-008 |

## NFR Coverage

| NFR | Test IDs |
|-----|----------|
| NFR-R1c (deterministic WF) | 4.1-ATDD-004 |
| NFR-P2 (WF perf < 15min) | (performance test — separate benchmark) |

## TDD Red Phase Confirmation

- [x] All tests import from **non-existent** modules (`trade_advisor.backtest.walkforward.*`)
- [x] All tests assert EXPECTED behavior with Given/When/Then structure
- [x] Tests will FAIL (ImportError) until implementation exists
- [x] No test.skip() — tests are active red-phase assertions
- [x] P0 tests cover critical acceptance criteria
- [x] Edge cases covered in P2 tests

## Implementation Modules Required

| Module | Purpose |
|--------|---------|
| `backtest/walkforward/__init__.py` | Package init |
| `backtest/walkforward/engine.py` | `WalkForwardEngine`, `WalkForwardError`, `DataBoundary` |
| `backtest/walkforward/optimize.py` | `HyperparamOptimizer` |
| `backtest/walkforward/stitch.py` | `stitch_oos_equity`, `compute_wfe`, `wfe_status`, `compute_expected_value` |
| `backtest/walkforward/deflated.py` | `compute_deflated_sharpe`, `count_independent_trials` |
| Web routes for `/walkforward` and `/api/walkforward` | WF Results page |
