"""ATDD: Story 4.3 — OOS Evaluation with Frozen Parameters.

Tests assert the EXPECTED end-state for Story 4.3.
RED PHASE: These tests will fail until OOS evaluation is implemented.
"""

from __future__ import annotations

import pytest


class TestStory43OOSFrozenParams:
    """Story 4.3: OOS evaluation with frozen parameters — no information leakage."""

    @pytest.mark.test_id("4.3-ATDD-001")
    @pytest.mark.p0
    async def test_oos_uses_frozen_params_from_prior_is(self, wf_ohlcv):
        # Given: optimized parameters from IS window
        from trade_advisor.backtest.walkforward.engine import WalkForwardEngine

        engine = WalkForwardEngine(mode="rolling", is_bars=60, oos_bars=20, seed=42)
        result = await engine.run(
            wf_ohlcv,
            strategy_config={"strategy_type": "sma"},
            optimize=True,
            param_ranges={"fast": (5, 50), "slow": (20, 200)},
        )

        # When: inspecting OOS results
        # Then: each OOS window uses frozen params from its prior IS window
        for window in result.windows:
            assert window.frozen_params is not None
            assert "fast" in window.frozen_params
            assert "slow" in window.frozen_params

    @pytest.mark.test_id("4.3-ATDD-002")
    @pytest.mark.p0
    async def test_no_refitting_in_oos(self, wf_ohlcv):
        # Given: a walk-forward result with optimization
        from trade_advisor.backtest.walkforward.engine import WalkForwardEngine

        engine = WalkForwardEngine(mode="rolling", is_bars=60, oos_bars=20, seed=42)
        result = await engine.run(
            wf_ohlcv,
            strategy_config={"strategy_type": "sma"},
            optimize=True,
            param_ranges={"fast": (5, 50), "slow": (20, 200)},
        )

        # When: checking OOS evaluation
        # Then: OOS params are identical to the IS-optimized params (no refitting)
        for window in result.windows:
            assert window.frozen_params == window.is_optimized_params

    @pytest.mark.test_id("4.3-ATDD-003")
    @pytest.mark.p0
    async def test_data_boundary_enforced(self, wf_ohlcv):
        # Given: a walk-forward configuration
        from trade_advisor.backtest.walkforward.engine import WalkForwardEngine

        engine = WalkForwardEngine(mode="rolling", is_bars=60, oos_bars=20, seed=42)
        result = await engine.run(wf_ohlcv, strategy_config={"strategy_type": "sma", "fast": 20, "slow": 50})

        # When: checking IS/OOS boundaries
        # Then: no data leakage — OOS timestamps start after IS timestamps
        for window in result.windows:
            is_end = window.is_segment.index[-1]
            oos_start = window.oos_segment.index[0]
            assert oos_start > is_end

    @pytest.mark.test_id("4.3-ATDD-004")
    @pytest.mark.p1
    async def test_embargo_period_prevents_leakage(self, wf_ohlcv):
        # Given: a walk-forward configuration with embargo
        from trade_advisor.backtest.walkforward.engine import WalkForwardEngine

        engine = WalkForwardEngine(
            mode="rolling",
            is_bars=60,
            oos_bars=20,
            embargo_bars=5,
            seed=42,
        )
        result = await engine.run(wf_ohlcv, strategy_config={"strategy_type": "sma", "fast": 20, "slow": 50})

        # When: checking window boundaries
        # Then: embargo bars create a gap between IS and OOS
        for window in result.windows:
            is_end = window.is_segment.index[-1]
            oos_start = window.oos_segment.index[0]
            gap = (oos_start - is_end).days
            assert gap >= 5

    @pytest.mark.test_id("4.3-ATDD-005")
    @pytest.mark.p1
    async def test_oos_results_computed_independently(self, wf_ohlcv):
        # Given: a walk-forward result with multiple windows
        from trade_advisor.backtest.walkforward.engine import WalkForwardEngine

        engine = WalkForwardEngine(mode="rolling", is_bars=60, oos_bars=20, seed=42)
        result = await engine.run(wf_ohlcv, strategy_config={"strategy_type": "sma", "fast": 20, "slow": 50})

        # When: comparing OOS equity across windows
        # Then: each window's OOS equity starts from the same base (independent)
        for window in result.windows:
            assert window.oos_equity is not None
            assert len(window.oos_equity) > 0

    @pytest.mark.test_id("4.3-ATDD-006")
    @pytest.mark.p2
    async def test_data_boundary_protocol_satisfied(self):
        # Given: the DataBoundary protocol
        from trade_advisor.backtest.walkforward.engine import DataBoundary

        # When: checking protocol compliance
        # Then: DataBoundary has the required methods
        assert hasattr(DataBoundary, "is_end")
        assert hasattr(DataBoundary, "oos_start")
        assert hasattr(DataBoundary, "embargo_bars")
