"""Comprehensive unit tests for the vectorized backtest engine.

Tests cover:
- Empty DataFrame handling
- Flat signal (zero) → constant equity
- Long-only strategy in uptrend
- Short-only strategy in downtrend
- Determinism (10-run bitwise identical)
- Cost model reducing equity
- Equity starts at initial_cash
- Trade list column schema
- Float signal values (continuous [-1.0, +1.0])
- Signal out-of-range rejection
- No NaN in equity curve
- Performance (2520 bars < 1s)
"""

from __future__ import annotations

import time
import warnings

import numpy as np
import pandas as pd
import pytest

from tests.helpers import _synthetic_ohlcv
from trade_advisor.backtest.engine import run_backtest
from trade_advisor.backtest.vectorized import run_vectorized_backtest
from trade_advisor.config import BacktestConfig, CostModel
from trade_advisor.strategies.sma_cross import SmaCross


@pytest.fixture
def ohlcv_500():
    return _synthetic_ohlcv(n=500, seed=42)


@pytest.fixture
def backtest_config():
    return BacktestConfig(
        initial_cash="100000",
        cost=CostModel(commission_pct=0.001, slippage_pct=0.0005),
    )


@pytest.fixture
def zero_cost_config():
    return BacktestConfig(
        initial_cash="100000",
        cost=CostModel(commission_pct=0.0, slippage_pct=0.0),
    )


@pytest.fixture
def ohlcv_trending_up():
    return _synthetic_ohlcv(n=500, seed=42, trend=0.002, vol=0.005)


@pytest.fixture
def ohlcv_trending_down():
    n = 500
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2020-01-01", periods=n)
    close = 100.0
    closes = []
    for _ in range(n):
        close *= 1.0 + rng.normal(-0.002, 0.01)
        closes.append(close)
    close_s = pd.Series(closes)
    return pd.DataFrame(
        {
            "symbol": "DOWN",
            "interval": "1d",
            "timestamp": dates,
            "open": close_s * 0.999,
            "high": close_s * 1.002,
            "low": close_s * 0.997,
            "close": close_s,
            "adj_close": close_s,
            "volume": rng.integers(1_000_000, 5_000_000, n),
            "source": "synthetic",
        }
    )


def test_empty_dataframe_returns_empty_result(backtest_config):
    empty = pd.DataFrame(
        columns=[
            "symbol",
            "interval",
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "adj_close",
            "volume",
            "source",
        ],
    )
    signal = pd.Series(dtype="float64", name="signal")
    result = run_vectorized_backtest(empty, signal, backtest_config)
    assert len(result.equity) == 0
    assert len(result.trades) == 0


def test_flat_signal_constant_equity(ohlcv_500, backtest_config):
    flat = pd.Series(0.0, index=range(len(ohlcv_500)), dtype="float64", name="signal")
    result = run_vectorized_backtest(ohlcv_500, flat, backtest_config)
    assert (result.equity == float(backtest_config.initial_cash)).all()
    assert result.trades.empty


def test_long_only_strategy_positive_return_in_up_trend(ohlcv_trending_up, zero_cost_config):
    strategy = SmaCross(fast=10, slow=30)
    signals = strategy.generate_signals(ohlcv_trending_up)
    result = run_vectorized_backtest(ohlcv_trending_up, signals, zero_cost_config)
    assert result.equity.iloc[-1] >= float(zero_cost_config.initial_cash)


def test_short_only_strategy_positive_return_in_down_trend(ohlcv_trending_down, zero_cost_config):
    strategy = SmaCross(fast=5, slow=20, allow_short=True)
    signals = strategy.generate_signals(ohlcv_trending_down)
    result = run_vectorized_backtest(ohlcv_trending_down, signals, zero_cost_config)
    assert result.equity.iloc[-1] >= float(zero_cost_config.initial_cash)


def test_determinism_10_runs_bitwise_identical(ohlcv_500, zero_cost_config):
    strategy = SmaCross(fast=20, slow=50)
    signals = strategy.generate_signals(ohlcv_500)
    results = [run_vectorized_backtest(ohlcv_500, signals, zero_cost_config) for _ in range(10)]
    for i in range(1, 10):
        np.testing.assert_array_equal(results[0].equity.values, results[i].equity.values)
        np.testing.assert_array_equal(results[0].returns.values, results[i].returns.values)
        np.testing.assert_array_equal(results[0].positions.values, results[i].positions.values)
        pd.testing.assert_frame_equal(results[0].trades, results[i].trades)
        assert results[0].meta == results[i].meta


def test_costs_reduce_final_equity(ohlcv_500):
    strategy = SmaCross(fast=10, slow=30)
    signals = strategy.generate_signals(ohlcv_500)

    no_cost = run_vectorized_backtest(
        ohlcv_500,
        signals,
        BacktestConfig(cost=CostModel(commission_pct=0, slippage_pct=0)),
    )
    with_cost = run_vectorized_backtest(
        ohlcv_500,
        signals,
        BacktestConfig(cost=CostModel(commission_pct=0.001, slippage_pct=0.001)),
    )
    assert with_cost.equity.iloc[-1] <= no_cost.equity.iloc[-1]


def test_equity_starts_at_initial_cash(ohlcv_500, backtest_config):
    strategy = SmaCross(fast=20, slow=50)
    signals = strategy.generate_signals(ohlcv_500)
    result = run_vectorized_backtest(ohlcv_500, signals, backtest_config)
    assert float(result.equity.iloc[0]) == float(backtest_config.initial_cash)


def test_trade_list_columns(ohlcv_500, backtest_config):
    strategy = SmaCross(fast=10, slow=30)
    signals = strategy.generate_signals(ohlcv_500)
    result = run_vectorized_backtest(ohlcv_500, signals, backtest_config)
    expected = {"entry_ts", "exit_ts", "side", "entry_price", "exit_price", "return", "weight"}
    assert expected == set(result.trades.columns)


def test_float_signal_values_accepted(ohlcv_500, zero_cost_config):
    n = len(ohlcv_500)
    rng = np.random.default_rng(42)
    float_signal = pd.Series(rng.uniform(-0.5, 0.5, n), dtype="float64", name="signal")
    result = run_vectorized_backtest(ohlcv_500, float_signal, zero_cost_config)
    assert len(result.equity) == n
    assert not result.equity.isna().any()


def test_signal_out_of_range_rejected(ohlcv_500, backtest_config):
    bad_signal = pd.Series(2.0, index=range(len(ohlcv_500)), dtype="float64", name="signal")
    with pytest.raises(ValueError, match=r"\[-1\.0.*\+1\.0\]"):
        run_vectorized_backtest(ohlcv_500, bad_signal, backtest_config)


def test_no_nan_in_equity_curve(ohlcv_500, backtest_config):
    strategy = SmaCross(fast=20, slow=50)
    signals = strategy.generate_signals(ohlcv_500)
    result = run_vectorized_backtest(ohlcv_500, signals, backtest_config)
    assert not result.equity.isna().any()
    assert not result.returns.isna().any()


def test_performance_10yr_single_symbol_fast():
    ohlcv = _synthetic_ohlcv(n=2520, seed=42, symbol="SPY")
    strategy = SmaCross(fast=20, slow=50)
    signals = strategy.generate_signals(ohlcv)
    config = BacktestConfig(cost=CostModel(commission_pct=0.001))

    start = time.monotonic()
    run_vectorized_backtest(ohlcv, signals, config)
    elapsed = time.monotonic() - start

    assert elapsed < 1.0, f"2520-bar backtest took {elapsed:.3f}s, exceeds 1s budget"


def test_float_signal_trade_records_have_weight(ohlcv_500, zero_cost_config):
    n = len(ohlcv_500)
    signal = pd.Series(0.0, index=range(n), dtype="float64", name="signal")
    signal.iloc[10:30] = 0.5
    signal.iloc[35:50] = -0.7
    result = run_vectorized_backtest(ohlcv_500, signal, zero_cost_config)
    if not result.trades.empty:
        assert "weight" in result.trades.columns
        assert all(0.0 < w <= 1.0 for w in result.trades["weight"])


def test_strict_mode_default_is_true():
    cfg = BacktestConfig()
    assert cfg.strict is True


def test_strict_mode_raises_on_nan_equity(ohlcv_500):
    df = ohlcv_500.copy()
    df.loc[df.index[100], "close"] = 0.0
    df.loc[df.index[100], "adj_close"] = 0.0
    df.loc[df.index[101], "close"] = 0.0
    df.loc[df.index[101], "adj_close"] = 0.0
    flat = pd.Series(1.0, index=range(len(df)), dtype="float64", name="signal")
    with pytest.raises(ValueError, match="Equity curve contains NaN"):
        run_vectorized_backtest(df, flat, BacktestConfig(strict=True))


def test_strict_false_fills_and_warns(ohlcv_500):
    df = ohlcv_500.copy()
    df.loc[df.index[100], "close"] = 0.0
    df.loc[df.index[100], "adj_close"] = 0.0
    df.loc[df.index[101], "close"] = 0.0
    df.loc[df.index[101], "adj_close"] = 0.0
    flat = pd.Series(1.0, index=range(len(df)), dtype="float64", name="signal")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = run_vectorized_backtest(df, flat, BacktestConfig(strict=False))
        assert not result.equity.isna().any()
        nan_warnings = [x for x in w if "NaN value" in str(x.message)]
        assert len(nan_warnings) >= 1


def test_missing_timestamp_raises():
    df = pd.DataFrame({"close": [100.0, 101.0], "volume": [1000, 1000]})
    sig = pd.Series([0.0, 0.0], dtype="float64")
    with pytest.raises(ValueError, match="timestamp"):
        run_vectorized_backtest(df, sig)


def test_missing_close_and_adj_close_raises():
    df = pd.DataFrame({"timestamp": ["2020-01-01", "2020-01-02"], "volume": [1000, 1000]})
    sig = pd.Series([0.0, 0.0], dtype="float64")
    with pytest.raises(ValueError, match=r"close.*adj_close"):
        run_vectorized_backtest(df, sig)


def test_run_backtest_backward_compat_delegates(ohlcv_500, backtest_config):
    strategy = SmaCross(fast=20, slow=50)
    signals = strategy.generate_signals(ohlcv_500)
    result_wrapped = run_backtest(ohlcv_500, signals, backtest_config)
    result_direct = run_vectorized_backtest(ohlcv_500, signals, backtest_config)
    pd.testing.assert_series_equal(result_wrapped.equity, result_direct.equity)
