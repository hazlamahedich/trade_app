"""ATDD: Story 2.7 — Portfolio & Trade-Level Metrics.

Covers performance metrics (total return, Sharpe, CAGR, Sortino, Calmar,
max drawdown), risk metrics (VaR-95, CVaR-95, max DD duration), and
trade-level analysis (holding period, MFE/MAE, entry/exit distributions).
"""

from __future__ import annotations

from decimal import Decimal

import pytest


@pytest.fixture
def backtest_metrics(ohlcv_500, backtest_config):
    from trade_advisor.backtest.engine import run_backtest
    from trade_advisor.backtest.metrics.performance import compute_performance_metrics
    from trade_advisor.strategies.sma_cross import SmaCross

    strategy = SmaCross(fast=20, slow=50)
    signals = strategy.generate_signals(ohlcv_500)
    result = run_backtest(ohlcv_500, signals, backtest_config)
    return compute_performance_metrics(result)


@pytest.fixture
def backtest_risk_metrics(ohlcv_500, backtest_config):
    from trade_advisor.backtest.engine import run_backtest
    from trade_advisor.backtest.metrics.risk import compute_risk_metrics
    from trade_advisor.strategies.sma_cross import SmaCross

    strategy = SmaCross(fast=20, slow=50)
    signals = strategy.generate_signals(ohlcv_500)
    result = run_backtest(ohlcv_500, signals, backtest_config)
    return compute_risk_metrics(result)


@pytest.fixture
def backtest_trade_analysis(ohlcv_500, backtest_config):
    from trade_advisor.backtest.engine import run_backtest
    from trade_advisor.backtest.metrics.trade_analysis import compute_trade_analysis
    from trade_advisor.strategies.sma_cross import SmaCross

    strategy = SmaCross(fast=20, slow=50)
    signals = strategy.generate_signals(ohlcv_500)
    result = run_backtest(ohlcv_500, signals, backtest_config)
    return compute_trade_analysis(result)


class TestStory27PortfolioMetrics:
    """Story 2.7: Comprehensive performance metrics."""

    @pytest.mark.test_id("2.7-ATDD-001")
    @pytest.mark.p1
    def test_performance_metrics_module_exists(self):
        from trade_advisor.backtest.metrics.performance import compute_performance_metrics

        assert compute_performance_metrics is not None

    @pytest.mark.test_id("2.7-ATDD-002")
    @pytest.mark.p1
    def test_total_return_computed(self, backtest_metrics):
        assert hasattr(backtest_metrics, "total_return")

    @pytest.mark.test_id("2.7-ATDD-003")
    @pytest.mark.p1
    def test_sharpe_computed(self, backtest_metrics):
        assert hasattr(backtest_metrics, "sharpe")

    @pytest.mark.test_id("2.7-ATDD-004")
    @pytest.mark.p1
    def test_cagr_computed(self, backtest_metrics):
        assert hasattr(backtest_metrics, "cagr")

    @pytest.mark.test_id("2.7-ATDD-005")
    @pytest.mark.p1
    def test_sortino_computed(self, backtest_metrics):
        assert hasattr(backtest_metrics, "sortino")

    @pytest.mark.test_id("2.7-ATDD-006")
    @pytest.mark.p1
    def test_calmar_computed(self, backtest_metrics):
        assert hasattr(backtest_metrics, "calmar")

    @pytest.mark.test_id("2.7-ATDD-007")
    @pytest.mark.p1
    def test_max_drawdown_computed(self, backtest_metrics):
        assert hasattr(backtest_metrics, "max_drawdown")
        assert backtest_metrics.max_drawdown <= 0


class TestStory27RiskMetrics:
    """Story 2.7: Risk metrics (VaR, CVaR, tail ratio)."""

    @pytest.mark.test_id("2.7-ATDD-008")
    @pytest.mark.p1
    def test_risk_metrics_module_exists(self):
        from trade_advisor.backtest.metrics.risk import compute_risk_metrics

        assert compute_risk_metrics is not None

    @pytest.mark.test_id("2.7-ATDD-009")
    @pytest.mark.p1
    def test_var_computed(self, backtest_risk_metrics):
        assert hasattr(backtest_risk_metrics, "var_95")

    @pytest.mark.test_id("2.7-ATDD-010")
    @pytest.mark.p1
    def test_cvar_computed(self, backtest_risk_metrics):
        assert hasattr(backtest_risk_metrics, "cvar_95")

    @pytest.mark.test_id("2.7-ATDD-011")
    @pytest.mark.p1
    def test_max_dd_duration_computed(self, backtest_risk_metrics):
        assert hasattr(backtest_risk_metrics, "max_dd_duration_bars")


class TestStory27TradeLevelMetrics:
    """Story 2.7: Trade-level analysis (MFE, MAE, holding period)."""

    @pytest.mark.test_id("2.7-ATDD-012")
    @pytest.mark.p1
    def test_trade_level_analysis_module_exists(self):
        from trade_advisor.backtest.metrics.trade_analysis import compute_trade_analysis

        assert compute_trade_analysis is not None

    @pytest.mark.test_id("2.7-ATDD-013")
    @pytest.mark.p1
    def test_holding_period_computed(self, backtest_trade_analysis):
        assert hasattr(backtest_trade_analysis, "avg_holding_period")

    @pytest.mark.test_id("2.7-ATDD-014")
    @pytest.mark.p1
    def test_mfe_mae_computed(self, backtest_trade_analysis):
        assert hasattr(backtest_trade_analysis, "avg_mfe")
        assert hasattr(backtest_trade_analysis, "avg_mae")

    @pytest.mark.test_id("2.7-ATDD-015")
    @pytest.mark.p1
    def test_entry_exit_distributions(self, backtest_trade_analysis):
        assert hasattr(backtest_trade_analysis, "entry_return_dist")
        assert hasattr(backtest_trade_analysis, "exit_return_dist")

    @pytest.mark.test_id("2.7-ATDD-016")
    @pytest.mark.p1
    def test_metrics_use_decimal_arithmetic(self, backtest_metrics):
        assert isinstance(backtest_metrics.total_return, Decimal)
