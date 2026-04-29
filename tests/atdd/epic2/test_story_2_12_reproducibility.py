"""ATDD red-phase: Story 2.12 — Strategy Reproducibility & Deterministic Run IDs.

Tests assert the expected end-state AFTER full Story 2.12 implementation.
All tests are SKIPPED (TDD red phase).

Remove @pytest.mark.skip when implementing Story 2.12.
"""

from __future__ import annotations

import pytest


class TestStory212Reproducibility:
    """Story 2.12: Deterministic run IDs and full reproducibility."""

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.12 not yet implemented")
    def test_deterministic_run_id_from_config_hash(self):
        from trade_advisor.backtest.run_id import generate_run_id

        config1 = {"strategy": "sma_cross", "fast": 20, "slow": 50, "seed": 42}
        config2 = {"strategy": "sma_cross", "fast": 20, "slow": 50, "seed": 42}
        id1 = generate_run_id(config1)
        id2 = generate_run_id(config2)
        assert id1 == id2

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.12 not yet implemented")
    def test_different_config_different_run_id(self):
        from trade_advisor.backtest.run_id import generate_run_id

        config1 = {"strategy": "sma_cross", "fast": 20, "slow": 50, "seed": 42}
        config2 = {"strategy": "sma_cross", "fast": 14, "slow": 50, "seed": 42}
        id1 = generate_run_id(config1)
        id2 = generate_run_id(config2)
        assert id1 != id2

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.12 not yet implemented")
    def test_run_metadata_stored_in_db(self, ohlcv_500, backtest_config):
        from trade_advisor.backtest.run_id import generate_run_id

        config = {
            "strategy": "sma_cross",
            "fast": 20,
            "slow": 50,
        }
        run_id = generate_run_id(config)
        assert run_id is not None

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.12 not yet implemented")
    def test_rerun_produces_bitwise_identical_results(self, ohlcv_500, zero_cost_config):

        from trade_advisor.backtest.engine import run_backtest
        from trade_advisor.strategies.sma_cross import SmaCross

        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv_500)
        result1 = run_backtest(ohlcv_500, signals, zero_cost_config)

        strategy2 = SmaCross(fast=20, slow=50)
        signals2 = strategy2.generate_signals(ohlcv_500)
        result2 = run_backtest(ohlcv_500, signals2, zero_cost_config)

        import numpy as np

        np.testing.assert_array_almost_equal(
            result1.equity.values,
            result2.equity.values,
            decimal=10,
        )

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.12 not yet implemented")
    def test_run_record_includes_pre_mortem(self):
        from trade_advisor.backtest.run_id import generate_run_id

        config = {"strategy": "sma_cross", "fast": 20, "slow": 50}
        run_id = generate_run_id(config, pre_mortem="I expect Sharpe > 1.0")
        assert run_id is not None
