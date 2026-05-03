"""Walk-forward validation engine — public API re-exports."""

from __future__ import annotations

from trade_advisor.backtest.walkforward.async_runner import async_run_walkforward
from trade_advisor.backtest.walkforward.engine import (
    DataBoundary,
    WalkForwardConfig,
    WalkForwardError,
    WalkForwardResult,
    WindowResult,
    walk_forward,
)
from trade_advisor.backtest.walkforward.optimize import (
    OptimizationConfig,
    OptimizationResult,
    PruningConfig,
    TrialResult,
    optimize_is_window,
)
from trade_advisor.backtest.walkforward.stitch import (
    StitchedOOSResult,
    WFEThresholds,
    build_stitched_result,
    compute_expected_value,
    compute_oos_baseline,
    compute_wfe,
    compute_wfe_from_result,
    stitch_oos_equity,
    wfe_status,
)

__all__ = [
    "DataBoundary",
    "OptimizationConfig",
    "OptimizationResult",
    "PruningConfig",
    "StitchedOOSResult",
    "TrialResult",
    "WFEThresholds",
    "WalkForwardConfig",
    "WalkForwardError",
    "WalkForwardResult",
    "WindowResult",
    "async_run_walkforward",
    "build_stitched_result",
    "compute_expected_value",
    "compute_oos_baseline",
    "compute_wfe",
    "compute_wfe_from_result",
    "stitch_oos_equity",
    "walk_forward",
    "wfe_status",
    "_extract_active_bar_returns",
]
