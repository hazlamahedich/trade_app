# Deferred Work

## Deferred from: code review of 4-4-oos-equity-curve-stitching-efficiency-ratio (2026-05-03)

- Near-zero `is_return` produces astronomically misleading WFE — `compute_wfe(0.05, 1e-15) = 5e13` classified "healthy". Guard with epsilon threshold. [stitch.py:43-46] — extreme edge case not triggered in normal walk-forward workflows where IS returns are meaningful percentages
- Timezone mismatch between `stitched_equity` index and `ohlcv` index — silent empty baseline. [stitch.py:94-95] — project convention is tz-naive DatetimeIndex throughout; tz-aware would be a broader project-level fix
- Zero OHLCV price → inf baseline — `pct_change` produces inf, baseline becomes meaningless. [stitch.py:101-102] — zero prices indicate data quality issues handled upstream in data layer
- `WFEThresholds` not validated — negative/inverted thresholds accepted. [stitch.py:16-18] — thresholds are config-level; validation belongs in config validation layer (pydantic), not in the dataclass itself
