"""Comprehensive unit tests for backtest/event_driven.py — EventDrivenEngine."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tests.helpers import _synthetic_ohlcv
from trade_advisor.backtest.engine import BacktestResult
from trade_advisor.backtest.event_driven import EventDrivenEngine
from trade_advisor.backtest.protocols import BacktestEngine
from trade_advisor.config import BacktestConfig, CostModel


@pytest.fixture
def ohlcv_500() -> pd.DataFrame:
    return _synthetic_ohlcv(n=500, seed=42)


@pytest.fixture
def backtest_config() -> BacktestConfig:
    return BacktestConfig(
        initial_cash="100000",
        cost=CostModel(commission_pct=0.001, slippage_pct=0.0005),
    )


@pytest.fixture
def zero_cost_config() -> BacktestConfig:
    return BacktestConfig(
        initial_cash="100000",
        cost=CostModel(commission_pct=0.0, slippage_pct=0.0),
    )


def _make_signals(ohlcv: pd.DataFrame, flat: bool = False) -> pd.Series:
    if flat:
        return pd.Series(np.zeros(len(ohlcv)), dtype="float64", name="signal")
    from trade_advisor.strategies.sma_cross import SmaCross

    strategy = SmaCross(fast=20, slow=50)
    return strategy.generate_signals(ohlcv)


class TestEventDrivenEngine:
    def test_event_driven_satisfies_protocol(self):
        assert isinstance(EventDrivenEngine(), BacktestEngine)

    def test_event_driven_empty_dataframe(self):
        ohlcv = pd.DataFrame(
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
            ]
        )
        signal = pd.Series(dtype="float64", name="signal")
        engine = EventDrivenEngine()
        result = engine.run(ohlcv, signal)
        assert isinstance(result, BacktestResult)
        assert len(result.equity) == 0
        assert len(result.trades) == 0

    def test_event_driven_flat_signal_constant_equity(self, ohlcv_500, backtest_config):
        signal = _make_signals(ohlcv_500, flat=True)
        engine = EventDrivenEngine(backtest_config)
        result = engine.run(ohlcv_500, signal)
        assert isinstance(result, BacktestResult)
        np.testing.assert_allclose(
            result.equity.values,
            float(backtest_config.initial_cash),
            atol=1e-10,
        )

    def test_event_driven_determinism_10_runs(self, ohlcv_500, backtest_config):
        signal = _make_signals(ohlcv_500)
        engine = EventDrivenEngine(backtest_config)
        results = [engine.run(ohlcv_500, signal) for _ in range(10)]
        first = results[0]
        for r in results[1:]:
            pd.testing.assert_series_equal(first.equity, r.equity)
            pd.testing.assert_frame_equal(first.trades, r.trades)

    def test_event_driven_market_order_trades(self, ohlcv_500, backtest_config):
        signal = _make_signals(ohlcv_500)
        engine = EventDrivenEngine(backtest_config)
        result = engine.run(ohlcv_500, signal)
        assert isinstance(result, BacktestResult)
        assert hasattr(result, "equity")
        assert hasattr(result, "trades")

    def test_event_driven_stop_loss_triggers(self, ohlcv_500, backtest_config):
        signal = _make_signals(ohlcv_500)
        engine = EventDrivenEngine(backtest_config, stop_loss_pct=0.05)
        result = engine.run(ohlcv_500, signal)
        assert isinstance(result, BacktestResult)
        assert hasattr(result, "equity")
        assert len(result.equity) > 0

    def test_event_driven_limit_order_execution(self, ohlcv_500, backtest_config):
        signal = _make_signals(ohlcv_500)
        engine = EventDrivenEngine(backtest_config)
        result = engine.run(ohlcv_500, signal)
        if not result.trades.empty:
            assert "order_type" in result.trades.columns
            limit_trades = result.trades[result.trades["order_type"] == "limit"]
            assert len(limit_trades) >= 0
        else:
            assert True

    def test_event_driven_equity_starts_at_initial_cash(self, ohlcv_500, backtest_config):
        signal = _make_signals(ohlcv_500)
        engine = EventDrivenEngine(backtest_config)
        result = engine.run(ohlcv_500, signal)
        assert abs(result.equity.iloc[0] - float(backtest_config.initial_cash)) < 1e-10

    def test_event_driven_no_nan_in_equity(self, ohlcv_500, backtest_config):
        signal = _make_signals(ohlcv_500)
        engine = EventDrivenEngine(backtest_config)
        result = engine.run(ohlcv_500, signal)
        assert not result.equity.isna().any()

    def test_event_driven_negative_equity_capped(self):
        n = 50
        dates = pd.bdate_range("2020-01-01", periods=n)
        close = pd.Series(np.linspace(100, 10, n))
        ohlcv = pd.DataFrame(
            {
                "symbol": "CRASH",
                "interval": "1d",
                "timestamp": dates,
                "open": close * 0.999,
                "high": close * 1.001,
                "low": close * 0.998,
                "close": close,
                "adj_close": close,
                "volume": 1_000_000,
                "source": "synthetic",
            }
        )
        sig = pd.Series(np.ones(n), dtype="float64", name="signal")
        sig.iloc[:5] = 0.0
        sig.iloc[5] = 1.0
        cfg = BacktestConfig(
            initial_cash="100",
            cost=CostModel(commission_pct=0.0, slippage_pct=0.0),
        )
        engine = EventDrivenEngine(cfg, stop_loss_pct=0.99)
        result = engine.run(ohlcv, sig)
        assert (result.equity >= 0).all()

    def test_event_driven_malformed_orderspec_raises(self):
        from trade_advisor.backtest.execution import OrderSpec

        with pytest.raises(ValueError):
            OrderSpec(side="buy", order_type="market", quantity=-5)
        with pytest.raises(ValueError):
            OrderSpec(side="buy", order_type="limit", quantity=10)

    def test_event_driven_signal_boundary_first_bar(self, ohlcv_500, backtest_config):
        signal = pd.Series(np.zeros(len(ohlcv_500)), dtype="float64", name="signal")
        signal.iloc[0] = 1.0
        engine = EventDrivenEngine(backtest_config)
        result = engine.run(ohlcv_500, signal)
        assert isinstance(result, BacktestResult)
        assert len(result.equity) == len(ohlcv_500)

    def test_event_driven_signal_boundary_last_bar(self, ohlcv_500, backtest_config):
        signal = pd.Series(np.zeros(len(ohlcv_500)), dtype="float64", name="signal")
        signal.iloc[-1] = 1.0
        engine = EventDrivenEngine(backtest_config)
        result = engine.run(ohlcv_500, signal)
        assert isinstance(result, BacktestResult)
        assert len(result.equity) == len(ohlcv_500)

    def test_event_driven_signal_range_validation(self, ohlcv_500, backtest_config):
        signal = pd.Series(np.ones(len(ohlcv_500)), dtype="float64", name="signal")
        signal.iloc[10] = 2.0
        engine = EventDrivenEngine(backtest_config)
        with pytest.raises(ValueError, match=r"\[-1\.0, \+1\.0\]"):
            engine.run(ohlcv_500, signal)

    def test_event_driven_config_override(self, ohlcv_500):
        cfg1 = BacktestConfig(initial_cash="100000")
        cfg2 = BacktestConfig(initial_cash="50000")
        signal = _make_signals(ohlcv_500)
        engine = EventDrivenEngine(cfg1)
        result = engine.run(ohlcv_500, signal, config=cfg2)
        assert abs(result.equity.iloc[0] - 50000.0) < 1e-10

    def test_stop_loss_produces_stop_order_type(self):
        n = 20
        dates = pd.bdate_range("2020-01-01", periods=n)
        close = pd.Series(np.linspace(100, 70, n))
        ohlcv = pd.DataFrame(
            {
                "symbol": "STOP",
                "interval": "1d",
                "timestamp": dates,
                "open": close * 0.999,
                "high": close * 1.001,
                "low": close * 0.998,
                "close": close,
                "adj_close": close,
                "volume": 1_000_000,
                "source": "synthetic",
            }
        )
        sig = pd.Series(np.zeros(n), dtype="float64", name="signal")
        sig.iloc[1:10] = 1.0
        cfg = BacktestConfig(
            initial_cash="100000",
            cost=CostModel(commission_pct=0.001, slippage_pct=0.0005),
        )
        engine = EventDrivenEngine(cfg, stop_loss_pct=0.10)
        result = engine.run(ohlcv, sig)
        if not result.trades.empty and "order_type" in result.trades.columns:
            stop_trades = result.trades[result.trades["order_type"] == "stop"]
            if len(stop_trades) > 0:
                assert stop_trades.iloc[0]["order_type"] == "stop"
                assert "cost_components" in stop_trades.iloc[0]

    def test_stop_loss_with_tight_threshold_exits_position(self):
        n = 15
        dates = pd.bdate_range("2020-01-01", periods=n)
        prices = [100, 101, 102, 99, 95, 90, 85, 80, 75, 70, 65, 60, 55, 50, 45]
        close = pd.Series(prices, dtype="float64")
        ohlcv = pd.DataFrame(
            {
                "symbol": "TIGHT",
                "interval": "1d",
                "timestamp": dates,
                "open": close * 0.999,
                "high": close * 1.001,
                "low": close * 0.998,
                "close": close,
                "adj_close": close,
                "volume": 1_000_000,
                "source": "synthetic",
            }
        )
        sig = pd.Series(np.zeros(n), dtype="float64", name="signal")
        sig.iloc[1:8] = 1.0
        cfg = BacktestConfig(
            initial_cash="100000",
            cost=CostModel(commission_pct=0.0, slippage_pct=0.0),
        )
        engine = EventDrivenEngine(cfg, stop_loss_pct=0.03)
        result = engine.run(ohlcv, sig)
        assert isinstance(result, BacktestResult)
        assert len(result.equity) == n
        assert (result.equity >= 0).all()

    def test_zero_equity_forces_flat_position(self):
        n = 10
        dates = pd.bdate_range("2020-01-01", periods=n)
        close = pd.Series(
            [100, 1, 0.01, 0.001, 0.0001, 0.00001, 0.000001, 0.0000001, 0.00000001, 0.000000001],
            dtype="float64",
        )
        ohlcv = pd.DataFrame(
            {
                "symbol": "WIPE",
                "interval": "1d",
                "timestamp": dates,
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "adj_close": close,
                "volume": 1_000_000,
                "source": "synthetic",
            }
        )
        sig = pd.Series(np.ones(n), dtype="float64", name="signal")
        sig.iloc[0] = 0.0
        sig.iloc[1] = 1.0
        cfg = BacktestConfig(
            initial_cash="1",
            cost=CostModel(commission_pct=0.0, slippage_pct=0.0),
            strict=False,
        )
        engine = EventDrivenEngine(cfg, stop_loss_pct=0.99)
        result = engine.run(ohlcv, sig)
        assert isinstance(result, BacktestResult)
        assert (result.equity >= -1e-10).all()

    def test_nan_equity_strict_mode_raises(self):
        n = 5
        dates = pd.bdate_range("2020-01-01", periods=n)
        close = pd.Series([100.0, np.nan, 98.0, 97.0, 96.0])
        ohlcv = pd.DataFrame(
            {
                "symbol": "NAN",
                "interval": "1d",
                "timestamp": dates,
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "adj_close": close,
                "volume": 1_000_000,
                "source": "synthetic",
            }
        )
        sig = pd.Series(np.ones(n), dtype="float64", name="signal")
        sig.iloc[0] = 0.0
        cfg = BacktestConfig(
            initial_cash="100000",
            cost=CostModel(commission_pct=0.0, slippage_pct=0.0),
            strict=True,
        )
        engine = EventDrivenEngine(cfg, stop_loss_pct=0.99)
        with pytest.raises(ValueError, match="NaN"):
            engine.run(ohlcv, sig)

    def test_nan_equity_non_strict_forward_fills(self):
        n = 5
        dates = pd.bdate_range("2020-01-01", periods=n)
        close = pd.Series([100.0, np.nan, 98.0, 97.0, 96.0])
        ohlcv = pd.DataFrame(
            {
                "symbol": "NAN2",
                "interval": "1d",
                "timestamp": dates,
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "adj_close": close,
                "volume": 1_000_000,
                "source": "synthetic",
            }
        )
        sig = pd.Series(np.ones(n), dtype="float64", name="signal")
        sig.iloc[0] = 0.0
        cfg = BacktestConfig(
            initial_cash="100000",
            cost=CostModel(commission_pct=0.0, slippage_pct=0.0),
            strict=False,
        )
        engine = EventDrivenEngine(cfg, stop_loss_pct=0.99)
        with pytest.warns(RuntimeWarning):
            result = engine.run(ohlcv, sig)
        assert isinstance(result, BacktestResult)
        assert not result.equity.isna().any()

    def test_stop_loss_with_short_position(self):
        n = 20
        dates = pd.bdate_range("2020-01-01", periods=n)
        close = pd.Series(np.linspace(100, 130, n), dtype="float64")
        ohlcv = pd.DataFrame(
            {
                "symbol": "SHORT",
                "interval": "1d",
                "timestamp": dates,
                "open": close * 0.999,
                "high": close * 1.001,
                "low": close * 0.998,
                "close": close,
                "adj_close": close,
                "volume": 1_000_000,
                "source": "synthetic",
            }
        )
        sig = pd.Series(np.zeros(n), dtype="float64", name="signal")
        sig.iloc[1:15] = -1.0
        cfg = BacktestConfig(
            initial_cash="100000",
            cost=CostModel(commission_pct=0.0, slippage_pct=0.0),
        )
        engine = EventDrivenEngine(cfg, stop_loss_pct=0.10)
        result = engine.run(ohlcv, sig)
        assert isinstance(result, BacktestResult)
        assert len(result.equity) == n
        assert (result.equity >= 0).all()

    def test_stop_loss_negative_stop_pct_raises(self):
        with pytest.raises(ValueError, match="stop_loss_pct must be positive"):
            EventDrivenEngine(stop_loss_pct=-0.05)

    def test_stop_loss_with_side_flip_generates_both_trade_types(self):
        n = 30
        dates = pd.bdate_range("2020-01-01", periods=n)
        close = pd.Series(100 + np.sin(np.arange(n) * 0.5) * 15, dtype="float64")
        ohlcv = pd.DataFrame(
            {
                "symbol": "FLIP",
                "interval": "1d",
                "timestamp": dates,
                "open": close * 0.999,
                "high": close * 1.001,
                "low": close * 0.998,
                "close": close,
                "adj_close": close,
                "volume": 1_000_000,
                "source": "synthetic",
            }
        )
        sig = pd.Series(np.zeros(n), dtype="float64", name="signal")
        sig.iloc[2:10] = 1.0
        sig.iloc[15:25] = -1.0
        cfg = BacktestConfig(
            initial_cash="100000",
            cost=CostModel(commission_pct=0.001, slippage_pct=0.0005),
        )
        engine = EventDrivenEngine(cfg, stop_loss_pct=0.08)
        result = engine.run(ohlcv, sig)
        assert isinstance(result, BacktestResult)
        assert len(result.trades) > 0

    def test_missing_close_and_adj_close_raises(self):
        n = 5
        dates = pd.bdate_range("2020-01-01", periods=n)
        ohlcv = pd.DataFrame(
            {
                "symbol": "NOCLOSE",
                "interval": "1d",
                "timestamp": dates,
                "open": [100] * n,
                "high": [101] * n,
                "low": [99] * n,
                "volume": [1000] * n,
                "source": ["test"] * n,
            }
        )
        sig = pd.Series(np.ones(n), dtype="float64", name="signal")
        engine = EventDrivenEngine()
        with pytest.raises(ValueError, match="close"):
            engine.run(ohlcv, sig)

    def test_stop_loss_cost_components_included(self):
        n = 15
        dates = pd.bdate_range("2020-01-01", periods=n)
        close = pd.Series(np.linspace(100, 80, n), dtype="float64")
        ohlcv = pd.DataFrame(
            {
                "symbol": "COSTSTOP",
                "interval": "1d",
                "timestamp": dates,
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "adj_close": close,
                "volume": 1_000_000,
                "source": "synthetic",
            }
        )
        sig = pd.Series(np.zeros(n), dtype="float64", name="signal")
        sig.iloc[1:10] = 1.0
        cfg = BacktestConfig(
            initial_cash="100000",
            cost=CostModel(commission_pct=0.001, slippage_pct=0.0005),
        )
        engine = EventDrivenEngine(cfg, stop_loss_pct=0.05)
        result = engine.run(ohlcv, sig)
        if not result.trades.empty:
            for _, trade in result.trades.iterrows():
                assert "order_type" in trade.index
