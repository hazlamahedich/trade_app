# Deferred Work

## Deferred from: code review of 4-4-oos-equity-curve-stitching-efficiency-ratio (2026-05-03)

All items from this review have been resolved:

- ~~Near-zero `is_return` produces astronomically misleading WFE~~ → Fixed: `compute_wfe()` guards with `abs(is_return) < 1e-6` returning 0.0 [stitch.py:114]
- ~~Timezone mismatch between `stitched_equity` index and `ohlcv` index~~ → Fixed: `_to_naive()` helper normalizes both indices before comparison [stitch.py:243-249]
- ~~Zero OHLCV price → inf baseline~~ → Fixed: `replace(0, np.nan).ffill().bfill()` before `pct_change` [stitch.py:256]
- ~~`WFEThresholds` not validated~~ → Fixed: `__post_init__` validates ordering + `dsr_significance` range [stitch.py:28-38]

## Deferred from: code review of 4-5-deflated-sharpe-ratio (2026-05-03)

All items from this review have been resolved:

- ~~Welford's algorithm duplication~~ → Not duplicated: `TrialStats` defined once in `deflated.py`, imported by `engine.py` and `async_runner.py`
- ~~Missing T>=250 enforcement in DSR~~ → Fixed: enforced in `compute_dsr()` [deflated.py:127-130]
- ~~Hardcoded 0.95 significance threshold~~ → Fixed: now configurable via `WFEThresholds.dsr_significance` [stitch.py:31]
- ~~DSR for non-Sharpe optimization metrics~~ → Design decision documented: Sharpe-only gate at [stitch.py:336-339]
- ~~Daily vs total Sharpe scaling ambiguity~~ → Design decision documented: de-annualize sr_variance to match daily Sharpe [stitch.py:346-347]

## Deferred from: Epic 3 reproduction (2026-04-28)

- ~~`stale_fingerprint_value` marker~~ → Removed. Real fingerprint recomputation via `_recompute_parquet_fingerprint` is used for all checks [reproduction.py:130-140]
