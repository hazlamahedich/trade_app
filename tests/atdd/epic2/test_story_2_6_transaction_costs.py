"""ATDD green-phase: Story 2.6 — Transaction Cost Engine.

Tests assert the expected end-state AFTER full Story 2.6 implementation.
"""

from __future__ import annotations


class TestStory26TransactionCosts:
    """Story 2.6: Realistic transaction costs applied to backtests."""

    def test_cost_module_exists(self):
        from trade_advisor.backtest.costs import CostEngine

        assert CostEngine is not None

    def test_fixed_per_trade_cost(self, ohlcv_500, backtest_config):
        from trade_advisor.backtest.costs import CostEngine

        engine = CostEngine(fixed_per_trade=1.0)
        cost = engine.compute(trade_notional=10000.0)
        assert cost == 1.0

    def test_basis_points_cost(self):
        from trade_advisor.backtest.costs import CostEngine

        engine = CostEngine(bps=5.0)
        cost = engine.compute(trade_notional=100000.0)
        assert cost == 50.0

    def test_slippage_as_atr_fraction(self, ohlcv_500):
        from trade_advisor.backtest.costs import CostEngine

        engine = CostEngine(slippage_atr_fraction=0.1)
        atr = ohlcv_500["high"].iloc[:20].max() - ohlcv_500["low"].iloc[:20].min()
        price = float(ohlcv_500["close"].iloc[0])
        cost = engine.compute(trade_notional=100000.0, atr=atr, price=price)
        assert cost > 0

    def test_costs_visible_in_trade_detail(self, ohlcv_500, backtest_config):
        from trade_advisor.backtest.costs import apply_costs
        from trade_advisor.backtest.engine import run_backtest
        from trade_advisor.strategies.sma_cross import SmaCross

        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv_500)
        result = run_backtest(ohlcv_500, signals, backtest_config)
        result_with_costs = apply_costs(result, backtest_config.cost)
        assert "cost" in result_with_costs.trades.columns

    def test_reality_check_mode(self):
        from trade_advisor.backtest.costs import CostEngine

        engine = CostEngine.reality_check()
        assert engine.fixed_per_trade > 0
        assert engine.bps > 0

    def test_cost_sensitivity_toggle(self, ohlcv_500):
        from trade_advisor.backtest.costs import CostEngine

        base = CostEngine(bps=5.0)
        doubled = base.sensitivity(2.0)
        assert doubled.bps == 10.0

    def test_forex_overnight_carry_cost(self):
        from trade_advisor.backtest.costs import forex_carry_cost

        cost = forex_carry_cost(
            position_notional=100000.0,
            swap_points=0.5,
            days=10,
        )
        assert cost > 0
