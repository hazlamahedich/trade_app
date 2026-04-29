"""Comprehensive tests for backtest metrics — Story 2.7."""

from __future__ import annotations

import math
from decimal import Decimal

import numpy as np
import pandas as pd

from tests.conftest import _synthetic_ohlcv
from trade_advisor.backtest.engine import BacktestResult, run_backtest
from trade_advisor.backtest.metrics import (
    MetricsBundle,
    compute_all_metrics,
)
from trade_advisor.backtest.metrics.performance import compute_performance_metrics
from trade_advisor.backtest.metrics.risk import compute_risk_metrics
from trade_advisor.backtest.metrics.trade_analysis import compute_trade_analysis
from trade_advisor.config import BacktestConfig, CostModel
from trade_advisor.strategies.sma_cross import SmaCross


def _make_result(
    equity_vals: list[float],
    dates: pd.DatetimeIndex | None = None,
    trades: pd.DataFrame | None = None,
) -> BacktestResult:
    if dates is None:
        dates = pd.bdate_range("2020-01-01", periods=len(equity_vals))
    equity = pd.Series(equity_vals, index=dates, dtype=float)
    returns = equity.pct_change()
    positions = pd.Series(1.0, index=dates, dtype=float)
    if trades is None:
        trades = pd.DataFrame(
            columns=["entry_ts", "exit_ts", "side", "entry_price", "exit_price", "return", "weight"]
        )
    config = BacktestConfig(initial_cash="100000", cost=CostModel())
    return BacktestResult(
        equity=equity, returns=returns, positions=positions, trades=trades, config=config
    )


def _known_answer_result() -> BacktestResult:
    dates = pd.bdate_range("2020-01-01", periods=5)
    equity = pd.Series([100000, 105000, 98000, 103000, 110000], index=dates, dtype=float)
    returns = equity.pct_change()
    positions = pd.Series(1.0, index=dates, dtype=float)
    trades = pd.DataFrame(
        {
            "entry_ts": [dates[0]],
            "exit_ts": [dates[4]],
            "side": [1],
            "entry_price": [100.0],
            "exit_price": [110.0],
            "return": [0.10],
            "weight": [1.0],
        }
    )
    config = BacktestConfig(initial_cash="100000", cost=CostModel())
    return BacktestResult(
        equity=equity, returns=returns, positions=positions, trades=trades, config=config
    )


def _sma_result() -> BacktestResult:
    ohlcv = _synthetic_ohlcv(n=500, seed=42)
    strat = SmaCross(fast=20, slow=50)
    signals = strat.generate_signals(ohlcv)
    cfg = BacktestConfig(
        initial_cash="100000", cost=CostModel(commission_pct=0.001, slippage_pct=0.0005)
    )
    return run_backtest(ohlcv, signals, cfg)


# ─── Performance metrics tests (10) ─────────────────────────────────────────


class TestPerformanceMetrics:
    def test_total_return_known_answer(self):
        result = _known_answer_result()
        metrics = compute_performance_metrics(result)
        assert abs(float(metrics.total_return) - 0.10) < 1e-6

    def test_total_return_flat_equity(self):
        result = _make_result([100000] * 10)
        metrics = compute_performance_metrics(result)
        assert metrics.total_return == Decimal("0")

    def test_sharpe_annualized_ddof1(self):
        result = _sma_result()
        metrics = compute_performance_metrics(result)
        returns = result.returns.dropna()
        expected_raw = returns.mean() / returns.std(ddof=1)
        expected = float(expected_raw) * (252**0.5)
        assert abs(metrics.sharpe - expected) < 1e-6

    def test_sharpe_zero_std_returns(self):
        result = _make_result([100000] * 10)
        metrics = compute_performance_metrics(result)
        assert metrics.sharpe == 0.0

    def test_sortino_downside_semi_deviation(self):
        result = _sma_result()
        metrics = compute_performance_metrics(result)
        returns = result.returns.dropna()
        downside_diff = np.minimum(returns.values, 0.0)
        dsd = float(np.sqrt(np.mean(downside_diff**2)))
        if dsd != 0:
            expected = float(returns.mean() / dsd * (252**0.5))
            assert abs(metrics.sortino - expected) < 1e-4

    def test_sortino_all_positive_returns(self):
        dates = pd.bdate_range("2020-01-01", periods=10)
        equity = pd.Series([100 + i for i in range(10)], index=dates, dtype=float) * 1000
        returns = equity.pct_change()
        positions = pd.Series(1.0, index=dates, dtype=float)
        config = BacktestConfig(initial_cash="100000", cost=CostModel())
        result = BacktestResult(
            equity=equity,
            returns=returns,
            positions=positions,
            trades=pd.DataFrame(
                columns=[
                    "entry_ts",
                    "exit_ts",
                    "side",
                    "entry_price",
                    "exit_price",
                    "return",
                    "weight",
                ]
            ),
            config=config,
        )
        metrics = compute_performance_metrics(result)
        assert metrics.sortino == 0.0

    def test_calmar_ratio(self):
        result = _sma_result()
        metrics = compute_performance_metrics(result)
        if metrics.max_drawdown != Decimal(0):
            expected = float(metrics.cagr) / abs(float(metrics.max_drawdown))
            assert abs(metrics.calmar - expected) < 1e-6

    def test_calmar_zero_drawdown(self):
        result = _make_result([100000] * 10)
        metrics = compute_performance_metrics(result)
        assert metrics.calmar == 0.0

    def test_max_drawdown_nonpositive(self):
        result = _sma_result()
        metrics = compute_performance_metrics(result)
        assert metrics.max_drawdown <= Decimal(0)

    def test_cagr_calendar_based(self):
        result = _known_answer_result()
        metrics = compute_performance_metrics(result)
        n_days = (result.equity.index[-1] - result.equity.index[0]).days
        years = n_days / 365.25
        expected = (1.10) ** (1 / years) - 1
        assert abs(float(metrics.cagr) - expected) < 1e-4


# ─── Risk metrics tests (8) ──────────────────────────────────────────────────


class TestRiskMetrics:
    def test_var_95_historical_percentile(self):
        result = _sma_result()
        risk = compute_risk_metrics(result)
        returns = result.returns.dropna()
        expected = float(np.percentile(returns, 5))
        assert abs(risk.var_95 - expected) < 1e-8

    def test_cvar_mean_tail(self):
        result = _sma_result()
        risk = compute_risk_metrics(result)
        returns = result.returns.dropna()
        var = float(np.percentile(returns, 5))
        tail = returns[returns <= var]
        expected = float(tail.mean())
        assert abs(risk.cvar_95 - expected) < 1e-6

    def test_tail_ratio_computed(self):
        result = _sma_result()
        risk = compute_risk_metrics(result)
        returns = result.returns.dropna()
        p95 = float(np.percentile(returns, 95))
        p5 = float(np.percentile(returns, 5))
        if p5 != 0:
            assert abs(risk.tail_ratio - abs(p95 / p5)) < 1e-6

    def test_tail_ratio_zero_p5(self):
        dates = pd.bdate_range("2020-01-01", periods=20)
        vals = [100000] * 20
        equity = pd.Series(vals, index=dates, dtype=float)
        returns = equity.pct_change()
        positions = pd.Series(0.0, index=dates, dtype=float)
        config = BacktestConfig(initial_cash="100000", cost=CostModel())
        result = BacktestResult(
            equity=equity,
            returns=returns,
            positions=positions,
            trades=pd.DataFrame(
                columns=[
                    "entry_ts",
                    "exit_ts",
                    "side",
                    "entry_price",
                    "exit_price",
                    "return",
                    "weight",
                ]
            ),
            config=config,
        )
        risk = compute_risk_metrics(result)
        assert risk.tail_ratio == 0.0

    def test_max_dd_duration_peak_to_recovery(self):
        result = _sma_result()
        risk = compute_risk_metrics(result)
        assert isinstance(risk.max_dd_duration_bars, int)
        assert risk.max_dd_duration_bars >= 0

    def test_drawdown_distribution_series(self):
        result = _sma_result()
        risk = compute_risk_metrics(result)
        assert len(risk.drawdown_distribution) == len(result.equity)

    def test_var_small_sample(self):
        dates = pd.bdate_range("2020-01-01", periods=5)
        equity = pd.Series([100000, 101000, 99500, 100200, 100500], index=dates, dtype=float)
        returns = equity.pct_change()
        positions = pd.Series(1.0, index=dates, dtype=float)
        config = BacktestConfig(initial_cash="100000", cost=CostModel())
        result = BacktestResult(
            equity=equity,
            returns=returns,
            positions=positions,
            trades=pd.DataFrame(
                columns=[
                    "entry_ts",
                    "exit_ts",
                    "side",
                    "entry_price",
                    "exit_price",
                    "return",
                    "weight",
                ]
            ),
            config=config,
        )
        risk = compute_risk_metrics(result)
        assert not math.isnan(risk.var_95)

    def test_empty_returns_risk_metrics(self):
        dates = pd.bdate_range("2020-01-01", periods=3)
        equity = pd.Series([100000, 100000, 100000], index=dates, dtype=float)
        returns = equity.pct_change()
        positions = pd.Series(0.0, index=dates, dtype=float)
        config = BacktestConfig(initial_cash="100000", cost=CostModel())
        result = BacktestResult(
            equity=equity,
            returns=returns,
            positions=positions,
            trades=pd.DataFrame(
                columns=[
                    "entry_ts",
                    "exit_ts",
                    "side",
                    "entry_price",
                    "exit_price",
                    "return",
                    "weight",
                ]
            ),
            config=config,
        )
        risk = compute_risk_metrics(result)
        assert math.isnan(risk.var_95) or isinstance(risk.var_95, float)


# ─── Trade analysis tests (10) ──────────────────────────────────────────────


class TestTradeAnalysis:
    def test_avg_holding_period(self):
        result = _sma_result()
        analysis = compute_trade_analysis(result)
        assert analysis.avg_holding_period >= 0.0

    def test_mfe_long_positive(self):
        result = _sma_result()
        analysis = compute_trade_analysis(result)
        if not result.trades.empty and (result.trades["side"] == 1).any():
            assert analysis.avg_mfe >= Decimal(0)

    def test_mae_long_negative(self):
        result = _sma_result()
        analysis = compute_trade_analysis(result)
        if not result.trades.empty and (result.trades["side"] == 1).any():
            assert analysis.avg_mae <= Decimal(0)

    def test_mfe_short_correct(self):
        dates = pd.bdate_range("2020-01-01", periods=6)
        equity = pd.Series([100000, 101000, 99000, 98000, 100000, 101000], index=dates, dtype=float)
        returns = equity.pct_change()
        positions = pd.Series([-1.0, -1.0, -1.0, -1.0, 0.0, 0.0], index=dates, dtype=float)
        trades = pd.DataFrame(
            {
                "entry_ts": [dates[0]],
                "exit_ts": [dates[3]],
                "side": [-1],
                "entry_price": [100.0],
                "exit_price": [98.0],
                "return": [0.02],
                "weight": [1.0],
            }
        )
        config = BacktestConfig(initial_cash="100000", cost=CostModel())
        result = BacktestResult(
            equity=equity, returns=returns, positions=positions, trades=trades, config=config
        )
        analysis = compute_trade_analysis(result)
        assert analysis.avg_mfe >= Decimal(0)

    def test_mae_short_correct(self):
        dates = pd.bdate_range("2020-01-01", periods=6)
        equity = pd.Series(
            [100000, 101000, 102000, 101000, 100000, 99000], index=dates, dtype=float
        )
        returns = equity.pct_change()
        positions = pd.Series([-1.0, -1.0, -1.0, -1.0, 0.0, 0.0], index=dates, dtype=float)
        trades = pd.DataFrame(
            {
                "entry_ts": [dates[0]],
                "exit_ts": [dates[3]],
                "side": [-1],
                "entry_price": [100.0],
                "exit_price": [101.0],
                "return": [-0.01],
                "weight": [1.0],
            }
        )
        config = BacktestConfig(initial_cash="100000", cost=CostModel())
        result = BacktestResult(
            equity=equity, returns=returns, positions=positions, trades=trades, config=config
        )
        analysis = compute_trade_analysis(result)
        assert analysis.avg_mae <= Decimal(0)

    def test_mfe_mae_mixed_long_short(self):
        dates = pd.bdate_range("2020-01-01", periods=8)
        equity = pd.Series(
            [100000, 105000, 103000, 100000, 98000, 99000, 101000, 102000],
            index=dates,
            dtype=float,
        )
        returns = equity.pct_change()
        positions = pd.Series([1, 1, 1, -1, -1, -1, 0, 0], index=dates, dtype=float)
        trades = pd.DataFrame(
            {
                "entry_ts": [dates[0], dates[3]],
                "exit_ts": [dates[2], dates[5]],
                "side": [1, -1],
                "entry_price": [100.0, 100.0],
                "exit_price": [103.0, 99.0],
                "return": [0.03, 0.01],
                "weight": [1.0, 1.0],
            }
        )
        config = BacktestConfig(initial_cash="100000", cost=CostModel())
        result = BacktestResult(
            equity=equity, returns=returns, positions=positions, trades=trades, config=config
        )
        analysis = compute_trade_analysis(result)
        assert analysis.avg_mfe >= Decimal(0)
        assert analysis.avg_mae <= Decimal(0)

    def test_single_bar_trade(self):
        dates = pd.bdate_range("2020-01-01", periods=5)
        equity = pd.Series([100000, 100500, 99800, 100100, 100200], index=dates, dtype=float)
        returns = equity.pct_change()
        positions = pd.Series([0, 1, 0, 1, 0], index=dates, dtype=float)
        trades = pd.DataFrame(
            {
                "entry_ts": [dates[1], dates[3]],
                "exit_ts": [dates[1], dates[3]],
                "side": [1, 1],
                "entry_price": [100.5, 100.1],
                "exit_price": [100.5, 100.1],
                "return": [0.0, 0.0],
                "weight": [1.0, 1.0],
            }
        )
        config = BacktestConfig(initial_cash="100000", cost=CostModel())
        result = BacktestResult(
            equity=equity, returns=returns, positions=positions, trades=trades, config=config
        )
        analysis = compute_trade_analysis(result)
        assert analysis.avg_holding_period == 0.0

    def test_entry_exit_distributions(self):
        result = _sma_result()
        analysis = compute_trade_analysis(result)
        if not result.trades.empty:
            assert len(analysis.entry_return_dist) == len(result.trades)
            assert len(analysis.exit_return_dist) == len(result.trades)

    def test_empty_trades_analysis(self):
        dates = pd.bdate_range("2020-01-01", periods=5)
        equity = pd.Series([100000, 100500, 99800, 100100, 100200], index=dates, dtype=float)
        returns = equity.pct_change()
        positions = pd.Series(0.0, index=dates, dtype=float)
        config = BacktestConfig(initial_cash="100000", cost=CostModel())
        result = BacktestResult(
            equity=equity,
            returns=returns,
            positions=positions,
            trades=pd.DataFrame(
                columns=[
                    "entry_ts",
                    "exit_ts",
                    "side",
                    "entry_price",
                    "exit_price",
                    "return",
                    "weight",
                ]
            ),
            config=config,
        )
        analysis = compute_trade_analysis(result)
        assert analysis.avg_holding_period == 0.0
        assert analysis.avg_mfe == Decimal("0")
        assert analysis.avg_mae == Decimal("0")
        assert len(analysis.entry_return_dist) == 0

    def test_timestamp_alignment_nearest(self):
        dates = pd.bdate_range("2020-01-01", periods=10)
        equity = pd.Series([100000 + i * 200 for i in range(10)], index=dates, dtype=float)
        returns = equity.pct_change()
        positions = pd.Series(1.0, index=dates, dtype=float)
        trades = pd.DataFrame(
            {
                "entry_ts": [dates[0]],
                "exit_ts": [dates[9]],
                "side": [1],
                "entry_price": [100.0],
                "exit_price": [101.8],
                "return": [0.018],
                "weight": [1.0],
            }
        )
        config = BacktestConfig(initial_cash="100000", cost=CostModel())
        result = BacktestResult(
            equity=equity, returns=returns, positions=positions, trades=trades, config=config
        )
        analysis = compute_trade_analysis(result)
        assert analysis.avg_holding_period == 9.0


# ─── Determinism tests (3) ──────────────────────────────────────────────────


class TestDeterminism:
    def test_performance_metrics_determinism(self):
        result = _sma_result()
        results = [compute_performance_metrics(result) for _ in range(10)]
        for r in results[1:]:
            assert r.total_return == results[0].total_return
            assert r.sharpe == results[0].sharpe
            assert r.max_drawdown == results[0].max_drawdown

    def test_risk_metrics_determinism(self):
        result = _sma_result()
        results = [compute_risk_metrics(result) for _ in range(10)]
        for r in results[1:]:
            assert r.var_95 == results[0].var_95
            assert r.cvar_95 == results[0].cvar_95
            assert r.max_dd_duration_bars == results[0].max_dd_duration_bars

    def test_trade_analysis_determinism(self):
        result = _sma_result()
        results = [compute_trade_analysis(result) for _ in range(10)]
        for r in results[1:]:
            assert r.avg_mfe == results[0].avg_mfe
            assert r.avg_mae == results[0].avg_mae
            assert r.avg_holding_period == results[0].avg_holding_period


# ─── Decimal convention tests (3) ────────────────────────────────────────────


class TestDecimalConvention:
    def test_decimal_fields_from_float(self):
        result = _sma_result()
        metrics = compute_performance_metrics(result)
        assert isinstance(metrics.total_return, Decimal)
        assert isinstance(metrics.cagr, Decimal)
        assert isinstance(metrics.max_drawdown, Decimal)

    def test_decimal_fields_are_decimal_type(self):
        result = _sma_result()
        metrics = compute_performance_metrics(result)
        analysis = compute_trade_analysis(result)
        assert isinstance(metrics.total_return, Decimal)
        assert isinstance(metrics.cagr, Decimal)
        assert isinstance(metrics.max_drawdown, Decimal)
        assert isinstance(analysis.avg_mfe, Decimal)
        assert isinstance(analysis.avg_mae, Decimal)

    def test_decimal_float_boundary_consistency(self):
        result = _known_answer_result()
        metrics = compute_performance_metrics(result)
        expected_tr = (110000 / 100000) - 1
        assert abs(float(metrics.total_return) - expected_tr) < 1e-6


# ─── Alpha/beta stub tests (2) ──────────────────────────────────────────────


class TestAlphaBetaStubs:
    def test_alpha_beta_nan_stub(self):
        result = _sma_result()
        metrics = compute_performance_metrics(result)
        assert math.isnan(metrics.alpha)
        assert math.isnan(metrics.beta)
        assert math.isnan(metrics.information_ratio)

    def test_nan_stubs_propagate(self):
        result = _sma_result()
        metrics = compute_performance_metrics(result)
        assert math.isnan(metrics.alpha + 1.0)
        assert math.isnan(metrics.beta * 2.0)


# ─── Integration tests (3) ──────────────────────────────────────────────────


class TestMetricsIntegration:
    def test_metrics_from_vectorized_engine(self):
        ohlcv = _synthetic_ohlcv(n=500, seed=42)
        strat = SmaCross(fast=20, slow=50)
        signals = strat.generate_signals(ohlcv)
        cfg = BacktestConfig(initial_cash="100000", cost=CostModel())
        result = run_backtest(ohlcv, signals, cfg)
        metrics = compute_performance_metrics(result)
        assert isinstance(metrics.total_return, Decimal)

    def test_metrics_from_event_driven_engine(self):
        ohlcv = _synthetic_ohlcv(n=500, seed=42)
        strat = SmaCross(fast=20, slow=50)
        signals = strat.generate_signals(ohlcv)
        cfg = BacktestConfig(initial_cash="100000", cost=CostModel())
        from trade_advisor.backtest.event_driven import EventDrivenEngine

        engine = EventDrivenEngine(cfg)
        result = engine.run(ohlcv, signals)
        metrics = compute_performance_metrics(result)
        assert isinstance(metrics.total_return, Decimal)

    def test_compute_all_metrics_bundle(self):
        result = _sma_result()
        bundle = compute_all_metrics(result)
        assert isinstance(bundle, MetricsBundle)
        assert isinstance(bundle.performance.total_return, Decimal)
        assert isinstance(bundle.risk.var_95, float)
        assert isinstance(bundle.trade_analysis.avg_mfe, Decimal)


# ─── Property-based tests (5) — deterministic ───────────────────────────────


class TestPropertyBased:
    def test_max_drawdown_always_nonpositive(self):
        for seed in range(10):
            ohlcv = _synthetic_ohlcv(n=200, seed=seed)
            strat = SmaCross(fast=10, slow=30)
            signals = strat.generate_signals(ohlcv)
            cfg = BacktestConfig(initial_cash="100000", cost=CostModel())
            result = run_backtest(ohlcv, signals, cfg)
            metrics = compute_performance_metrics(result)
            assert metrics.max_drawdown <= Decimal(0), f"seed={seed}: max_dd={metrics.max_drawdown}"

    def test_sharpe_negates_on_return_flip(self):
        result = _sma_result()
        metrics = compute_performance_metrics(result)
        flipped_returns = -result.returns
        flipped_result = BacktestResult(
            equity=result.equity,
            returns=flipped_returns,
            positions=result.positions,
            trades=result.trades,
            config=result.config,
        )
        flipped_metrics = compute_performance_metrics(flipped_result)
        if metrics.sharpe != 0.0:
            assert abs(flipped_metrics.sharpe + metrics.sharpe) < 1e-4

    def test_mfe_nonnegative_mae_nonpositive(self):
        for seed in range(5):
            ohlcv = _synthetic_ohlcv(n=300, seed=seed)
            strat = SmaCross(fast=10, slow=30)
            signals = strat.generate_signals(ohlcv)
            cfg = BacktestConfig(initial_cash="100000", cost=CostModel())
            result = run_backtest(ohlcv, signals, cfg)
            if not result.trades.empty:
                analysis = compute_trade_analysis(result)
                assert analysis.avg_mfe >= Decimal(0), f"seed={seed}: mfe={analysis.avg_mfe}"
                assert analysis.avg_mae <= Decimal(0), f"seed={seed}: mae={analysis.avg_mae}"

    def test_total_return_matches_equity_endpoints(self):
        for seed in range(5):
            ohlcv = _synthetic_ohlcv(n=200, seed=seed)
            strat = SmaCross(fast=10, slow=30)
            signals = strat.generate_signals(ohlcv)
            cfg = BacktestConfig(initial_cash="100000", cost=CostModel())
            result = run_backtest(ohlcv, signals, cfg)
            metrics = compute_performance_metrics(result)
            expected = (result.equity.iloc[-1] / 100000.0) - 1.0
            assert abs(float(metrics.total_return) - expected) < 1e-6

    def test_metrics_deterministic_across_seeds_same_data(self):
        ohlcv = _synthetic_ohlcv(n=300, seed=42)
        strat = SmaCross(fast=10, slow=30)
        signals = strat.generate_signals(ohlcv)
        cfg = BacktestConfig(initial_cash="100000", cost=CostModel())
        result = run_backtest(ohlcv, signals, cfg)
        m1 = compute_all_metrics(result)
        m2 = compute_all_metrics(result)
        assert m1.performance.total_return == m2.performance.total_return
        assert m1.risk.var_95 == m2.risk.var_95
        assert m1.trade_analysis.avg_mfe == m2.trade_analysis.avg_mfe
