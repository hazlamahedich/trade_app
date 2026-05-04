"""Walk-forward validation engine — synchronous core (rolling & anchored modes).

This module implements the sync walk-forward engine that partitions OHLCV data
into sequential IS/OOS windows, runs backtests per window, and returns
structured results with full determinism and data-leakage prevention.

Architecture decisions (from adversarial review):
- Engine is sync, not async (async bridge belongs in Story 4.1b).
- Internals operate in float64 (Decimal convention at storage boundary only).
- WalkForwardConfig is a typed pydantic BaseModel composing BacktestConfig.
- DataBoundary is a frozen dataclass with invariant validation.
- IS→OOS transition gap: 1 bar (prevents serial correlation leakage).
- Empty OOS window → INCONCLUSIVE marker, not crash.
- Frozen params mode (Story 4.3): OOS uses prior window's best_params.
"""

from __future__ import annotations

import copy
import logging
import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, Field, model_validator

from trade_advisor.backtest.engine import BacktestResult, run_backtest
from trade_advisor.backtest.walkforward.deflated import compute_trial_stats_online
from trade_advisor.backtest.walkforward.optimize import (
    OptimizationConfig,
    OptimizationResult,
    optimize_is_window,
)
from trade_advisor.config import BacktestConfig
from trade_advisor.infra.seed import SeedManager

if False:
    from trade_advisor.strategies.interface import Strategy

logger = logging.getLogger(__name__)


class WalkForwardError(Exception):
    """Raised when walk-forward preconditions are violated."""


class WalkForwardConfig(BaseModel):
    mode: Literal["rolling", "anchored"]
    is_bars: int = Field(..., gt=0)
    oos_bars: int = Field(..., gt=0)
    gap_bars: int = Field(1, ge=0)
    seed: int = Field(42, ge=0)
    strategy_type: str = "sma"
    strategy_params: dict[str, Any] = Field(default_factory=dict)
    backtest: BacktestConfig = BacktestConfig()  # type: ignore[call-arg]
    optimization: OptimizationConfig | None = None
    frozen_params_mode: bool = False

    @model_validator(mode="after")
    def _validate_frozen_params(self) -> WalkForwardConfig:
        if self.frozen_params_mode and self.optimization is None:
            raise WalkForwardError("frozen_params_mode requires optimization to be configured")
        return self


@dataclass(frozen=True)
class DataBoundary:
    is_start: int
    is_end: int
    oos_start: int
    oos_end: int

    def __post_init__(self) -> None:
        if self.is_start < 0:
            raise WalkForwardError(f"is_start must be >= 0, got {self.is_start}")
        if self.is_end <= self.is_start:
            raise WalkForwardError(
                f"is_end must be > is_start, got is_end={self.is_end} is_start={self.is_start}"
            )
        if self.oos_start < self.is_end:
            raise WalkForwardError(
                f"oos_start must be >= is_end ({self.is_end}), got oos_start={self.oos_start}"
            )
        if self.oos_end <= self.oos_start:
            raise WalkForwardError(
                f"oos_end must be > oos_start, got oos_end={self.oos_end} oos_start={self.oos_start}"
            )


@dataclass
class WindowResult:
    boundary: DataBoundary
    is_segment: pd.DataFrame
    oos_segment: pd.DataFrame
    is_equity: pd.Series
    oos_equity: pd.Series
    is_sharpe: float
    oos_sharpe: float
    is_return: float
    oos_return: float
    status: Literal["OK", "INCONCLUSIVE", "DEGRADED"] = "OK"
    optimization_result: OptimizationResult | None = None
    frozen_oos_params: dict[str, Any] | None = None
    frozen_params_source_window: int | None = None
    frozen_fallback: bool = False


@dataclass
class WalkForwardResult:
    n_windows: int
    windows: list[WindowResult]
    config: WalkForwardConfig
    discarded_bars: int = 0
    baseline_params: dict[str, Any] | None = None
    total_trials: int = 0
    sr_variance: float = 0.0


def _generate_rolling_boundaries(
    data_len: int,
    is_bars: int,
    oos_bars: int,
    gap_bars: int,
) -> list[DataBoundary]:
    stride = is_bars + gap_bars + oos_bars
    boundaries: list[DataBoundary] = []
    offset = 0
    while offset + stride <= data_len:
        boundaries.append(
            DataBoundary(
                is_start=offset,
                is_end=offset + is_bars,
                oos_start=offset + is_bars + gap_bars,
                oos_end=offset + is_bars + gap_bars + oos_bars,
            )
        )
        offset += stride
    return boundaries


def _generate_anchored_boundaries(
    data_len: int,
    is_bars: int,
    oos_bars: int,
    gap_bars: int,
) -> list[DataBoundary]:
    stride = oos_bars + gap_bars
    boundaries: list[DataBoundary] = []
    is_end = is_bars
    while is_end + gap_bars + oos_bars <= data_len:
        boundaries.append(
            DataBoundary(
                is_start=0,
                is_end=is_end,
                oos_start=is_end + gap_bars,
                oos_end=is_end + gap_bars + oos_bars,
            )
        )
        is_end += stride
    return boundaries


def _resolve_strategy(config: WalkForwardConfig) -> Strategy:
    if config.strategy_type == "sma":
        from trade_advisor.strategies.sma_cross import SmaCross

        try:
            return SmaCross(**config.strategy_params)
        except (TypeError, ValueError) as exc:
            raise WalkForwardError(
                f"Invalid strategy params for {config.strategy_type!r}: {exc}"
            ) from exc
    raise WalkForwardError(f"Unknown strategy_type: {config.strategy_type!r}")


def _build_strategy_factory(strategy_type: str) -> Callable[[dict[str, Any]], Strategy]:
    if strategy_type == "sma":
        from trade_advisor.strategies.sma_cross import SmaCross

        return lambda params: SmaCross(**params)
    raise WalkForwardError(f"Unknown strategy_type: {strategy_type!r}")


def _run_single_window(
    strategy: Strategy,
    ohlcv: pd.DataFrame,
    boundary: DataBoundary,
    config: WalkForwardConfig,
    optimization_result: OptimizationResult | None = None,
    oos_strategy: Strategy | None = None,
    frozen_oos_params: dict[str, Any] | None = None,
    frozen_params_source_window: int | None = None,
    is_fallback: bool = False,
) -> WindowResult:
    if is_fallback:
        logger.warning(
            "ta:walkforward:frozen_fallback window_idx=%s boundary=%s",
            frozen_params_source_window,
            boundary,
        )
        is_slice = ohlcv.iloc[boundary.is_start : boundary.is_end].copy()
        oos_slice = ohlcv.iloc[boundary.oos_start : boundary.oos_end].copy()
        actual_oos_strategy = oos_strategy if oos_strategy is not None else strategy
        oos_warmup = getattr(actual_oos_strategy, "warmup_period", 0)
        oos_len = boundary.oos_end - boundary.oos_start

        if oos_len < oos_warmup:
            return WindowResult(
                boundary=boundary,
                is_segment=is_slice,
                oos_segment=oos_slice,
                is_equity=pd.Series(dtype="float64", name="equity"),
                oos_equity=pd.Series(dtype="float64", name="equity"),
                is_sharpe=float("nan"),
                oos_sharpe=float("nan"),
                is_return=float("nan"),
                oos_return=float("nan"),
                status="INCONCLUSIVE",
                optimization_result=optimization_result,
                frozen_oos_params=frozen_oos_params,
                frozen_params_source_window=frozen_params_source_window,
                frozen_fallback=True,
            )

        if oos_warmup > 0:
            warmup_start = max(boundary.oos_start - oos_warmup, 0)
            extended_oos = ohlcv.iloc[warmup_start : boundary.oos_end].copy()
            extended_signals = actual_oos_strategy.generate_signals(extended_oos)
            n_oos = boundary.oos_end - boundary.oos_start
            oos_signals = extended_signals.iloc[-n_oos:].copy()
            oos_signals.index = oos_slice.index
        else:
            oos_signals = actual_oos_strategy.generate_signals(oos_slice)

        oos_bt = run_backtest(oos_slice, oos_signals, config.backtest)
        oos_sharpe, oos_return = _compute_metrics(oos_bt)

        if len(oos_bt.trades) == 0 or not _metrics_sane(oos_sharpe, oos_return):
            oos_sharpe = float("nan")
            oos_return = float("nan")
            fb_status: Literal["OK", "INCONCLUSIVE", "DEGRADED"] = "INCONCLUSIVE"
        else:
            fb_status = "DEGRADED"

        return WindowResult(
            boundary=boundary,
            is_segment=is_slice,
            oos_segment=oos_slice,
            is_equity=pd.Series(dtype="float64", name="equity"),
            oos_equity=oos_bt.equity,
            is_sharpe=float("nan"),
            oos_sharpe=oos_sharpe,
            is_return=float("nan"),
            oos_return=oos_return,
            status=fb_status,
            optimization_result=optimization_result,
            frozen_oos_params=frozen_oos_params,
            frozen_params_source_window=frozen_params_source_window,
            frozen_fallback=True,
        )

    actual_oos_strategy = oos_strategy if oos_strategy is not None else strategy

    oos_warmup = getattr(actual_oos_strategy, "warmup_period", 0)

    is_slice = ohlcv.iloc[boundary.is_start : boundary.is_end].copy()
    oos_slice = ohlcv.iloc[boundary.oos_start : boundary.oos_end].copy()

    is_signals = strategy.generate_signals(is_slice)

    oos_len = boundary.oos_end - boundary.oos_start
    if oos_len < oos_warmup:
        is_bt = run_backtest(is_slice, is_signals, config.backtest)
        is_sharpe, is_return = _compute_metrics(is_bt)
        return WindowResult(
            boundary=boundary,
            is_segment=is_slice,
            oos_segment=oos_slice,
            is_equity=is_bt.equity,
            oos_equity=pd.Series(dtype="float64", name="equity"),
            is_sharpe=is_sharpe,
            oos_sharpe=float("nan"),
            is_return=is_return,
            oos_return=float("nan"),
            status="INCONCLUSIVE",
            optimization_result=optimization_result,
            frozen_oos_params=frozen_oos_params,
            frozen_params_source_window=frozen_params_source_window,
        )

    if oos_warmup > 0:
        warmup_start = max(boundary.oos_start - oos_warmup, 0)
        extended_oos = ohlcv.iloc[warmup_start : boundary.oos_end].copy()
        extended_signals = actual_oos_strategy.generate_signals(extended_oos)
        n_oos = boundary.oos_end - boundary.oos_start
        oos_signals = extended_signals.iloc[-n_oos:].copy()
        oos_signals.index = oos_slice.index
    else:
        oos_signals = actual_oos_strategy.generate_signals(oos_slice)

    is_bt = run_backtest(is_slice, is_signals, config.backtest)
    oos_bt = run_backtest(oos_slice, oos_signals, config.backtest)

    is_sharpe, is_return = _compute_metrics(is_bt)
    oos_sharpe, oos_return = _compute_metrics(oos_bt)

    n_oos_trades = len(oos_bt.trades)
    if n_oos_trades == 0 or not _metrics_sane(oos_sharpe, oos_return):
        status: Literal["OK", "INCONCLUSIVE", "DEGRADED"] = "INCONCLUSIVE"
        oos_sharpe = float("nan")
        oos_return = float("nan")
    else:
        status = "OK"

    return WindowResult(
        boundary=boundary,
        is_segment=is_slice,
        oos_segment=oos_slice,
        is_equity=is_bt.equity,
        oos_equity=oos_bt.equity,
        is_sharpe=is_sharpe,
        oos_sharpe=oos_sharpe,
        is_return=is_return,
        oos_return=oos_return,
        status=status,
        optimization_result=optimization_result,
        frozen_oos_params=frozen_oos_params,
        frozen_params_source_window=frozen_params_source_window,
    )


def _compute_metrics(result: BacktestResult) -> tuple[float, float]:
    equity = result.equity
    if len(equity) < 2:
        return float("nan"), float("nan")
    if equity.iloc[0] == 0.0:
        return float("nan"), float("nan")
    total_return = float(equity.iloc[-1] / equity.iloc[0] - 1.0)
    rets = result.returns
    sharpe = 0.0 if rets.std() == 0.0 else float(rets.mean() / rets.std() * math.sqrt(252))
    return sharpe, total_return


_SANITY_SHARPE_RANGE = (-10.0, 100.0)
_SANITY_RETURN_RANGE = (-1.0, 10.0)


def _metrics_sane(sharpe: float, total_return: float) -> bool:
    return (
        math.isfinite(sharpe)
        and math.isfinite(total_return)
        and _SANITY_SHARPE_RANGE[0] <= sharpe <= _SANITY_SHARPE_RANGE[1]
        and _SANITY_RETURN_RANGE[0] <= total_return <= _SANITY_RETURN_RANGE[1]
    )


def walk_forward(
    ohlcv: pd.DataFrame,
    config: WalkForwardConfig,
) -> WalkForwardResult:
    """Synchronous walk-forward engine. Pure function — no side effects."""
    data_len = len(ohlcv)
    min_required = config.is_bars + config.gap_bars + config.oos_bars
    if data_len < min_required:
        raise WalkForwardError(f"Need >= {min_required} bars, got {data_len}")

    if config.mode == "rolling":
        boundaries = _generate_rolling_boundaries(
            data_len, config.is_bars, config.oos_bars, config.gap_bars
        )
    else:
        boundaries = _generate_anchored_boundaries(
            data_len, config.is_bars, config.oos_bars, config.gap_bars
        )

    windows: list[WindowResult] = []
    baseline_params: dict[str, Any] | None = None
    if config.frozen_params_mode:
        baseline_params = dict(config.strategy_params)

    prior_best_params: dict[str, Any] | None = None
    prior_source_window: int | None = None

    from trade_advisor.backtest.walkforward.deflated import TrialStats

    cumulative_stats = TrialStats()

    if config.optimization is not None:
        if not isinstance(config.optimization, OptimizationConfig):
            raise WalkForwardError(
                f"config.optimization must be OptimizationConfig, got {type(config.optimization).__name__}"
            )
        seed_mgr = SeedManager(global_seed=config.seed)
        strategy_factory = _build_strategy_factory(config.strategy_type)
    else:
        fallback_strategy = _resolve_strategy(config)

    for window_idx, boundary in enumerate(boundaries):
        opt_result: OptimizationResult | None = None
        oos_strategy: Strategy | None = None
        frozen_oos: dict[str, Any] | None = None
        frozen_source: int | None = None

        if config.frozen_params_mode:
            if not baseline_params:
                raise WalkForwardError("frozen_params_mode requires non-empty strategy_params")
            if prior_best_params is not None:
                oos_params: dict[str, Any] = copy.deepcopy(prior_best_params)
                source_window: int | None = prior_source_window
            else:
                oos_params = copy.deepcopy(baseline_params)
                source_window = None
            oos_strategy = strategy_factory(oos_params)
            frozen_oos = copy.deepcopy(oos_params)
            frozen_source = source_window

        if config.optimization is not None:
            is_slice = ohlcv.iloc[boundary.is_start : boundary.is_end].copy()
            window_seed = seed_mgr.derive_experiment_seed(f"wf_window_{window_idx}")
            try:
                opt_result = optimize_is_window(
                    is_slice,
                    config.optimization,
                    strategy_factory,
                    config.backtest,
                    seed=window_seed,
                )
            except Exception as exc:
                raise WalkForwardError(
                    f"Optimization failed for window {window_idx}: {exc}"
                ) from exc

            # Story 4.5: Accumulate trial stats for DSR (Welford's algorithm)
            # Consensus: Only accumulate if metric is 'sharpe' to avoid poisoning sr_variance.
            if opt_result and config.optimization.metric == "sharpe":
                window_stats = compute_trial_stats_online(
                    opt_result.n_trials, (r.metric for r in opt_result.all_results)
                )
                cumulative_stats.merge(window_stats)

            if opt_result.best_params:
                is_strategy = strategy_factory(opt_result.best_params)
                prior_best_params = copy.deepcopy(opt_result.best_params)
                prior_source_window = window_idx
            else:
                if config.frozen_params_mode:
                    is_strategy = strategy_factory(oos_params)
                    wr = _run_single_window(
                        is_strategy,
                        ohlcv,
                        boundary,
                        config,
                        opt_result,
                        oos_strategy=oos_strategy,
                        frozen_oos_params=copy.deepcopy(oos_params),
                        frozen_params_source_window=frozen_source,
                        is_fallback=True,
                    )
                    windows.append(wr)
                    continue
                else:
                    raise WalkForwardError(
                        f"Window {window_idx}: optimization produced no valid params"
                    )
        else:
            is_strategy = fallback_strategy

        windows.append(
            _run_single_window(
                is_strategy,
                ohlcv,
                boundary,
                config,
                opt_result,
                oos_strategy=oos_strategy,
                frozen_oos_params=frozen_oos,
                frozen_params_source_window=frozen_source,
            )
        )

    last_boundary = boundaries[-1] if boundaries else None
    discarded_bars = data_len - last_boundary.oos_end if last_boundary else data_len

    return WalkForwardResult(
        n_windows=len(windows),
        windows=windows,
        config=config,
        discarded_bars=discarded_bars,
        baseline_params=baseline_params,
        total_trials=cumulative_stats.n_trials,
        sr_variance=cumulative_stats.variance,
    )
