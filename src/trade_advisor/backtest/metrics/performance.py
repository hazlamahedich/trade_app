"""Performance metrics: return, risk-adjusted ratios, drawdown."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

import numpy as np
import pandas as pd

from trade_advisor.backtest.engine import BacktestResult
from trade_advisor.backtest.metrics._helpers import _annualization_factor, _simple_returns
from trade_advisor.core.types import from_float


@dataclass
class PerformanceMetrics:
    __hash__ = None  # type: ignore[assignment]

    total_return: Decimal
    cagr: Decimal
    sharpe: float
    sortino: float
    calmar: float
    max_drawdown: Decimal
    alpha: float
    beta: float
    information_ratio: float


_QUANT = Decimal("0.0000000001")


def _q(v: float) -> Decimal:
    if not np.isfinite(v):
        return Decimal("0")
    return from_float(v).quantize(_QUANT, rounding=ROUND_HALF_EVEN)


def _empty_metrics() -> PerformanceMetrics:
    return PerformanceMetrics(
        total_return=Decimal("0"),
        cagr=Decimal("0"),
        sharpe=0.0,
        sortino=0.0,
        calmar=0.0,
        max_drawdown=Decimal("0"),
        alpha=float("nan"),
        beta=float("nan"),
        information_ratio=float("nan"),
    )


def compute_performance_metrics(result: BacktestResult) -> PerformanceMetrics:
    equity = result.equity
    returns = _simple_returns(result).dropna()
    ann = _annualization_factor(result.config)
    initial_cash = float(result.config.initial_cash)

    if equity.empty:
        return _empty_metrics()

    total_return = _q((equity.iloc[-1] / initial_cash) - 1.0)

    idx = equity.index
    n_days = (idx[-1] - idx[0]).days if isinstance(idx, pd.DatetimeIndex) and len(idx) >= 2 else 0
    years = n_days / 365.25

    if years == 0 or total_return <= Decimal("-1"):
        cagr = total_return
    else:
        base = Decimal(1) + total_return
        if base <= 0:
            cagr = total_return
        else:
            cagr = _q(
                float(base ** (Decimal(1) / Decimal(str(years))) - Decimal(1))
            )

    cummax = equity.cummax()
    dd = (equity - cummax) / cummax
    max_drawdown = _q(float(dd.min()))

    returns_std = returns.std(ddof=1)
    if len(returns) > 1 and np.isfinite(returns_std) and returns_std != 0:
        sharpe = float(returns.mean() / returns_std * ann)
    else:
        sharpe = 0.0

    if len(returns) > 1:
        downside_diff = np.minimum(np.asarray(returns.values, dtype=float) - 0.0, 0.0)
        downside_semi_dev = float(np.sqrt(np.mean(downside_diff**2)))
        sortino = (
            float(returns.mean() / downside_semi_dev * ann)
            if np.isfinite(downside_semi_dev) and downside_semi_dev != 0
            else 0.0
        )
    else:
        sortino = 0.0

    calmar = float(cagr) / abs(float(max_drawdown)) if max_drawdown != Decimal(0) else 0.0

    return PerformanceMetrics(
        total_return=total_return,
        cagr=cagr,
        sharpe=sharpe,
        sortino=sortino,
        calmar=calmar,
        max_drawdown=max_drawdown,
        alpha=float("nan"),
        beta=float("nan"),
        information_ratio=float("nan"),
    )
