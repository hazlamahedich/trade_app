"""ATDD: Story 4.2 — In-Sample Hyperparameter Search with Pruning.

Tests assert the EXPECTED end-state for Story 4.2, matching the revised API
with strategy_factory, PruningConfig, ParamConstraint protocol, and sync
optimize_is_window function.
"""

from __future__ import annotations

import math

import pytest

from trade_advisor.backtest.walkforward.optimize import (
    OptimizationConfig,
    PruningConfig,
    TrialResult,
    monotonic_increasing,
    optimize_is_window,
)
from trade_advisor.config import BacktestConfig
from trade_advisor.strategies.sma_cross import SmaCross


def _make_sma_factory():
    return lambda params: SmaCross(**params)


class TestStory42HyperparameterSearch:
    """Story 4.2: IS hyperparameter search with median pruning."""

    @pytest.mark.test_id("4.2-ATDD-001")
    @pytest.mark.p0
    def test_search_finds_best_params_per_window(self, wf_ohlcv):
        is_window = wf_ohlcv.iloc[:60]
        cfg = OptimizationConfig(
            param_ranges={"fast": [5, 10, 20], "slow": [30, 50, 100]},
            pruning=PruningConfig(enabled=False),
        )
        result = optimize_is_window(is_window, cfg, _make_sma_factory(), BacktestConfig(), seed=42)

        assert result.best_params is not None
        assert "fast" in result.best_params
        assert "slow" in result.best_params
        evaluated = [t for t in result.all_results if t.status == "evaluated"]
        assert len(evaluated) > 0
        max_metric = max(t.metric for t in evaluated if math.isfinite(t.metric))
        assert result.best_metric == pytest.approx(max_metric)

    @pytest.mark.test_id("4.2-ATDD-002")
    @pytest.mark.p0
    def test_median_pruning_reduces_trials(self, wf_ohlcv):
        is_window = wf_ohlcv.iloc[:120]
        cfg = OptimizationConfig(
            param_ranges={
                "fast": [5, 10, 15, 20, 25, 30, 35],
                "slow": [30, 40, 50, 60, 80, 100, 120],
            },
            pruning=PruningConfig(enabled=True, min_trials_before_prune=5),
            max_trials=49,
        )
        result = optimize_is_window(is_window, cfg, _make_sma_factory(), BacktestConfig(), seed=42)

        assert result.n_pruned > 0
        evaluated = [t for t in result.all_results if t.status == "evaluated"]
        assert len(evaluated) >= cfg.pruning.min_trials_before_prune

    @pytest.mark.test_id("4.2-ATDD-003")
    @pytest.mark.p0
    def test_constraints_enforced(self, wf_ohlcv):
        is_window = wf_ohlcv.iloc[:120]
        cfg = OptimizationConfig(
            param_ranges={"fast": [5, 10, 20, 50], "slow": [10, 30, 50, 80]},
            pruning=PruningConfig(enabled=False),
            constraints=[monotonic_increasing("fast", "slow")],
        )
        result = optimize_is_window(is_window, cfg, _make_sma_factory(), BacktestConfig(), seed=42)

        assert result.best_params["fast"] < result.best_params["slow"]

    @pytest.mark.test_id("4.2-ATDD-004")
    @pytest.mark.p1
    def test_best_params_recorded_with_is_metrics(self, wf_ohlcv):
        is_window = wf_ohlcv.iloc[:120]
        cfg = OptimizationConfig(
            param_ranges={"fast": [5, 10], "slow": [30, 50]},
            pruning=PruningConfig(enabled=False),
        )
        result = optimize_is_window(is_window, cfg, _make_sma_factory(), BacktestConfig(), seed=42)

        assert result.all_results is not None
        assert len(result.all_results) > 0
        for trial in result.all_results:
            assert isinstance(trial, TrialResult)
            assert trial.status in ("evaluated", "pruned", "failed")
            assert "params" in trial.__dataclass_fields__

    @pytest.mark.test_id("4.2-ATDD-005")
    @pytest.mark.p1
    def test_seed_hierarchy_respected(self, wf_ohlcv):
        is_window = wf_ohlcv.iloc[:120]
        cfg = OptimizationConfig(
            param_ranges={"fast": [5, 10, 20], "slow": [30, 50, 80]},
            pruning=PruningConfig(enabled=False),
        )

        result_a = optimize_is_window(
            is_window, cfg, _make_sma_factory(), BacktestConfig(), seed=42
        )
        result_b = optimize_is_window(
            is_window, cfg, _make_sma_factory(), BacktestConfig(), seed=42
        )

        assert result_a.best_params == result_b.best_params

    @pytest.mark.test_id("4.2-ATDD-006")
    @pytest.mark.p2
    def test_inverted_range_triggers_constraint(self, wf_ohlcv):
        is_window = wf_ohlcv.iloc[:120]
        cfg = OptimizationConfig(
            param_ranges={"fast": [50], "slow": [10]},
            pruning=PruningConfig(enabled=False),
            constraints=[monotonic_increasing("fast", "slow")],
        )
        result = optimize_is_window(is_window, cfg, _make_sma_factory(), BacktestConfig(), seed=42)
        assert result.n_trials == 1
        failed = [t for t in result.all_results if t.status == "failed"]
        assert len(failed) == 1

    @pytest.mark.test_id("4.2-ATDD-007")
    @pytest.mark.p2
    def test_pruning_disabled_uses_all_trials(self, wf_ohlcv):
        is_window = wf_ohlcv.iloc[:120]
        cfg = OptimizationConfig(
            param_ranges={"fast": [5, 10, 20], "slow": [30, 50, 80]},
            pruning=PruningConfig(enabled=False),
        )
        result = optimize_is_window(is_window, cfg, _make_sma_factory(), BacktestConfig(), seed=42)

        evaluated = [t for t in result.all_results if t.status == "evaluated"]
        assert len(evaluated) == result.n_trials
        assert result.n_pruned == 0
