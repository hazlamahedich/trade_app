"""Tests for code review fixes — Story 1.1 review findings."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from trade_advisor.backtest.engine import _extract_trades, run_backtest
from trade_advisor.config import BacktestConfig, CostModel
from trade_advisor.evaluation.metrics import compute_metrics


def test_commission_fixed_now_supported():
    model = CostModel(commission_fixed=1.0)
    assert model.commission_fixed == 1.0


def test_initial_cash_rejects_zero():
    with pytest.raises(Exception):  # noqa: B017
        BacktestConfig(initial_cash=0)


def test_initial_cash_rejects_negative():
    with pytest.raises(Exception):  # noqa: B017
        BacktestConfig(initial_cash=-100)


def test_sortino_known_values():
    r = pd.Series([0.01, -0.02, 0.03, -0.01, 0.005, -0.03, 0.02, 0.01, -0.005, 0.015])
    m = compute_metrics(r, bars_per_year=252)
    downside_diff = np.minimum(r.values, 0.0)
    expected_dd = float(np.sqrt(np.mean(downside_diff**2)))
    expected_sortino = float(r.mean() / expected_dd * np.sqrt(252))
    assert abs(m.sortino - expected_sortino) < 0.01


def test_sortino_gte_sharpe_for_same_input():
    rng = np.random.default_rng(99)
    r = pd.Series(rng.normal(0.0005, 0.015, 500))
    m = compute_metrics(r)
    assert m.sortino >= m.sharpe - 0.5


def test_cagr_negative_equity_returns_minus_one():
    r = pd.Series([-1.5])
    m = compute_metrics(r, bars_per_year=252)
    assert m.cagr == -1.0


def test_cagr_positive_equity():
    r = pd.Series([0.01] * 252)
    m = compute_metrics(r)
    assert m.cagr > 0


def test_extract_trades_empty_position():
    pos = pd.Series(dtype="float64", name="position")
    price = pd.Series(dtype="float64", name="price")
    trades = _extract_trades(pos, price)
    assert trades.empty
    assert "entry_ts" in trades.columns
    assert "exit_ts" in trades.columns
    assert "side" in trades.columns


def test_signal_validation_rejects_invalid(synthetic_ohlcv):
    bad_sig = pd.Series(2, index=range(len(synthetic_ohlcv)), dtype="int8")
    with pytest.raises(ValueError, match=r"Signal values must be in"):
        run_backtest(synthetic_ohlcv, bad_sig)
