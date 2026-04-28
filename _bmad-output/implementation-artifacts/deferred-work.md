# Deferred Work

## Deferred from: code review of 1-9-composition-root-strategy-protocol.md (2026-04-27)

- `bootstrap()` called per invocation in `cli.py:87` and `ui/app.py:122` — not a bug (CLI runs once per process, Streamlit reruns whole script). Consider module-level caching if it becomes a performance concern.
- `_synthetic_ohlcv(n=0)` raises `IndexError` in `tests/helpers.py:24` — no caller passes n=0. Add guard if parametric tests need it.
- `assert_no_lookahead_bias` vacuous pass when `warmup_period >= cutoff` in `tests/helpers.py:98` — all current strategies have warmup < 200. Raise cutoff or add assertion for non-trivial signals before cutoff.
- `_scan_imports` regex in `tests/test_import_contracts.py:17` matches commented-out imports and docstrings — use AST-based parsing if false positives appear.
- `SignalBatch` with empty `signals=[]` skips strategy_name consistency check in `strategies/schemas.py:51` — empty batch is semantically neutral. Add validation if downstream code depends on batch.strategy_name.
- AC-14 advisory: `SmaCross.generate_signals` returns `int8` dtype while Protocol specifies `pd.Series[float]` — Phase 1 acceptable, reconcile dtype when ML strategies (SE-2) introduce continuous signals.

## Deferred from: code review #1 of 1-9-composition-root-strategy-protocol.md (2026-04-27)

- W1: `SignalModel.confidence` could be `Optional[float]` constrained to `[0.0, 1.0]` — low risk; add when ML strategies need it
- W2: `SignalBatch.strategy_name` could use `Literal` type for compile-time checking — premature with only one strategy
- W3: `AppContainer` could expose `.config` as read-only via `MappingProxyType` — over-engineering for current needs
- W4: `interface.py` Protocol docs could include Sphinx-style `:param:` annotations — cosmetic; documentation sprint
- W5: Add Hypothesis property-based test for arbitrary signal series — add in test-hardening pass

## Deferred from: code review of 1-10-htmx-preact-bridge-proof-of-concept.md (2026-04-28)

- Hardcoded port 8199 with no conflict detection [conftest_bridge.py:26] — pre-existing pattern; consider dynamic port allocation
- urlopen response never closed [conftest_bridge.py:14] — pre-existing; GC handles it on CPython but could exhaust FDs under load
- Fragile parents[3] path resolution [test_event_contract.py:6] — path depends on project structure; breaks if test file is moved
- E2E tests use hardcoded wait_for_timeout — flaky on slow CI; consider polling on DOM conditions instead
- Leak detection tolerance +2 masks real leaks [test_bridge_lifecycle.py:68] — tolerance added for flakiness; tighten after CI stability proven
- Watch mode skips bundle size enforcement [esbuild.config.mjs:49-66] — dev-only concern; CI catches budget violations
- Module-level initBridge() fails in non-browser env [bridge.ts:6] — only loaded via browser script tag; blocks future Node.js testability
- SVG elements with data-preact-mount [bridgeUtils.ts:47] — no SVG islands in current scope; add instanceof check if needed later

## Deferred from: code review of 1-11-schema-migration-framework.md (2026-04-28)

- Checksums stored for additive migrations despite spec saying "destructive only" [migrate.py:351] — additive checksums are inert (never verified); harmless deferral
- No enforcement of rollback instructions in manual SQL files [migrate.py:330-345] — README documents the requirement but code doesn't validate; pre-existing design choice
- `default_factory` fields get no SQL DEFAULT [migrate.py:177-188] — Python factories can't be expressed as SQL DEFAULT; could warn but no model uses it yet
- Removing model from `SCHEMA_MODELS` leaves orphaned table with no warning [migrate.py:422-434] — schema validation only checks for missing, not orphaned; deferred until a story needs it
- Gap detection test bypasses public API [test_migrate.py:391-399] — calls `_detect_gaps()` directly; minor test quality issue
