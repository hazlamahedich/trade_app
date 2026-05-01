# Deferred Work

## Deferred from: code review of 3-3-comparebridge-split-panel.md (2026-05-01)

- f-string in SQL column list (`compare.py:100`) — `_COMPARE_COLS` is a module-level constant injected via f-string. Currently safe since it's hardcoded, but the pattern bypasses parameterized-query guarantees. Consider using a plain string constant instead.

## Deferred from: re-review round 2 of 3-3-comparebridge-split-panel.md (2026-05-01)

- **P2: `db: Any` + private method access** — Every function takes `db: Any` and calls `db._execute_read()`. No protocol/ABC for type safety. Refactor to a typed `Protocol` with `execute_read()` when time permits.
- **P2: `chart_overlay: None` is a permanent lie** — `CompareResult.chart_overlay` is always `None`. Remove the field entirely and add it back when chart overlay is implemented (YAGNI).
- **P2: `_compute_parameter_diff_list` drops added/removed keys** — Only shared keys are compared. Keys unique to one config are silently ignored. Consider reporting `config_a ^ config_b` as "added"/"removed" parameter changes.
- **P2: `_determine_order` silently reorders** — Caller passes `(run_a, run_b)` but function reorders by creation time. Document the convention prominently in the docstring so callers understand baseline/challenger assignment.
