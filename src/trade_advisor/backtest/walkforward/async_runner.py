"""Async walk-forward runner with per-window progress callbacks.

Wraps the sync walk_forward engine to provide:
- Per-window progress via on_progress callback
- Cooperative cancellation via cancel_check callable
- asyncio.to_thread() bridge for each window (non-blocking)
"""

from __future__ import annotations

import asyncio
import math
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from trade_advisor.backtest.walkforward.deflated import (
    TrialStats,
    compute_trial_stats_online,
)
from trade_advisor.backtest.walkforward.engine import (
    WalkForwardConfig,
    WalkForwardError,
    WalkForwardResult,
    WindowResult,
    _build_strategy_factory,
    _generate_anchored_boundaries,
    _generate_rolling_boundaries,
    _resolve_strategy,
    _run_single_window,
)
from trade_advisor.backtest.walkforward.optimize import optimize_is_window
from trade_advisor.infra.seed import SeedManager
from trade_advisor.web.sse import WalkForwardProgressEvent


async def async_run_walkforward(
    ohlcv: pd.DataFrame,
    config: WalkForwardConfig,
    *,
    on_progress: Callable[[WalkForwardProgressEvent], Any] | None = None,
    cancel_check: Callable[[], bool] | None = None,
    run_id: str = "",
) -> WalkForwardResult:
    if config.frozen_params_mode:
        raise WalkForwardError(
            "frozen_params_mode requires sequential execution — use sync walk_forward()"
        )

    data_len = len(ohlcv)
    min_required = config.is_bars + config.gap_bars + config.oos_bars
    if data_len < min_required:
        raise WalkForwardError(f"Need >= {min_required} bars, got {data_len}")

    strategy = await asyncio.to_thread(_resolve_strategy, config)
    strategy_factory = _build_strategy_factory(config.strategy_type)

    if config.mode == "rolling":
        boundaries = _generate_rolling_boundaries(
            data_len, config.is_bars, config.oos_bars, config.gap_bars
        )
    else:
        boundaries = _generate_anchored_boundaries(
            data_len, config.is_bars, config.oos_bars, config.gap_bars
        )

    total_windows = len(boundaries)
    windows: list[WindowResult] = []
    cumulative_stats = TrialStats()

    for window_idx, boundary in enumerate(boundaries):
        if cancel_check and cancel_check():
            break

        opt_result = None
        current_strategy = strategy
        if config.optimization:
            is_slice = ohlcv.iloc[boundary.is_start : boundary.is_end].copy()
            opt_result = await asyncio.to_thread(
                optimize_is_window,
                is_slice,
                config.optimization,
                strategy_factory,
                config.backtest,
                seed=SeedManager().get_seed(config.seed, "window", window_idx),
            )
            if opt_result.best_params:
                current_strategy = strategy_factory(opt_result.best_params)

            # Story 4.5: Accumulate trial stats
            if config.optimization.metric == "sharpe":
                window_stats = compute_trial_stats_online(
                    opt_result.n_trials, (r.metric for r in opt_result.all_results)
                )
                cumulative_stats.merge(window_stats)

        window_result = await asyncio.to_thread(
            _run_single_window,
            current_strategy,
            ohlcv,
            boundary,
            config,
            optimization_result=opt_result,
        )
        windows.append(window_result)

        if on_progress is not None:
            oos_sharpe = window_result.oos_sharpe
            oos_return = window_result.oos_return
            ts_index = window_result.is_segment.index
            if len(ts_index) > 0 and hasattr(ts_index[-1], "isoformat"):
                ts_str = ts_index[-1].isoformat()
            else:
                ts_str = datetime.now(UTC).isoformat()
            event = WalkForwardProgressEvent(
                run_id=run_id,
                timestamp=ts_str,
                window_idx=window_idx,
                total_windows=total_windows,
                is_sharpe=window_result.is_sharpe,
                oos_sharpe=oos_sharpe if not math.isnan(oos_sharpe) else float("nan"),
                oos_return=oos_return if not math.isnan(oos_return) else float("nan"),
                status=window_result.status,
            )
            on_progress(event)

        if cancel_check and cancel_check():
            break

    last_boundary = windows[-1].boundary if windows else (boundaries[-1] if boundaries else None)
    discarded_bars = data_len - last_boundary.oos_end if last_boundary else data_len

    return WalkForwardResult(
        n_windows=len(windows),
        windows=windows,
        config=config,
        discarded_bars=discarded_bars,
        total_trials=cumulative_stats.n_trials,
        sr_variance=cumulative_stats.variance,
    )
