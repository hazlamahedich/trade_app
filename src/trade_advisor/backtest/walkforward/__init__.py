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

__all__ = [
    "DataBoundary",
    "OptimizationConfig",
    "OptimizationResult",
    "PruningConfig",
    "TrialResult",
    "WalkForwardConfig",
    "WalkForwardError",
    "WalkForwardResult",
    "WindowResult",
    "async_run_walkforward",
    "optimize_is_window",
    "walk_forward",
]
