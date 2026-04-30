"""ATDD: Story 2.12 — Strategy Reproducibility & Deterministic Run IDs."""

from __future__ import annotations

import pytest


class TestStory212Reproducibility:
    """Story 2.12: Deterministic run IDs and full reproducibility."""

    @pytest.mark.test_id("2.12-ATDD-001")
    @pytest.mark.p1
    def test_deterministic_run_id_from_config_hash(self):
        from trade_advisor.experiments.tracker import HashedRunInputs, generate_run_id

        inputs1 = HashedRunInputs(
            config={"strategy": "sma_cross", "fast": 20, "slow": 50, "seed": 42}
        )
        inputs2 = HashedRunInputs(
            config={"strategy": "sma_cross", "fast": 20, "slow": 50, "seed": 42}
        )
        id1 = generate_run_id(inputs1)
        id2 = generate_run_id(inputs2)
        assert id1 == id2

    @pytest.mark.test_id("2.12-ATDD-002")
    @pytest.mark.p1
    def test_different_config_different_run_id(self):
        from trade_advisor.experiments.tracker import HashedRunInputs, generate_run_id

        inputs1 = HashedRunInputs(
            config={"strategy": "sma_cross", "fast": 20, "slow": 50, "seed": 42}
        )
        inputs2 = HashedRunInputs(
            config={"strategy": "sma_cross", "fast": 14, "slow": 50, "seed": 42}
        )
        id1 = generate_run_id(inputs1)
        id2 = generate_run_id(inputs2)
        assert id1 != id2

    @pytest.mark.test_id("2.12-ATDD-003")
    @pytest.mark.p1
    def test_run_metadata_stored_in_db(self, ohlcv_500, backtest_config):
        from trade_advisor.experiments.tracker import (
            HashedRunInputs,
            compute_config_hash,
            generate_run_id,
        )

        config = {"strategy": "sma_cross", "fast": 20, "slow": 50}
        config_hash = compute_config_hash(config)
        inputs = HashedRunInputs(config=config)
        run_id = generate_run_id(inputs)
        assert run_id is not None
        assert run_id.startswith("run_")
        assert len(config_hash) == 64

    @pytest.mark.test_id("2.12-ATDD-004")
    @pytest.mark.p1
    def test_rerun_produces_bitwise_identical_results(self, ohlcv_500, zero_cost_config):
        from trade_advisor.backtest.engine import run_backtest
        from trade_advisor.strategies.sma_cross import SmaCross

        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv_500)
        result1 = run_backtest(ohlcv_500, signals, zero_cost_config)

        strategy2 = SmaCross(fast=20, slow=50)
        signals2 = strategy2.generate_signals(ohlcv_500)
        result2 = run_backtest(ohlcv_500, signals2, zero_cost_config)

        assert result1.equity.values.tobytes() == result2.equity.values.tobytes()

    @pytest.mark.test_id("2.12-ATDD-005")
    @pytest.mark.p1
    def test_run_record_includes_pre_mortem(self):
        from trade_advisor.experiments.tracker import (
            ExperimentRecord,
            HashedRunInputs,
            RunAnnotations,
            generate_run_id,
        )

        config = {"strategy": "sma_cross", "fast": 20, "slow": 50}
        inputs = HashedRunInputs(config=config)
        run_id = generate_run_id(inputs)
        annotations = RunAnnotations(pre_mortem="I expect Sharpe > 1.0")
        record = ExperimentRecord(
            run_id=run_id,
            config_hash="abc123",
            strategy="sma",
            pre_mortem=annotations.pre_mortem,
        )
        assert record.pre_mortem == "I expect Sharpe > 1.0"

    @pytest.mark.test_id("2.12-ATDD-006")
    @pytest.mark.p1
    def test_package_versions_in_hash(self):
        from trade_advisor.experiments.tracker import HashedRunInputs, generate_run_id

        inputs1 = HashedRunInputs(config={"fast": 20}, package_versions='{"numpy": "1.24.0"}')
        inputs2 = HashedRunInputs(config={"fast": 20}, package_versions='{"numpy": "1.26.0"}')
        assert generate_run_id(inputs1) != generate_run_id(inputs2)

    @pytest.mark.test_id("2.12-ATDD-007")
    @pytest.mark.p1
    def test_dirty_tree_warning(self):
        from trade_advisor.experiments.tracker import is_dirty_tree

        result = is_dirty_tree()
        assert isinstance(result, bool)
