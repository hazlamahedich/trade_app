"""Risk metrics: VaR, CVaR, tail ratio, drawdown analysis."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from trade_advisor.backtest.engine import BacktestResult
from trade_advisor.backtest.metrics._helpers import _simple_returns


@dataclass
class RiskMetrics:
    __hash__ = None  # type: ignore[assignment]

    var_95: float
    cvar_95: float
    tail_ratio: float
    max_dd_duration_bars: int
    drawdown_distribution: pd.Series


def compute_risk_metrics(result: BacktestResult) -> RiskMetrics:
    returns = _simple_returns(result).dropna()
    equity = result.equity

    if returns.empty:
        cummax = equity.cummax()
        dd_dist = (equity - cummax) / cummax
        return RiskMetrics(
            var_95=float("nan"),
            cvar_95=float("nan"),
            tail_ratio=0.0,
            max_dd_duration_bars=0,
            drawdown_distribution=dd_dist,
        )

    var_95 = float(np.percentile(returns, 5))
    tail = returns[returns <= var_95]
    cvar_95 = float(tail.mean()) if len(tail) > 0 else float("nan")

    p95 = float(np.percentile(returns, 95))
    p5 = float(np.percentile(returns, 5))
    tail_ratio = abs(p95 / p5) if p5 != 0 else 0.0

    cummax = equity.cummax()
    dd_dist = (equity - cummax) / cummax

    in_dd = equity < cummax
    max_dd_duration_bars = 0
    current_streak = 0
    for val in in_dd:
        if val:
            current_streak += 1
            max_dd_duration_bars = max(max_dd_duration_bars, current_streak)
        else:
            current_streak = 0

    return RiskMetrics(
        var_95=var_95,
        cvar_95=cvar_95,
        tail_ratio=tail_ratio,
        max_dd_duration_bars=max_dd_duration_bars,
        drawdown_distribution=dd_dist,
    )
