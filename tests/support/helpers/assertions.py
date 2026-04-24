"""Shared test helpers and utilities."""

from __future__ import annotations

import numpy as np
import pandas as pd


def assert_no_lookahead_bias(signals: pd.Series, price: pd.Series) -> None:
    shifted = signals.shift(1)
    correlation = shifted.corr(price.pct_change())
    if not pd.isna(correlation) and abs(correlation) > 0.9:
        raise AssertionError(f"Signals may have lookahead bias: corr={correlation:.4f}")


def assert_signals_in_range(signals: pd.Series) -> None:
    unique = set(signals.dropna().unique())
    valid = {-1, 0, 1}
    invalid = unique - valid
    if invalid:
        raise AssertionError(f"Invalid signal values: {invalid}. Expected subset of {-1, 0, 1}")


def compute_test_sharpe(returns: pd.Series, periods_per_year: int = 252) -> float:
    if returns.std() == 0:
        return 0.0
    return float((returns.mean() / returns.std()) * np.sqrt(periods_per_year))
