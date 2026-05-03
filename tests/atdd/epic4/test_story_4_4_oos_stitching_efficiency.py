"""ATDD: Story 4.4 — OOS Equity Curve Stitching & Efficiency Ratio.

Tests assert the EXPECTED end-state for Story 4.4.
RED PHASE: These tests will fail until OOS stitching and WFE are implemented.
"""

from __future__ import annotations

import pytest


class TestStory44OOSStitching:
    """Story 4.4: OOS equity curve stitching and walk-forward efficiency."""

    @pytest.mark.test_id("4.4-ATDD-001")
    @pytest.mark.p0
    async def test_stitching_produces_continuous_curve(self, wf_windows):
        # Given: OOS segments from multiple walk-forward windows
        from trade_advisor.backtest.walkforward.stitch import stitch_oos_equity

        oos_segments = [w["oos_equity"] for w in wf_windows]

        # When: stitching OOS segments
        stitched = stitch_oos_equity(oos_segments)

        # Then: result is a single continuous equity curve
        assert isinstance(stitched, __import__("pandas").Series)
        assert len(stitched) > 0
        assert stitched.index.is_monotonic_increasing

    @pytest.mark.test_id("4.4-ATDD-002")
    @pytest.mark.p0
    async def test_wfe_computed_correctly(self, wf_windows):
        # Given: IS and OOS returns from walk-forward
        import math

        from trade_advisor.backtest.walkforward.stitch import compute_wfe

        # Compounding per spec: product(1 + r_i) - 1
        total_is_return = math.prod(1.0 + w["is_return"] for w in wf_windows) - 1.0
        total_oos_return = math.prod(1.0 + w["oos_return"] for w in wf_windows) - 1.0

        # When: computing WFE ratio
        wfe = compute_wfe(oos_return=total_oos_return, is_return=total_is_return)

        # Then: WFE = OOS_return / IS_return
        assert 0.0 < wfe <= 1.0 or wfe < 0.0
        assert abs(wfe - total_oos_return / total_is_return) < 1e-10

    @pytest.mark.test_id("4.4-ATDD-003")
    @pytest.mark.p0
    async def test_wfe_healthy_flag(self):
        # Given: a WFE >= 0.7 and positive IS
        from trade_advisor.backtest.walkforward.stitch import wfe_status

        # When: checking status
        status = wfe_status(0.75, total_is_return=0.2, total_oos_return=0.15)

        # Then: status is "healthy"
        assert status == "healthy"

    @pytest.mark.test_id("4.4-ATDD-004")
    @pytest.mark.p0
    async def test_wfe_caution_flag(self):
        # Given: a WFE between 0.5 and 0.7 and positive IS
        from trade_advisor.backtest.walkforward.stitch import wfe_status

        # When: checking status
        status = wfe_status(0.6, total_is_return=0.2, total_oos_return=0.12)

        # Then: status is "caution"
        assert status == "caution"

    @pytest.mark.test_id("4.4-ATDD-005")
    @pytest.mark.p0
    async def test_wfe_unreliable_flag(self):
        # Given: a WFE < 0.5
        from trade_advisor.backtest.walkforward.stitch import wfe_status

        # When: checking status
        status = wfe_status(0.3, total_is_return=0.2, total_oos_return=0.06)

        # Then: status is "unreliable" (UNRELIABLE flag per WFO-5)
        assert status == "unreliable"


    @pytest.mark.test_id("4.4-ATDD-006")
    @pytest.mark.p1
    async def test_oos_curve_with_baseline_comparison(self, wf_windows):
        # Given: stitched OOS equity and buy-and-hold baseline
        import pandas as pd

        from trade_advisor.backtest.walkforward.engine import WalkForwardConfig
        from trade_advisor.backtest.walkforward.stitch import (
            compute_oos_baseline,
            stitch_oos_equity,
        )

        oos_segments = [w["oos_equity"] for w in wf_windows]
        # Use common initial cash
        initial_cash = 100_000.0
        stitched = stitch_oos_equity(oos_segments, initial_cash=initial_cash)

        # Mock ohlcv with matching index
        all_indices = pd.concat([s.to_frame() for s in oos_segments]).index.unique().sort_values()
        ohlcv = pd.DataFrame({"close": range(len(all_indices))}, index=all_indices)
        config = WalkForwardConfig(mode="rolling", strategy_type="sma", is_bars=20, oos_bars=10)

        # When: computing baseline

        baseline = compute_oos_baseline(stitched, ohlcv, config)

        # Then: OOS curve and baseline have matching scale and index
        assert len(baseline) == len(stitched)
        assert baseline.iloc[0] == pytest.approx(stitched.iloc[0])
        assert (baseline.index == stitched.index).all()


    @pytest.mark.test_id("4.4-ATDD-007")
    @pytest.mark.p1
    async def test_expected_value_per_trade(self):
        # Given: a distribution of OOS trades
        from trade_advisor.backtest.walkforward.stitch import compute_expected_value

        trade_returns = [0.02, -0.01, 0.03, -0.005, 0.015, -0.02, 0.01]

        # When: computing expected value per trade (BT-8)
        ev = compute_expected_value(trade_returns)

        # Then: EV is the mean of the trade distribution
        import numpy as np

        assert abs(ev - np.mean(trade_returns)) < 1e-10

    @pytest.mark.test_id("4.4-ATDD-008")
    @pytest.mark.p2
    async def test_negative_ev_flagged(self):
        # Given: a negative expected value
        from trade_advisor.backtest.walkforward.stitch import compute_expected_value

        trade_returns = [-0.05, -0.03, -0.02, -0.01]

        # When: computing EV
        ev = compute_expected_value(trade_returns)

        # Then: EV is negative
        assert ev < 0

    @pytest.mark.test_id("4.4-ATDD-009")
    @pytest.mark.p2
    async def test_empty_trades_returns_zero_ev(self):
        # Given: no trades
        from trade_advisor.backtest.walkforward.stitch import compute_expected_value

        # When: computing EV with empty list
        ev = compute_expected_value([])

        # Then: EV is 0.0
        assert ev == 0.0
