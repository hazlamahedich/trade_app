"""ATDD tests: Story 2.3 — Vectorized Backtest Engine.

Tests assert the expected end-state after full Story 2.3 implementation.
"""

from __future__ import annotations

import time

import pandas as pd

from trade_advisor.backtest.engine import run_backtest
from trade_advisor.backtest.protocols import BacktestEngine
from trade_advisor.backtest.vectorized import VectorizedEngine, run_vectorized_backtest
from trade_advisor.config import BacktestConfig, CostModel
from trade_advisor.strategies.sma_cross import SmaCross


class TestStory23VectorizedBacktest:
    """Story 2.3: Fast vectorized backtest execution."""

    def test_vectorized_backtest_produces_result(self, ohlcv_500, backtest_config):
        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv_500)
        result = run_backtest(ohlcv_500, signals, backtest_config)
        assert hasattr(result, "equity")
        assert hasattr(result, "returns")
        assert hasattr(result, "positions")
        assert hasattr(result, "trades")
        assert hasattr(result, "config")

    def test_equity_curve_starts_at_initial_cash(self, ohlcv_500, backtest_config):
        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv_500)
        result = run_backtest(ohlcv_500, signals, backtest_config)
        assert float(result.equity.iloc[0]) == float(backtest_config.initial_cash)

    def test_backtest_result_contains_trade_list(self, ohlcv_500, backtest_config):
        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv_500)
        result = run_backtest(ohlcv_500, signals, backtest_config)
        assert "entry_ts" in result.trades.columns
        assert "exit_ts" in result.trades.columns
        assert "side" in result.trades.columns
        assert "entry_price" in result.trades.columns
        assert "exit_price" in result.trades.columns
        assert "return" in result.trades.columns
        assert "weight" in result.trades.columns

    def test_performance_10yr_50_symbols_under_10s(self, ohlcv_50_symbols):
        strategy = SmaCross(fast=20, slow=50)
        config = BacktestConfig(cost=CostModel(commission_pct=0.001))

        start = time.monotonic()
        for df in ohlcv_50_symbols:
            signals = strategy.generate_signals(df)
            run_vectorized_backtest(df, signals, config)
        elapsed = time.monotonic() - start
        assert elapsed < 10.0, f"50-symbol backtest took {elapsed:.1f}s, exceeds 10s NFR-P1"

    def test_deterministic_identical_config_same_equity(self, ohlcv_500, zero_cost_config):
        strategy = SmaCross(fast=20, slow=50)
        s1 = strategy.generate_signals(ohlcv_500)
        result1 = run_backtest(ohlcv_500, s1, zero_cost_config)

        strategy2 = SmaCross(fast=20, slow=50)
        s2 = strategy2.generate_signals(ohlcv_500)
        result2 = run_backtest(ohlcv_500, s2, zero_cost_config)

        pd.testing.assert_series_equal(result1.equity, result2.equity)

    def test_backtest_engine_protocol_exists(self):
        assert BacktestEngine is not None

    def test_vectorized_engine_satisfies_protocol(self):
        assert isinstance(VectorizedEngine(), BacktestEngine)

    def test_to_frame_produces_dataframe(self, ohlcv_500, backtest_config):
        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv_500)
        result = run_backtest(ohlcv_500, signals, backtest_config)
        df = result.to_frame()
        assert "equity" in df.columns
        assert "position" in df.columns
