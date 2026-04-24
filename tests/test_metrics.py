"""Metrics unit tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from trade_advisor.evaluation.metrics import compute_metrics, drawdown_series, max_drawdown


def test_empty_returns_gives_zeros():
    m = compute_metrics(pd.Series([], dtype="float64"))
    assert m.total_return == 0
    assert m.sharpe == 0


def test_positive_constant_returns():
    """A tiny positive return every bar -> positive metrics, zero drawdown."""
    r = pd.Series([0.001] * 252)
    m = compute_metrics(r)
    assert m.total_return > 0
    assert m.cagr > 0
    assert m.max_drawdown == 0
    # Zero vol means Sharpe is undefined; we return 0 by convention.
    assert m.sharpe == 0


def test_known_sharpe_roughly_matches():
    """With known mean/std, annualized Sharpe should match the formula."""
    rng = np.random.default_rng(7)
    mu, sigma = 0.0005, 0.01
    r = pd.Series(rng.normal(mu, sigma, 10_000))
    m = compute_metrics(r)
    expected = (mu / sigma) * np.sqrt(252)
    assert abs(m.sharpe - expected) < 0.2  # loose — finite-sample noise


def test_max_drawdown_simple():
    equity = pd.Series([100, 110, 90, 95, 120])
    # Drawdown trough at bar 2: (90 - 110) / 110 = -0.1818...
    assert max_drawdown(equity) == pytest.approx(-0.1818, abs=1e-3)


def test_drawdown_series_always_non_positive():
    rng = np.random.default_rng(1)
    equity = pd.Series(100 * np.cumprod(1 + rng.normal(0, 0.01, 500)))
    dd = drawdown_series(equity)
    assert (dd <= 1e-12).all()
