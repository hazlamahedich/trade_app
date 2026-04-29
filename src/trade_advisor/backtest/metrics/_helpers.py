"""Shared helper utilities for metric computations."""

from __future__ import annotations

import pandas as pd

from trade_advisor.backtest.engine import BacktestResult
from trade_advisor.config import BacktestConfig


def _annualization_factor(config: BacktestConfig) -> float:
    freq: str = getattr(config, "freq", "1D")
    mapping: dict[str, float] = {
        "1D": 252,
        "1W": 52,
        "1M": 12,
        "1H": 252 * 6.5,
    }
    periods = mapping.get(freq, 252)
    return float(periods**0.5)


def _simple_returns(result: BacktestResult) -> pd.Series:
    return result.returns
