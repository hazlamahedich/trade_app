"""ATDD red-phase: Story 2.7 — Portfolio & Trade-Level Metrics.

Tests assert the expected end-state AFTER full Story 2.7 implementation.
All tests are SKIPPED (TDD red phase).

Remove @pytest.mark.skip when implementing Story 2.7.
"""

from __future__ import annotations

from decimal import Decimal

import pytest


class TestStory27PortfolioMetrics:
    """Story 2.7: Comprehensive performance metrics."""

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.7 not yet implemented")
    def test_performance_metrics_module_exists(self):
        from trade_advisor.backtest.metrics.performance import compute_performance_metrics

        assert compute_performance_metrics is not None

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.7 not yet implemented")
    def test_total_return_computed(self, ohlcv_500, backtest_config):
        from trade_advisor.backtest.metrics.performance import compute_performance_metrics

        from trade_advisor.backtest.engine import run_backtest
        from trade_advisor.strategies.sma_cross import SmaCross

        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv_500)
        result = run_backtest(ohlcv_500, signals, backtest_config)
        metrics = compute_performance_metrics(result)
        assert hasattr(metrics, "total_return")

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.7 not yet implemented")
    def test_sharpe_computed(self, ohlcv_500, backtest_config):
        from trade_advisor.backtest.metrics.performance import compute_performance_metrics

        from trade_advisor.backtest.engine import run_backtest
        from trade_advisor.strategies.sma_cross import SmaCross

        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv_500)
        result = run_backtest(ohlcv_500, signals, backtest_config)
        metrics = compute_performance_metrics(result)
        assert hasattr(metrics, "sharpe")

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.7 not yet implemented")
    def test_cagr_computed(self, ohlcv_500, backtest_config):
        from trade_advisor.backtest.metrics.performance import compute_performance_metrics

        from trade_advisor.backtest.engine import run_backtest
        from trade_advisor.strategies.sma_cross import SmaCross

        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv_500)
        result = run_backtest(ohlcv_500, signals, backtest_config)
        metrics = compute_performance_metrics(result)
        assert hasattr(metrics, "cagr")

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.7 not yet implemented")
    def test_sortino_computed(self, ohlcv_500, backtest_config):
        from trade_advisor.backtest.metrics.performance import compute_performance_metrics

        from trade_advisor.backtest.engine import run_backtest
        from trade_advisor.strategies.sma_cross import SmaCross

        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv_500)
        result = run_backtest(ohlcv_500, signals, backtest_config)
        metrics = compute_performance_metrics(result)
        assert hasattr(metrics, "sortino")

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.7 not yet implemented")
    def test_calmar_computed(self, ohlcv_500, backtest_config):
        from trade_advisor.backtest.metrics.performance import compute_performance_metrics

        from trade_advisor.backtest.engine import run_backtest
        from trade_advisor.strategies.sma_cross import SmaCross

        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv_500)
        result = run_backtest(ohlcv_500, signals, backtest_config)
        metrics = compute_performance_metrics(result)
        assert hasattr(metrics, "calmar")

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.7 not yet implemented")
    def test_max_drawdown_computed(self, ohlcv_500, backtest_config):
        from trade_advisor.backtest.metrics.performance import compute_performance_metrics

        from trade_advisor.backtest.engine import run_backtest
        from trade_advisor.strategies.sma_cross import SmaCross

        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv_500)
        result = run_backtest(ohlcv_500, signals, backtest_config)
        metrics = compute_performance_metrics(result)
        assert hasattr(metrics, "max_drawdown")
        assert metrics.max_drawdown <= 0


class TestStory27RiskMetrics:
    """Story 2.7: Risk metrics (VaR, CVaR, tail ratio)."""

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.7 not yet implemented")
    def test_risk_metrics_module_exists(self):
        from trade_advisor.backtest.metrics.risk import compute_risk_metrics

        assert compute_risk_metrics is not None

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.7 not yet implemented")
    def test_var_computed(self, ohlcv_500, backtest_config):
        from trade_advisor.backtest.metrics.risk import compute_risk_metrics

        from trade_advisor.backtest.engine import run_backtest
        from trade_advisor.strategies.sma_cross import SmaCross

        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv_500)
        result = run_backtest(ohlcv_500, signals, backtest_config)
        risk = compute_risk_metrics(result)
        assert hasattr(risk, "var_95")

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.7 not yet implemented")
    def test_cvar_computed(self, ohlcv_500, backtest_config):
        from trade_advisor.backtest.metrics.risk import compute_risk_metrics

        from trade_advisor.backtest.engine import run_backtest
        from trade_advisor.strategies.sma_cross import SmaCross

        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv_500)
        result = run_backtest(ohlcv_500, signals, backtest_config)
        risk = compute_risk_metrics(result)
        assert hasattr(risk, "cvar_95")

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.7 not yet implemented")
    def test_max_dd_duration_computed(self, ohlcv_500, backtest_config):
        from trade_advisor.backtest.metrics.risk import compute_risk_metrics

        from trade_advisor.backtest.engine import run_backtest
        from trade_advisor.strategies.sma_cross import SmaCross

        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv_500)
        result = run_backtest(ohlcv_500, signals, backtest_config)
        risk = compute_risk_metrics(result)
        assert hasattr(risk, "max_dd_duration_bars")


class TestStory27TradeLevelMetrics:
    """Story 2.7: Trade-level analysis (MFE, MAE, holding period)."""

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.7 not yet implemented")
    def test_trade_level_analysis_module_exists(self):
        from trade_advisor.backtest.metrics.trade_analysis import compute_trade_analysis

        assert compute_trade_analysis is not None

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.7 not yet implemented")
    def test_holding_period_computed(self, ohlcv_500, backtest_config):
        from trade_advisor.backtest.metrics.trade_analysis import compute_trade_analysis

        from trade_advisor.backtest.engine import run_backtest
        from trade_advisor.strategies.sma_cross import SmaCross

        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv_500)
        result = run_backtest(ohlcv_500, signals, backtest_config)
        analysis = compute_trade_analysis(result)
        assert hasattr(analysis, "avg_holding_period")

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.7 not yet implemented")
    def test_mfe_mae_computed(self, ohlcv_500, backtest_config):
        from trade_advisor.backtest.metrics.trade_analysis import compute_trade_analysis

        from trade_advisor.backtest.engine import run_backtest
        from trade_advisor.strategies.sma_cross import SmaCross

        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv_500)
        result = run_backtest(ohlcv_500, signals, backtest_config)
        analysis = compute_trade_analysis(result)
        assert hasattr(analysis, "avg_mfe")
        assert hasattr(analysis, "avg_mae")

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.7 not yet implemented")
    def test_entry_exit_distributions(self, ohlcv_500, backtest_config):
        from trade_advisor.backtest.metrics.trade_analysis import compute_trade_analysis

        from trade_advisor.backtest.engine import run_backtest
        from trade_advisor.strategies.sma_cross import SmaCross

        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv_500)
        result = run_backtest(ohlcv_500, signals, backtest_config)
        analysis = compute_trade_analysis(result)
        assert hasattr(analysis, "entry_return_dist")
        assert hasattr(analysis, "exit_return_dist")

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.7 not yet implemented")
    def test_metrics_use_decimal_arithmetic(self, ohlcv_500, backtest_config):
        from trade_advisor.backtest.metrics.performance import compute_performance_metrics

        from trade_advisor.backtest.engine import run_backtest
        from trade_advisor.strategies.sma_cross import SmaCross

        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv_500)
        result = run_backtest(ohlcv_500, signals, backtest_config)
        metrics = compute_performance_metrics(result)
        assert isinstance(metrics.total_return, Decimal)
