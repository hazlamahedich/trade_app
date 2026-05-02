# Deferred Work

## Deferred from: code review of 3-3-comparebridge-split-panel.md (2026-05-01)

- f-string in SQL column list (`compare.py:100`) — `_COMPARE_COLS` is a module-level constant injected via f-string. Currently safe since it's hardcoded, but the pattern bypasses parameterized-query guarantees. Consider using a plain string constant instead.

## Deferred from: re-review round 2 of 3-3-comparebridge-split-panel.md (2026-05-01)

- **P2: `db: Any` + private method access** — Every function takes `db: Any` and calls `db._execute_read()`. No protocol/ABC for type safety. Refactor to a typed `Protocol` with `execute_read()` when time permits.
- **P2: `chart_overlay: None` is a permanent lie** — `CompareResult.chart_overlay` is always `None`. Remove the field entirely and add it back when chart overlay is implemented (YAGNI).
- **P2: `_compute_parameter_diff_list` drops added/removed keys** — Only shared keys are compared. Keys unique to one config are silently ignored. Consider reporting `config_a ^ config_b` as "added"/"removed" parameter changes.
- **P2: `_determine_order` silently reorders** — Caller passes `(run_a, run_b)` but function reorders by creation time. Document the convention prominently in the docstring so callers understand baseline/challenger assignment.

## Deferred from: code review of 3-4-run-retrieval-full-reproduction.md (2026-05-02)

- **Stub data freshness check** — `check_data_freshness()` compares stored fingerprint against itself. Only detects `"stale_fingerprint_value"` magic string. Real data changes are never flagged. Known limitation documented with `fingerprint_method="stub_self_compare"`. Target: Epic 4+.
- **Transaction atomicity for reproduce_run** — INSERT into experiments and equity copy are two separate operations. If equity INSERT fails, orphaned child run with `status='completed'` exists. `_execute_many` has its own BEGIN/COMMIT, preventing outer transaction wrapping. Target: Epic 4+ (requires refactoring `_execute_many` or adding atomic write path).
- **DatabaseManager write lock bypass** — `reproduce_run()` uses `db._execute()` directly, bypassing `_rw_lock`. Safe for single-user MVP. DuckDB connections are NOT thread-safe — concurrent writes cause segfault. TODO comments added in `reproduction.py:188-189`. Target: Epic 4+ (add `write_sync()` or route through repo with lock).
- **f-string SQL column list** — `_REPRODUCTION_COLS` injected via f-string. Constant is safe but pattern is fragile if refactored. Same issue as `compare.py` (deferred from Story 3.3 review).
