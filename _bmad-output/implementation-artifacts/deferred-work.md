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

## Deferred from: code review of 2-1-built-in-sma-crossover-strategy.md (2026-04-28)

- `test_nan_close_produces_flat_signals` name promises "flat" but only asserts no NaN leakage — test is still useful for NaN-leak detection; consider renaming to `test_nan_close_no_nan_leakage` or adding explicit flatness assertion
- `to_signal_batch` uses `datetime.now(UTC)` for `generated_at` — wall-clock time, not data time. Two calls on same data produce different `generated_at`. Consider using last OHLCV timestamp for reproducibility
- `generate_signals` raises raw `KeyError` if DataFrame has neither `close` nor `adj_close` — add descriptive error message for better DX

## Deferred from: re-review of 2-1-built-in-sma-crossover-strategy.md (2026-04-28)

- Empty DataFrame path in `generate_signals` loses original index type — `pd.Series(dtype="float64")` returns RangeIndex, causing `to_signal_batch` TypeError on empty DatetimeIndex input. Fix: `pd.Series(dtype="float64", index=ohlcv.index)` [sma_cross.py:55]
- tz-naive DatetimeIndex passes DatetimeIndex guard but crashes in Pydantic `AwareDatetime` validation — strengthen guard to check `signals.index.tz is not None` [sma_cross.py:83]
- NaN in close column silently masked as flat signal — no way to distinguish "flat by strategy" from "flat due to missing data". Pre-existing; revisit if risk/position-sizing layer needs the distinction

## Deferred from: code review of 2-2-position-sizing-methods.md (2026-04-28)

- `SizingConfig.method` is unconstrained `str` — no Literal type or discriminated union enforcement. `SizingConfig(method="bogus")` is valid. Consider `Literal` type when integrating with strategy config in Story 2.3
- `FixedFractionalConfig` Pydantic model rejects `fraction>1` (Field le=1) while raw `fixed_fractional()` silently clamps to `MAX_FRACTION`. Two code paths produce inconsistent behavior for same logical input. Revisit when engine integration adds the canonical call path
- `SizingConfig` base class has no abstract `compute()` method — no type-level guarantee that a SizingConfig instance supports compute(). Add Protocol or abstract method when polymorphic dispatch is needed in Story 2.3

## Deferred from: code review of 2-3-vectorized-backtest-engine.md (2026-04-29)

- Zero/negative prices cause `inf` in equity curve — `pct_change()` produces `inf` for zero prices; `fillna` doesn't catch `inf`. Pre-existing issue from old engine. [vectorized.py:113]
- Signal length mismatch silently truncated via `reindex` — short signals padded with 0.0, long signals truncated. Pre-existing from old engine. [vectorized.py:104]
- `sizing` parameter accepted but never used — by design per spec ("establish parameter slot, deferred"). [vectorized.py:52]
- `@runtime_checkable` only checks method names, not signatures — known Python limitation. [protocols.py:21]
- Duplicate timestamps cause `reindex` misalignment — no uniqueness check on timestamps. Pre-existing. [vectorized.py:100-104]
- `delta` first-bar cost semantics — charges entry cost on first bar. Carried from old engine. [vectorized.py:116]
- `type: ignore[call-arg]` on BacktestConfig() — pre-existing suppress. [vectorized.py:80]
- `_extract_trades` silently drops last unclosed trade — if position is open at end of series, no post-loop flush appends it. Pre-existing from old engine. Suggest fixing in Story 2.4 when trade extraction gets refactored. [engine.py:92-121]

## Deferred from: code review of 2-6-transaction-cost-engine.md (2026-04-29)

- T-1 convention is static constant, not true per-bar T-1 — effective_cost_pct computed once using initial_cash. Acknowledged in spec Phase 1 limitation. ATR-varying slippage deferred to convergence-hardening story. [_equity.py:91]
- apply_costs notional (entry_price × weight) diverges from equity curve's effective_cost_pct — post-hoc cost attribution uses per-trade notional while equity uses constant scalar. Intentional design split per spec.
- No forced-flat guard in vectorized equity when equity hits zero — positions continue after equity = 0, creating silent inconsistency between equity/returns/positions series. Pre-existing from Story 2.3. [_equity.py:101]
- Bar-0 cost drag vs equity inconsistency in event_driven stop-loss path — ret_arr[0] can be negative from cost_drag while equity_arr[0] = initial_cash. Pre-existing from Story 2.4. [event_driven.py:265]
