from __future__ import annotations

import pytest


class TestCostEngine:
    def test_cost_engine_zero_cost(self):
        from trade_advisor.backtest.costs import CostEngine

        engine = CostEngine()
        assert engine.compute(trade_notional=100000.0) == 0.0

    def test_cost_engine_fixed_per_trade(self):
        from trade_advisor.backtest.costs import CostEngine

        engine = CostEngine(fixed_per_trade=1.0)
        cost = engine.compute(trade_notional=10000.0)
        assert cost == 1.0

    def test_cost_engine_bps(self):
        from trade_advisor.backtest.costs import CostEngine

        engine = CostEngine(bps=5.0)
        cost = engine.compute(trade_notional=100000.0)
        assert cost == 50.0

    def test_cost_engine_combined(self):
        from trade_advisor.backtest.costs import CostEngine

        engine = CostEngine(fixed_per_trade=1.0, bps=10.0)
        cost = engine.compute(trade_notional=10000.0)
        assert cost == 1.0 + 10000.0 * (10.0 / 10_000)

    def test_cost_engine_slippage_atr_position_scaled(self):
        from trade_advisor.backtest.costs import CostEngine

        engine = CostEngine(slippage_atr_fraction=0.1)
        atr = 2.5
        price = 100.0
        notional = 100000.0
        cost = engine.compute(trade_notional=notional, atr=atr, price=price)
        shares = notional / price
        expected = 0.1 * atr * shares
        assert cost == pytest.approx(expected)

    def test_cost_engine_slippage_no_atr_ignores(self):
        from trade_advisor.backtest.costs import CostEngine

        engine = CostEngine(slippage_atr_fraction=0.1)
        cost = engine.compute(trade_notional=100000.0, atr=None)
        assert cost == 0.0

    def test_cost_engine_slippage_requires_price(self):
        from trade_advisor.backtest.costs import CostEngine

        engine = CostEngine(slippage_atr_fraction=0.1)
        with pytest.raises(ValueError, match="price is required"):
            engine.compute(trade_notional=100000.0, atr=2.5, price=None)

    def test_cost_engine_slippage_doubles_with_notional(self):
        from trade_advisor.backtest.costs import CostEngine

        engine = CostEngine(slippage_atr_fraction=0.1)
        cost_50k = engine.compute(trade_notional=50000.0, atr=2.5, price=100.0)
        cost_100k = engine.compute(trade_notional=100000.0, atr=2.5, price=100.0)
        assert cost_100k == pytest.approx(cost_50k * 2.0)

    def test_cost_engine_slippage_zero_price(self):
        from trade_advisor.backtest.costs import CostEngine

        engine = CostEngine(slippage_atr_fraction=0.1)
        cost = engine.compute(trade_notional=100000.0, atr=2.5, price=0.0)
        assert cost == 0.0

    def test_cost_engine_reality_check(self):
        from trade_advisor.backtest.costs import CostEngine

        engine = CostEngine.reality_check()
        assert engine.fixed_per_trade > 0
        assert engine.bps > 0
        assert engine.slippage_atr_fraction > 0

    def test_cost_engine_sensitivity_doubles_all(self):
        from trade_advisor.backtest.costs import CostEngine

        base = CostEngine(fixed_per_trade=1.0, bps=5.0, slippage_atr_fraction=0.1)
        doubled = base.sensitivity(2.0)
        assert doubled.fixed_per_trade == 2.0
        assert doubled.bps == 10.0
        assert doubled.slippage_atr_fraction == pytest.approx(0.2)

    def test_cost_engine_sensitivity_half(self):
        from trade_advisor.backtest.costs import CostEngine

        base = CostEngine(fixed_per_trade=2.0, bps=10.0, slippage_atr_fraction=0.2)
        halved = base.sensitivity(0.5)
        assert halved.fixed_per_trade == 1.0
        assert halved.bps == 5.0
        assert halved.slippage_atr_fraction == pytest.approx(0.1)

    def test_cost_engine_negative_field_raises(self):
        from trade_advisor.backtest.costs import CostEngine

        with pytest.raises(ValueError):
            CostEngine(fixed_per_trade=-1.0)

    def test_cost_engine_negative_notional_abs(self):
        from trade_advisor.backtest.costs import CostEngine

        engine = CostEngine(bps=5.0)
        assert engine.compute(trade_notional=-100000.0) == 50.0

    def test_sensitivity_negative_factor_raises(self):
        from trade_advisor.backtest.costs import CostEngine

        engine = CostEngine(bps=5.0)
        with pytest.raises(ValueError, match="sensitivity factor must be >= 0"):
            engine.sensitivity(-1.0)


class TestFactoryMapping:
    def test_from_model_basic_mapping(self):
        from trade_advisor.backtest.costs import CostEngine
        from trade_advisor.core.config import CostModel

        model = CostModel(commission_pct=0.001, slippage_pct=0.0005, commission_fixed=1.0)
        engine = CostEngine.from_model(model)
        assert engine.fixed_per_trade == 1.0
        total_bps = (0.001 + 0.0005) * 10_000
        assert engine.bps == pytest.approx(total_bps)

    def test_from_model_zero_config(self):
        from trade_advisor.backtest.costs import CostEngine
        from trade_advisor.core.config import CostModel

        model = CostModel(commission_pct=0.0, slippage_pct=0.0)
        engine = CostEngine.from_model(model)
        assert engine.fixed_per_trade == 0.0
        assert engine.bps == 0.0

    def test_from_model_preserves_fixed(self):
        from trade_advisor.backtest.costs import CostEngine
        from trade_advisor.core.config import CostModel

        model = CostModel(commission_fixed=5.0)
        engine = CostEngine.from_model(model)
        assert engine.fixed_per_trade == 5.0

    def test_cost_model_commission_fixed_no_error(self):
        from trade_advisor.core.config import CostModel

        model = CostModel(commission_fixed=1.0)
        assert model.commission_fixed == 1.0

    def test_default_cost_model_has_zero_slippage(self):
        from trade_advisor.core.config import CostModel

        model = CostModel()
        assert model.slippage_pct == 0.0


class TestForexCarryCost:
    def test_forex_carry_cost_basic(self):
        from trade_advisor.backtest.costs import forex_carry_cost

        cost = forex_carry_cost(100000.0, 0.5, 10)
        expected = abs(100000.0) * 0.5 * 10 / 10_000
        assert cost == pytest.approx(expected)

    def test_forex_carry_cost_zero_days(self):
        from trade_advisor.backtest.costs import forex_carry_cost

        assert forex_carry_cost(100000.0, 0.5, 0) == 0.0

    def test_forex_carry_cost_negative_notional(self):
        from trade_advisor.backtest.costs import forex_carry_cost

        cost = forex_carry_cost(-100000.0, 0.5, 10)
        assert cost == pytest.approx(abs(-100000.0) * 0.5 * 10 / 10_000)

    def test_forex_carry_cost_negative_swap_raises(self):
        from trade_advisor.backtest.costs import forex_carry_cost

        with pytest.raises(ValueError, match="swap_points must be >= 0"):
            forex_carry_cost(100000.0, -0.5, 10)

    def test_forex_carry_cost_negative_days_raises(self):
        from trade_advisor.backtest.costs import forex_carry_cost

        with pytest.raises(ValueError, match="days must be >= 0"):
            forex_carry_cost(100000.0, 0.5, -1)


class TestApplyCosts:
    def test_apply_costs_adds_column(self):
        from tests.helpers import _synthetic_ohlcv
        from trade_advisor.backtest.costs import apply_costs
        from trade_advisor.backtest.engine import run_backtest
        from trade_advisor.core.config import BacktestConfig, CostModel
        from trade_advisor.strategies.sma_cross import SmaCross

        ohlcv = _synthetic_ohlcv(n=200, seed=42)
        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv)
        cfg = BacktestConfig(initial_cash="100000", cost=CostModel(commission_pct=0.001))
        result = run_backtest(ohlcv, signals, cfg)
        result_with_costs = apply_costs(result, cfg.cost)
        assert "cost" in result_with_costs.trades.columns
        assert result_with_costs.trades["cost"].dtype == "float64"

    def test_apply_costs_non_negative(self):
        from tests.helpers import _synthetic_ohlcv
        from trade_advisor.backtest.costs import apply_costs
        from trade_advisor.backtest.engine import run_backtest
        from trade_advisor.core.config import BacktestConfig, CostModel
        from trade_advisor.strategies.sma_cross import SmaCross

        ohlcv = _synthetic_ohlcv(n=200, seed=42)
        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv)
        cfg = BacktestConfig(initial_cash="100000", cost=CostModel(commission_pct=0.001))
        result = run_backtest(ohlcv, signals, cfg)
        result_with_costs = apply_costs(result, cfg.cost)
        assert (result_with_costs.trades["cost"] >= 0).all()

    def test_apply_costs_zero_config_zero_column(self):
        from tests.helpers import _synthetic_ohlcv
        from trade_advisor.backtest.costs import apply_costs
        from trade_advisor.backtest.engine import run_backtest
        from trade_advisor.core.config import BacktestConfig, CostModel
        from trade_advisor.strategies.sma_cross import SmaCross

        ohlcv = _synthetic_ohlcv(n=200, seed=42)
        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv)
        cfg = BacktestConfig(
            initial_cash="100000", cost=CostModel(commission_pct=0.0, slippage_pct=0.0)
        )
        result = run_backtest(ohlcv, signals, cfg)
        result_with_costs = apply_costs(result, cfg.cost)
        if not result_with_costs.trades.empty:
            assert (result_with_costs.trades["cost"] == 0.0).all()

    def test_apply_costs_type_error(self):
        from trade_advisor.backtest.costs import apply_costs
        from trade_advisor.core.config import CostModel

        with pytest.raises(TypeError, match="BacktestResult"):
            apply_costs("not_a_result", CostModel())

    def test_apply_costs_missing_columns_error(self):
        import pandas as pd

        from trade_advisor.backtest.costs import apply_costs
        from trade_advisor.backtest.engine import BacktestResult
        from trade_advisor.core.config import BacktestConfig, CostModel

        cfg = BacktestConfig()
        bad_trades = pd.DataFrame(
            {"entry_ts": [pd.Timestamp("2024-01-01")], "exit_ts": [pd.Timestamp("2024-01-02")]}
        )
        result = BacktestResult(
            equity=pd.Series([100000.0], name="equity"),
            returns=pd.Series([0.0], name="returns"),
            positions=pd.Series([0.0], name="position"),
            trades=bad_trades,
            config=cfg,
            meta={},
        )
        with pytest.raises(ValueError, match="missing required columns"):
            apply_costs(result, CostModel())


class TestDeterminismConvergence:
    def test_cost_engine_determinism(self):
        from trade_advisor.backtest.costs import CostEngine

        engine = CostEngine(fixed_per_trade=1.0, bps=5.0, slippage_atr_fraction=0.1)
        results = [engine.compute(100000.0, atr=2.5, price=100.0) for _ in range(10)]
        assert all(r == results[0] for r in results)

    def test_backward_compat_zero_cost(self):
        from tests.helpers import _synthetic_ohlcv
        from trade_advisor.backtest.engine import run_backtest
        from trade_advisor.core.config import BacktestConfig, CostModel
        from trade_advisor.strategies.sma_cross import SmaCross

        ohlcv = _synthetic_ohlcv(n=200, seed=42)
        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv)
        cfg_old = BacktestConfig(
            initial_cash="100000", cost=CostModel(commission_pct=0.0, slippage_pct=0.0)
        )
        result = run_backtest(ohlcv, signals, cfg_old)
        eq_old = result.equity.values

        cfg_new = BacktestConfig(
            initial_cash="100000", cost=CostModel(commission_pct=0.0, slippage_pct=0.0)
        )
        result_new = run_backtest(ohlcv, signals, cfg_new)
        eq_new = result_new.equity.values

        import numpy as np

        np.testing.assert_array_equal(eq_old, eq_new)

    def test_default_config_zero_cost(self):
        from tests.helpers import _synthetic_ohlcv
        from trade_advisor.backtest.engine import run_backtest
        from trade_advisor.core.config import BacktestConfig
        from trade_advisor.strategies.sma_cross import SmaCross

        ohlcv = _synthetic_ohlcv(n=200, seed=42)
        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv)
        cfg_default = BacktestConfig(initial_cash="100000")
        result_default = run_backtest(ohlcv, signals, cfg_default)
        cfg_zero = BacktestConfig(
            initial_cash="100000",
            cost=__import__("trade_advisor.core.config", fromlist=["CostModel"]).CostModel(
                commission_pct=0.0, slippage_pct=0.0
            ),
        )
        result_zero = run_backtest(ohlcv, signals, cfg_zero)

        import numpy as np

        np.testing.assert_array_equal(result_default.equity.values, result_zero.equity.values)

    def test_convergence_with_costs(self):
        import numpy as np

        from tests.helpers import _synthetic_ohlcv
        from trade_advisor.backtest.engine import run_backtest
        from trade_advisor.backtest.event_driven import EventDrivenEngine
        from trade_advisor.core.config import BacktestConfig, CostModel
        from trade_advisor.strategies.sma_cross import SmaCross

        ohlcv = _synthetic_ohlcv(n=200, seed=42)
        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv)
        cfg = BacktestConfig(
            initial_cash="100000", cost=CostModel(commission_pct=0.001, slippage_pct=0.0005)
        )

        vec_result = run_backtest(ohlcv, signals, cfg)
        ed_engine = EventDrivenEngine(config=cfg)
        ed_result = ed_engine.run(ohlcv, signals, cfg)

        np.testing.assert_allclose(
            vec_result.equity.values,
            ed_result.equity.values,
            atol=1e-12,
            rtol=1e-9,
        )

    def test_convergence_zero_cost_unchanged(self):
        import numpy as np

        from tests.helpers import _synthetic_ohlcv
        from trade_advisor.backtest.engine import run_backtest
        from trade_advisor.backtest.event_driven import EventDrivenEngine
        from trade_advisor.core.config import BacktestConfig, CostModel
        from trade_advisor.strategies.sma_cross import SmaCross

        ohlcv = _synthetic_ohlcv(n=200, seed=42)
        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv)
        cfg = BacktestConfig(
            initial_cash="100000", cost=CostModel(commission_pct=0.0, slippage_pct=0.0)
        )

        vec_result = run_backtest(ohlcv, signals, cfg)
        ed_engine = EventDrivenEngine(config=cfg)
        ed_result = ed_engine.run(ohlcv, signals, cfg)

        np.testing.assert_array_equal(vec_result.equity.values, ed_result.equity.values)


class TestIntegration:
    def test_vectorized_with_cost_engine(self):
        from tests.helpers import _synthetic_ohlcv
        from trade_advisor.backtest.engine import run_backtest
        from trade_advisor.core.config import BacktestConfig, CostModel
        from trade_advisor.strategies.sma_cross import SmaCross

        ohlcv = _synthetic_ohlcv(n=200, seed=42)
        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv)

        cfg_zero = BacktestConfig(
            initial_cash="100000", cost=CostModel(commission_pct=0.0, slippage_pct=0.0)
        )
        result_zero = run_backtest(ohlcv, signals, cfg_zero)

        cfg_cost = BacktestConfig(
            initial_cash="100000", cost=CostModel(commission_pct=0.001, slippage_pct=0.0005)
        )
        result_cost = run_backtest(ohlcv, signals, cfg_cost)

        assert result_cost.equity.iloc[-1] <= result_zero.equity.iloc[-1] + 1e-10

    def test_event_driven_with_cost_engine(self):
        from tests.helpers import _synthetic_ohlcv
        from trade_advisor.backtest.event_driven import EventDrivenEngine
        from trade_advisor.core.config import BacktestConfig, CostModel
        from trade_advisor.strategies.sma_cross import SmaCross

        ohlcv = _synthetic_ohlcv(n=200, seed=42)
        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv)

        cfg_zero = BacktestConfig(
            initial_cash="100000", cost=CostModel(commission_pct=0.0, slippage_pct=0.0)
        )
        ed_zero = EventDrivenEngine(config=cfg_zero)
        result_zero = ed_zero.run(ohlcv, signals, cfg_zero)

        cfg_cost = BacktestConfig(
            initial_cash="100000", cost=CostModel(commission_pct=0.001, slippage_pct=0.0005)
        )
        ed_cost = EventDrivenEngine(config=cfg_cost)
        result_cost = ed_cost.run(ohlcv, signals, cfg_cost)

        assert result_cost.equity.iloc[-1] <= result_zero.equity.iloc[-1] + 1e-10

    def test_equity_after_costs_leq_before(self):
        from tests.helpers import _synthetic_ohlcv
        from trade_advisor.backtest.engine import run_backtest
        from trade_advisor.core.config import BacktestConfig, CostModel
        from trade_advisor.strategies.sma_cross import SmaCross

        ohlcv = _synthetic_ohlcv(n=200, seed=42)
        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv)

        cfg_zero = BacktestConfig(
            initial_cash="100000", cost=CostModel(commission_pct=0.0, slippage_pct=0.0)
        )
        result_zero = run_backtest(ohlcv, signals, cfg_zero)

        cfg_cost = BacktestConfig(
            initial_cash="100000", cost=CostModel(commission_pct=0.001, slippage_pct=0.0005)
        )
        result_cost = run_backtest(ohlcv, signals, cfg_cost)

        import numpy as np

        assert np.all(result_cost.equity.values <= result_zero.equity.values + 1e-10)


class TestComputeBreakdown:
    def test_breakdown_commission_slippage(self):
        from trade_advisor.backtest.costs import CostEngine

        engine = CostEngine(fixed_per_trade=1.0, bps=10.0, slippage_atr_fraction=0.1)
        breakdown = engine.compute_breakdown(trade_notional=10000.0, atr=2.5, price=100.0)
        assert "commission" in breakdown
        assert "slippage" in breakdown
        assert "total" in breakdown
        assert breakdown["commission"] == 1.0 + 10000.0 * (10.0 / 10_000)
        shares = 10000.0 / 100.0
        assert breakdown["slippage"] == pytest.approx(0.1 * 2.5 * shares)
        assert breakdown["total"] == pytest.approx(breakdown["commission"] + breakdown["slippage"])

    def test_breakdown_zero_cost(self):
        from trade_advisor.backtest.costs import CostEngine

        engine = CostEngine()
        breakdown = engine.compute_breakdown(trade_notional=100000.0)
        assert breakdown["commission"] == 0.0
        assert breakdown["slippage"] == 0.0
        assert breakdown["total"] == 0.0

    def test_breakdown_values_match_compute(self):
        from trade_advisor.backtest.costs import CostEngine

        engine = CostEngine(fixed_per_trade=1.0, bps=5.0, slippage_atr_fraction=0.05)
        total = engine.compute(trade_notional=50000.0, atr=3.0, price=50.0)
        breakdown = engine.compute_breakdown(trade_notional=50000.0, atr=3.0, price=50.0)
        assert breakdown["total"] == pytest.approx(total)


class TestDivisionByZeroGuard:
    def test_equity_zero_initial_cash_raises(self):
        import pandas as pd

        from trade_advisor.backtest._equity import compute_equity_curve
        from trade_advisor.backtest.costs import CostEngine

        sig = pd.Series([1.0, 0.0, -1.0])
        ret = pd.Series([0.01, -0.005, 0.02])
        engine = CostEngine(fixed_per_trade=1.0)
        with pytest.raises(ValueError, match="initial_cash must be > 0"):
            compute_equity_curve(sig, ret, initial_cash=0.0, cost_engine=engine)
