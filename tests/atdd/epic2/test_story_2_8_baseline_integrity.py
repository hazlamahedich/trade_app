"""ATDD red-phase: Story 2.8 — Mandatory Baseline Comparison & Integrity Checks.

Tests assert the expected end-state AFTER full Story 2.8 implementation.
All tests are SKIPPED (TDD red phase).

Remove @pytest.mark.skip when implementing Story 2.8.
"""

from __future__ import annotations

import pytest


class TestStory28BaselineComparison:
    """Story 2.8: Every backtest compared against buy-and-hold with integrity checks."""

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.8 not yet implemented")
    def test_buy_and_hold_always_shown(self, ohlcv_500, backtest_config):
        from trade_advisor.backtest.baseline import compute_with_baseline

        from trade_advisor.strategies.sma_cross import SmaCross

        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv_500)
        comparison = compute_with_baseline(ohlcv_500, signals, backtest_config)
        assert hasattr(comparison, "strategy_metrics")
        assert hasattr(comparison, "buy_and_hold_metrics")
        assert comparison.buy_and_hold_metrics is not None

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.8 not yet implemented")
    def test_impossible_negative_portfolio_detected(self):
        import pandas as pd
        from trade_advisor.backtest.integrity import check_integrity

        equity = pd.Series([100000, 50000, -1000])
        result = check_integrity(equity)
        assert not result.is_valid
        assert any("negative" in e.lower() for e in result.errors)

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.8 not yet implemented")
    def test_impossible_returns_over_100_pct_detected(self):
        import pandas as pd
        from trade_advisor.backtest.integrity import check_integrity

        equity = pd.Series([100000, 500000, 300000])
        result = check_integrity(equity)
        assert not result.is_valid

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.8 not yet implemented")
    def test_equity_curve_gaps_detected(self):
        import pandas as pd
        from trade_advisor.backtest.integrity import check_integrity

        equity = pd.Series([100000, pd.NA, 105000])
        result = check_integrity(equity)
        assert not result.is_valid

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.8 not yet implemented")
    def test_is_label_shown_on_all_results(self, ohlcv_500, backtest_config):
        from trade_advisor.backtest.baseline import compute_with_baseline

        from trade_advisor.strategies.sma_cross import SmaCross

        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv_500)
        comparison = compute_with_baseline(ohlcv_500, signals, backtest_config)
        assert comparison.is_label == "In-Sample Only — not validated for live trading"

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.8 not yet implemented")
    def test_integrity_failure_halts_display(self):
        import pandas as pd
        from trade_advisor.backtest.integrity import check_integrity

        equity = pd.Series([100000, -5000])
        result = check_integrity(equity)
        assert result.should_halt_display is True

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.8 not yet implemented")
    def test_regime_stratification_when_data_available(self, ohlcv_500, backtest_config):
        from trade_advisor.backtest.regime import stratify_by_regime

        from trade_advisor.strategies.sma_cross import SmaCross

        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv_500)
        regimes = stratify_by_regime(ohlcv_500, signals)
        assert "trending" in regimes or "mean_reverting" in regimes
