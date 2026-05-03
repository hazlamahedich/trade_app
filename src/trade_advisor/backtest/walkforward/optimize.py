"""In-sample hyperparameter search with median pruning.

Searches parameter space within a single IS window using cartesian product
enumeration with deterministic shuffle.  Median pruning marks below-median
trials post-hoc.  Sync, pure function — async bridge belongs in async_runner.

Architecture decisions (from adversarial review):
- strategy_factory decouples optimizer from specific strategies.
- ParamConstraint is a Protocol, not stringly-typed.
- PruningConfig dataclass replaces boolean flag.
- Seed via SeedManager hierarchy for deterministic reproducibility.
- Per-trial errors caught gracefully → TrialResult(status="failed").
"""

from __future__ import annotations

import itertools
import math
import random
import statistics
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from trade_advisor.backtest.engine import run_backtest
from trade_advisor.config import BacktestConfig

if False:
    from trade_advisor.strategies.interface import Strategy


class ParamConstraint(Protocol):
    def __call__(self, params: dict[str, Any]) -> bool: ...


def monotonic_increasing(*param_names: str) -> ParamConstraint:
    def _check(params: dict[str, Any]) -> bool:
        for i in range(len(param_names) - 1):
            if params[param_names[i]] >= params[param_names[i + 1]]:
                return False
        return True

    return _check


def min_spacing(param_a: str, param_b: str, *, min_gap: int = 1) -> ParamConstraint:
    def _check(params: dict[str, Any]) -> bool:
        val: bool = abs(params[param_a] - params[param_b]) >= min_gap
        return val

    return _check


@dataclass(frozen=True)
class PruningConfig:
    enabled: bool = True
    method: Literal["median"] = "median"
    min_trials_before_prune: int = 5


class OptimizationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    param_ranges: dict[str, list[Any]]
    max_trials: int = Field(100, gt=0)
    pruning: PruningConfig = Field(default_factory=PruningConfig)
    metric: str = "sharpe"
    maximize: bool = True
    constraints: list[Any] = Field(default_factory=list)


@dataclass
class TrialResult:
    params: dict[str, Any]
    metric: float
    status: Literal["evaluated", "pruned", "failed"] = "evaluated"
    error: str | None = None


@dataclass
class OptimizationResult:
    best_params: dict[str, Any]
    best_metric: float
    n_trials: int
    n_pruned: int
    all_results: list[TrialResult] = field(default_factory=list)


def _enumerate_candidates(
    param_ranges: dict[str, list[Any]],
    max_trials: int,
    seed: int,
) -> list[dict[str, Any]]:
    keys = list(param_ranges.keys())
    all_combos = [
        dict(zip(keys, vals, strict=True)) for vals in itertools.product(*param_ranges.values())
    ]
    rng = random.Random(seed)
    rng.shuffle(all_combos)
    return all_combos[:max_trials]


def _extract_metric(bt_result: Any, metric_name: str) -> float:
    equity = bt_result.equity
    if len(equity) < 2 or equity.iloc[0] == 0.0:
        return float("nan")

    total_return = float(equity.iloc[-1] / equity.iloc[0] - 1.0)

    if metric_name == "return":
        return total_return

    rets = bt_result.returns
    if rets.std() == 0.0:
        return 0.0
    import math as _math

    return float(rets.mean() / rets.std() * _math.sqrt(252))


def _evaluate_trial(
    is_ohlcv: pd.DataFrame,
    params: dict[str, Any],
    strategy_factory: Callable[[dict[str, Any]], Strategy],
    backtest_cfg: BacktestConfig,
    metric_name: str,
    constraints: list[Any],
) -> TrialResult:
    for constraint in constraints:
        if not constraint(params):
            return TrialResult(
                params=params,
                metric=float("nan"),
                status="failed",
                error="Constraint violated",
            )

    try:
        strategy = strategy_factory(params)
    except Exception as exc:
        return TrialResult(
            params=params,
            metric=float("nan"),
            status="failed",
            error=str(exc),
        )

    try:
        signals = strategy.generate_signals(is_ohlcv)
        bt_result = run_backtest(is_ohlcv, signals, backtest_cfg)
        metric_val = _extract_metric(bt_result, metric_name)
    except Exception as exc:
        return TrialResult(
            params=params,
            metric=float("nan"),
            status="failed",
            error=str(exc),
        )

    return TrialResult(params=params, metric=metric_val, status="evaluated")


def _median_prune(
    results: list[TrialResult],
    maximize: bool,
    min_trials: int,
) -> int:
    evaluated = [r for r in results if r.status == "evaluated"]
    if len(evaluated) < min_trials:
        return 0

    finite_metrics = [r.metric for r in evaluated if math.isfinite(r.metric)]
    if not finite_metrics:
        return 0

    median = statistics.median(finite_metrics)
    n_pruned = 0
    for r in evaluated:
        if (maximize and r.metric < median) or (not maximize and r.metric > median):
            r.status = "pruned"
            n_pruned += 1
    return n_pruned


def optimize_is_window(
    is_ohlcv: pd.DataFrame,
    config: OptimizationConfig,
    strategy_factory: Callable[[dict[str, Any]], Strategy],
    backtest_cfg: BacktestConfig,
    seed: int = 0,
) -> OptimizationResult:
    candidates = _enumerate_candidates(config.param_ranges, config.max_trials, seed)

    all_results: list[TrialResult] = []
    for _trial_index, candidate_params in enumerate(candidates):
        result = _evaluate_trial(
            is_ohlcv,
            candidate_params,
            strategy_factory,
            backtest_cfg,
            config.metric,
            config.constraints,
        )
        all_results.append(result)

    n_pruned = 0
    if config.pruning.enabled:
        n_pruned = _median_prune(
            all_results, config.maximize, config.pruning.min_trials_before_prune
        )

    evaluated_results = [r for r in all_results if r.status == "evaluated"]
    finite_results = [r for r in evaluated_results if math.isfinite(r.metric)]
    if not finite_results:
        best_params: dict[str, Any] = {}
        best_metric = float("nan")
    else:
        if config.maximize:
            best = max(finite_results, key=lambda r: r.metric)
        else:
            best = min(finite_results, key=lambda r: r.metric)
        best_params = best.params
        best_metric = best.metric

    return OptimizationResult(
        best_params=best_params,
        best_metric=best_metric,
        n_trials=len(candidates),
        n_pruned=n_pruned,
        all_results=all_results,
    )
