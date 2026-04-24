"""Performance metrics.

All metrics assume ``returns`` is a Series of per-bar simple returns.
``bars_per_year`` defaults to 252 (US equity trading days). For hourly or
crypto data, pass the appropriate value.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


@dataclass
class Metrics:
    total_return: float
    cagr: float
    annual_vol: float
    sharpe: float
    sortino: float
    max_drawdown: float
    calmar: float
    win_rate: float
    n_bars: int

    def to_dict(self) -> dict:
        return asdict(self)


def compute_metrics(
    returns: pd.Series,
    bars_per_year: int = 252,
    rf: float = 0.0,
) -> Metrics:
    r = returns.dropna().astype("float64")
    if len(r) == 0:
        return Metrics(0, 0, 0, 0, 0, 0, 0, 0, 0)

    equity = (1.0 + r).cumprod()
    total_return = float(equity.iloc[-1] - 1.0)

    # CAGR
    years = len(r) / bars_per_year
    cagr = float(equity.iloc[-1] ** (1 / years) - 1.0) if years > 0 else 0.0

    annual_vol = float(r.std(ddof=0) * np.sqrt(bars_per_year))

    excess = r - rf / bars_per_year
    sharpe = float(excess.mean() / r.std(ddof=0) * np.sqrt(bars_per_year)) if r.std(ddof=0) > 0 else 0.0

    downside = r[r < 0]
    downside_std = float(downside.std(ddof=0)) if len(downside) > 0 else 0.0
    sortino = float(excess.mean() / downside_std * np.sqrt(bars_per_year)) if downside_std > 0 else 0.0

    mdd = float(max_drawdown(equity))
    calmar = float(cagr / abs(mdd)) if mdd < 0 else 0.0

    win_rate = float((r > 0).sum() / (r != 0).sum()) if (r != 0).any() else 0.0

    return Metrics(
        total_return=total_return,
        cagr=cagr,
        annual_vol=annual_vol,
        sharpe=sharpe,
        sortino=sortino,
        max_drawdown=mdd,
        calmar=calmar,
        win_rate=win_rate,
        n_bars=len(r),
    )


def max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = equity / peak - 1.0
    return float(dd.min())


def drawdown_series(equity: pd.Series) -> pd.Series:
    peak = equity.cummax()
    return equity / peak - 1.0
