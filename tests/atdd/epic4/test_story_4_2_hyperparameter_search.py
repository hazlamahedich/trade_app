"""ATDD: Story 4.2 — In-Sample Hyperparameter Search with Pruning.

Tests assert the EXPECTED end-state for Story 4.2.
RED PHASE: These tests will fail until the hyperparameter optimizer is implemented.
"""

from __future__ import annotations

import pytest


class TestStory42HyperparameterSearch:
    """Story 4.2: IS hyperparameter search with median pruning."""

    @pytest.mark.test_id("4.2-ATDD-001")
    @pytest.mark.p0
    async def test_search_finds_best_params_per_window(self, wf_ohlcv):
        # Given: a walk-forward configuration with parameter ranges
        from trade_advisor.backtest.walkforward.optimize import HyperparamOptimizer

        optimizer = HyperparamOptimizer(
            param_ranges={"fast": (5, 50), "slow": (20, 200)},
            is_bars=60,
            oos_bars=20,
        )

        # When: searching within a single IS window
        is_window = wf_ohlcv.iloc[:60]
        result = await optimizer.search(is_window, n_trials=20, seed=42)

        # Then: best parameters are returned with IS metrics
        assert result.best_params is not None
        assert "fast" in result.best_params
        assert "slow" in result.best_params
        assert result.best_is_sharpe is not None

    @pytest.mark.test_id("4.2-ATDD-002")
    @pytest.mark.p0
    async def test_median_pruning_reduces_trials(self, wf_ohlcv):
        # Given: a set of trial results
        from trade_advisor.backtest.walkforward.optimize import HyperparamOptimizer

        optimizer = HyperparamOptimizer(
            param_ranges={"fast": (5, 50), "slow": (20, 200)},
            is_bars=60,
            oos_bars=20,
        )

        # When: running median pruning
        is_window = wf_ohlcv.iloc[:60]
        result = await optimizer.search(is_window, n_trials=20, seed=42, pruning=True)

        # Then: trials actually evaluated < n_trials (bottom 50% pruned)
        assert result.trials_evaluated < 20
        assert result.trials_pruned > 0
        assert result.trials_evaluated + result.trials_pruned <= 20

    @pytest.mark.test_id("4.2-ATDD-003")
    @pytest.mark.p0
    async def test_constraints_enforced(self, wf_ohlcv):
        # Given: monotonicity constraints on parameters
        from trade_advisor.backtest.walkforward.optimize import HyperparamOptimizer

        optimizer = HyperparamOptimizer(
            param_ranges={"fast": (5, 50), "slow": (20, 200)},
            constraints={"slow_gt_fast": True},
            is_bars=60,
            oos_bars=20,
        )

        # When: searching parameters
        is_window = wf_ohlcv.iloc[:60]
        result = await optimizer.search(is_window, n_trials=20, seed=42)

        # Then: best params respect the constraint (slow > fast)
        assert result.best_params["slow"] > result.best_params["fast"]

    @pytest.mark.test_id("4.2-ATDD-004")
    @pytest.mark.p1
    async def test_best_params_recorded_with_is_metrics(self, wf_ohlcv):
        # Given: a completed search
        from trade_advisor.backtest.walkforward.optimize import HyperparamOptimizer

        optimizer = HyperparamOptimizer(
            param_ranges={"fast": (5, 50), "slow": (20, 200)},
            is_bars=60,
            oos_bars=20,
        )

        # When: searching parameters
        is_window = wf_ohlcv.iloc[:60]
        result = await optimizer.search(is_window, n_trials=20, seed=42)

        # Then: result includes per-trial IS metrics
        assert result.all_trials is not None
        assert len(result.all_trials) > 0
        for trial in result.all_trials:
            assert "params" in trial
            assert "is_sharpe" in trial

    @pytest.mark.test_id("4.2-ATDD-005")
    @pytest.mark.p1
    async def test_seed_hierarchy_respected(self, wf_ohlcv):
        # Given: the seed hierarchy from infra/seed.py
        from trade_advisor.backtest.walkforward.optimize import HyperparamOptimizer

        optimizer_a = HyperparamOptimizer(
            param_ranges={"fast": (5, 50), "slow": (20, 200)},
            is_bars=60,
            oos_bars=20,
            seed=42,
        )
        optimizer_b = HyperparamOptimizer(
            param_ranges={"fast": (5, 50), "slow": (20, 200)},
            is_bars=60,
            oos_bars=20,
            seed=42,
        )

        # When: searching with identical seeds
        is_window = wf_ohlcv.iloc[:60]
        result_a = await optimizer_a.search(is_window, n_trials=10, seed=42)
        result_b = await optimizer_b.search(is_window, n_trials=10, seed=42)

        # Then: identical parameters are sampled in the same order
        assert result_a.best_params == result_b.best_params

    @pytest.mark.test_id("4.2-ATDD-006")
    @pytest.mark.p2
    async def test_empty_param_range_raises(self):
        # Given: an empty parameter range
        from trade_advisor.backtest.walkforward.optimize import HyperparamOptimizer

        # When: constructing with empty range
        # Then: a validation error is raised
        with pytest.raises((ValueError, TypeError)):
            HyperparamOptimizer(
                param_ranges={"fast": (50, 5)},
                is_bars=60,
                oos_bars=20,
            )

    @pytest.mark.test_id("4.2-ATDD-007")
    @pytest.mark.p2
    async def test_pruning_disabled_uses_all_trials(self, wf_ohlcv):
        # Given: pruning disabled
        from trade_advisor.backtest.walkforward.optimize import HyperparamOptimizer

        optimizer = HyperparamOptimizer(
            param_ranges={"fast": (5, 50), "slow": (20, 200)},
            is_bars=60,
            oos_bars=20,
        )

        # When: searching without pruning
        is_window = wf_ohlcv.iloc[:60]
        result = await optimizer.search(is_window, n_trials=10, seed=42, pruning=False)

        # Then: all trials are evaluated
        assert result.trials_evaluated == 10
        assert result.trials_pruned == 0
