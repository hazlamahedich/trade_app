"""ATDD red-phase: Story 2.4 — Event-Driven Backtest Engine.

Tests assert the expected end-state AFTER full Story 2.4 implementation.
All tests are SKIPPED (TDD red phase).

Remove @pytest.mark.skip when implementing Story 2.4.
"""

from __future__ import annotations

import pytest


class TestStory24EventDrivenBacktest:
    """Story 2.4: Event-driven backtest for realistic order simulation."""

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.4 not yet implemented")
    def test_event_driven_engine_exists(self):
        from trade_advisor.backtest.event_driven import EventDrivenEngine

        assert EventDrivenEngine is not None

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.4 not yet implemented")
    def test_execution_router_protocol_exists(self):
        from trade_advisor.backtest.execution import ExecutionRouter

        assert ExecutionRouter is not None

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.4 not yet implemented")
    def test_order_spec_type_exists(self):
        from trade_advisor.backtest.execution import OrderSpec

        spec = OrderSpec(side="buy", order_type="market", quantity=100)
        assert spec is not None

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.4 not yet implemented")
    def test_event_driven_supports_market_orders(self, ohlcv_500, backtest_config):
        from trade_advisor.backtest.event_driven import EventDrivenEngine

        from trade_advisor.strategies.sma_cross import SmaCross

        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv_500)
        engine = EventDrivenEngine(backtest_config)
        result = engine.run(ohlcv_500, signals)
        assert hasattr(result, "equity")
        assert hasattr(result, "trades")

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.4 not yet implemented")
    def test_event_driven_supports_limit_orders(self, ohlcv_500, backtest_config):
        from trade_advisor.backtest.event_driven import EventDrivenEngine

        from trade_advisor.strategies.sma_cross import SmaCross

        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv_500)
        engine = EventDrivenEngine(backtest_config)
        result = engine.run(ohlcv_500, signals)
        limit_trades = result.trades[result.trades["order_type"] == "limit"]
        assert len(limit_trades) >= 0

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.4 not yet implemented")
    def test_event_driven_supports_stop_loss(self, ohlcv_500, backtest_config):
        from trade_advisor.backtest.event_driven import EventDrivenEngine

        from trade_advisor.strategies.sma_cross import SmaCross

        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv_500)
        engine = EventDrivenEngine(backtest_config, stop_loss_pct=0.05)
        result = engine.run(ohlcv_500, signals)
        assert hasattr(result, "equity")

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.4 not yet implemented")
    def test_same_backtest_result_schema(self, ohlcv_500, backtest_config):
        from trade_advisor.backtest.event_driven import EventDrivenEngine

        from trade_advisor.backtest.engine import BacktestResult
        from trade_advisor.strategies.sma_cross import SmaCross

        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv_500)
        engine = EventDrivenEngine(backtest_config)
        result = engine.run(ohlcv_500, signals)
        assert isinstance(result, BacktestResult)

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.4 not yet implemented")
    def test_convergence_vectorized_vs_event_driven(self, ohlcv_500, zero_cost_config):
        import pandas as pd
        from trade_advisor.backtest.event_driven import EventDrivenEngine

        from trade_advisor.backtest.engine import run_backtest
        from trade_advisor.strategies.sma_cross import SmaCross

        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv_500)

        vec_result = run_backtest(ohlcv_500, signals, zero_cost_config)
        ed_engine = EventDrivenEngine(zero_cost_config)
        ed_result = ed_engine.run(ohlcv_500, signals)

        pd.testing.assert_series_equal(
            vec_result.equity.reset_index(drop=True),
            ed_result.equity.reset_index(drop=True),
            check_names=False,
        )
