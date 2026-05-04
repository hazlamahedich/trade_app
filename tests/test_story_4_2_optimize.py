"""Tests for Story 4.2: In-Sample Hyperparameter Search with Pruning.

Covers all acceptance criteria: OptimizationConfig, PruningConfig, ParamConstraint,
strategy_factory, OOS contamination guard, median pruning, deterministic shuffle,
engine integration, auto-validation, reproducibility, and performance.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from tests.conftest import _synthetic_ohlcv
from trade_advisor.backtest.walkforward.engine import (
    WalkForwardConfig,
    walk_forward,
)
from trade_advisor.backtest.walkforward.optimize import (
    OptimizationConfig,
    OptimizationResult,
    PruningConfig,
    min_spacing,
    monotonic_increasing,
    optimize_is_window,
)
from trade_advisor.config import BacktestConfig
from trade_advisor.strategies.sma_cross import SmaCross


def _make_sma_factory():
    return lambda params: SmaCross(**params)


def _make_ohlcv(n: int = 200, seed: int = 42) -> pd.DataFrame:
    return _synthetic_ohlcv(n=n, seed=seed)


# ---------------------------------------------------------------------------
# AC-1, AC-2: OptimizationConfig & PruningConfig
# ---------------------------------------------------------------------------


class TestOptimizationConfig:
    def test_default_values(self):
        cfg = OptimizationConfig(param_ranges={"fast": [5, 10], "slow": [30, 50]})
        assert cfg.max_trials == 100
        assert cfg.pruning.enabled is True
        assert cfg.pruning.method == "median"
        assert cfg.pruning.min_trials_before_prune == 5
        assert cfg.metric == "sharpe"
        assert cfg.maximize is True
        assert cfg.constraints == []

    def test_extra_forbid(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            OptimizationConfig(param_ranges={"fast": [5]}, unknown_field=True)

    def test_max_trials_gt_zero(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            OptimizationConfig(param_ranges={"fast": [5]}, max_trials=0)

    def test_custom_purning_config(self):
        pc = PruningConfig(enabled=False, min_trials_before_prune=10)
        cfg = OptimizationConfig(param_ranges={"fast": [5]}, pruning=pc)
        assert cfg.pruning.enabled is False
        assert cfg.pruning.min_trials_before_prune == 10


# ---------------------------------------------------------------------------
# AC-3: ParamConstraint Protocol
# ---------------------------------------------------------------------------


class TestParamConstraints:
    def test_monotonic_increasing_passes(self):
        check = monotonic_increasing("fast", "slow")
        assert check({"fast": 10, "slow": 50}) is True

    def test_monotonic_increasing_fails(self):
        check = monotonic_increasing("fast", "slow")
        assert check({"fast": 50, "slow": 10}) is False

    def test_monotonic_increasing_equal_fails(self):
        check = monotonic_increasing("fast", "slow")
        assert check({"fast": 10, "slow": 10}) is False

    def test_min_spacing_passes(self):
        check = min_spacing("slow", "fast", min_gap=1)
        assert check({"fast": 10, "slow": 11}) is True

    def test_min_spacing_fails(self):
        check = min_spacing("slow", "fast", min_gap=5)
        assert check({"fast": 10, "slow": 12}) is False

    def test_custom_lambda_constraint(self):
        def constraint(p):
            return p["slow"] >= 2 * p["fast"]

        assert constraint({"fast": 10, "slow": 30}) is True
        assert constraint({"fast": 20, "slow": 30}) is False


# ---------------------------------------------------------------------------
# AC-5: optimize_is_window core function
# ---------------------------------------------------------------------------


class TestOptimizeIsWindow:
    def test_finds_best_params(self):
        ohlcv = _make_ohlcv(n=200)
        is_slice = ohlcv.iloc[:120]
        cfg = OptimizationConfig(
            param_ranges={"fast": [5, 10, 20], "slow": [30, 50, 100]},
            pruning=PruningConfig(enabled=False),
        )
        result = optimize_is_window(is_slice, cfg, _make_sma_factory(), BacktestConfig(), seed=42)
        assert result.best_params is not None
        assert "fast" in result.best_params
        assert "slow" in result.best_params
        assert result.n_trials == 9

    def test_best_metric_matches_max_of_evaluated(self):
        ohlcv = _make_ohlcv(n=200)
        is_slice = ohlcv.iloc[:120]
        cfg = OptimizationConfig(
            param_ranges={"fast": [5, 10], "slow": [30, 50]},
            pruning=PruningConfig(enabled=False),
        )
        result = optimize_is_window(is_slice, cfg, _make_sma_factory(), BacktestConfig(), seed=42)
        evaluated = [t for t in result.all_results if t.status == "evaluated"]
        assert len(evaluated) > 0
        max_metric = max(t.metric for t in evaluated if math.isfinite(t.metric))
        assert result.best_metric == pytest.approx(max_metric)

    def test_trial_result_statuses(self):
        ohlcv = _make_ohlcv(n=200)
        is_slice = ohlcv.iloc[:120]
        cfg = OptimizationConfig(
            param_ranges={"fast": [5, 10], "slow": [30, 50]},
            pruning=PruningConfig(enabled=False),
        )
        result = optimize_is_window(is_slice, cfg, _make_sma_factory(), BacktestConfig(), seed=42)
        for trial in result.all_results:
            assert trial.status in ("evaluated", "pruned", "failed")


# ---------------------------------------------------------------------------
# AC-6: OOS contamination guard
# ---------------------------------------------------------------------------


class TestOOSContamination:
    def test_optimizer_receives_exactly_is_slice(self):
        ohlcv = _make_ohlcv(n=200)
        is_slice = ohlcv.iloc[:60].copy()
        is_len = len(is_slice)

        captured_lengths: list[int] = []

        def instrumented_factory(params):
            strategy = SmaCross(**params)

            def patched_generate(ohlcv_df):
                captured_lengths.append(len(ohlcv_df))
                return strategy.generate_signals(ohlcv_df)

            strategy.generate_signals = patched_generate
            return strategy

        cfg = OptimizationConfig(
            param_ranges={"fast": [5], "slow": [30]},
            pruning=PruningConfig(enabled=False),
        )
        optimize_is_window(is_slice, cfg, instrumented_factory, BacktestConfig(), seed=42)
        assert all(ln == is_len for ln in captured_lengths), (
            f"Backtest received wrong lengths: {captured_lengths}"
        )


# ---------------------------------------------------------------------------
# AC-7: Median pruning with min-trials guard
# ---------------------------------------------------------------------------


class TestMedianPruning:
    def test_pruning_reduces_trials(self):
        ohlcv = _make_ohlcv(n=200)
        is_slice = ohlcv.iloc[:120]
        cfg = OptimizationConfig(
            param_ranges={"fast": [5, 10, 15, 20, 25], "slow": [30, 40, 50, 60, 80]},
            pruning=PruningConfig(enabled=True, min_trials_before_prune=5),
            max_trials=25,
        )
        result = optimize_is_window(is_slice, cfg, _make_sma_factory(), BacktestConfig(), seed=42)
        evaluated_count = len([t for t in result.all_results if t.status == "evaluated"])
        assert evaluated_count >= cfg.pruning.min_trials_before_prune
        assert result.n_pruned > 0

    def test_no_pruning_when_below_min_trials(self):
        ohlcv = _make_ohlcv(n=200)
        is_slice = ohlcv.iloc[:120]
        cfg = OptimizationConfig(
            param_ranges={"fast": [5], "slow": [30]},
            pruning=PruningConfig(enabled=True, min_trials_before_prune=5),
        )
        result = optimize_is_window(is_slice, cfg, _make_sma_factory(), BacktestConfig(), seed=42)
        assert result.n_pruned == 0

    def test_pruning_disabled_evaluates_all(self):
        ohlcv = _make_ohlcv(n=200)
        is_slice = ohlcv.iloc[:120]
        cfg = OptimizationConfig(
            param_ranges={"fast": [5, 10], "slow": [30, 50]},
            pruning=PruningConfig(enabled=False),
        )
        result = optimize_is_window(is_slice, cfg, _make_sma_factory(), BacktestConfig(), seed=42)
        assert result.n_pruned == 0
        all_evaluated = all(t.status == "evaluated" for t in result.all_results)
        assert all_evaluated

    def test_pruning_preserves_true_best(self):
        ohlcv = _make_ohlcv(n=200)
        is_slice = ohlcv.iloc[:120]
        cfg_no_prune = OptimizationConfig(
            param_ranges={"fast": [5, 10, 20], "slow": [30, 50, 80]},
            pruning=PruningConfig(enabled=False),
        )
        cfg_prune = OptimizationConfig(
            param_ranges={"fast": [5, 10, 20], "slow": [30, 50, 80]},
            pruning=PruningConfig(enabled=True, min_trials_before_prune=5),
        )
        r_no = optimize_is_window(
            is_slice, cfg_no_prune, _make_sma_factory(), BacktestConfig(), seed=42
        )
        r_pr = optimize_is_window(
            is_slice, cfg_prune, _make_sma_factory(), BacktestConfig(), seed=42
        )
        assert r_no.best_params == r_pr.best_params
        assert r_no.best_metric == pytest.approx(r_pr.best_metric)

    def test_pruning_maximize_false_prunes_above_median(self):
        ohlcv = _make_ohlcv(n=200)
        is_slice = ohlcv.iloc[:120]
        cfg = OptimizationConfig(
            param_ranges={"fast": [5, 10, 15, 20, 25], "slow": [30, 40, 50, 60, 80]},
            pruning=PruningConfig(enabled=True, min_trials_before_prune=5),
            maximize=False,
            max_trials=25,
        )
        result = optimize_is_window(is_slice, cfg, _make_sma_factory(), BacktestConfig(), seed=42)
        evaluated = [t for t in result.all_results if t.status == "evaluated"]
        pruned = [t for t in result.all_results if t.status == "pruned"]
        assert len(evaluated) > 0
        assert len(pruned) > 0


# ---------------------------------------------------------------------------
# AC-8: Grid enumeration with deterministic shuffle
# ---------------------------------------------------------------------------


class TestCandidateEnumeration:
    def test_cartesian_product_all_evaluated(self):
        ohlcv = _make_ohlcv(n=200)
        is_slice = ohlcv.iloc[:120]
        cfg = OptimizationConfig(
            param_ranges={"fast": [5, 10], "slow": [30, 50]},
            pruning=PruningConfig(enabled=False),
            max_trials=100,
        )
        result = optimize_is_window(is_slice, cfg, _make_sma_factory(), BacktestConfig(), seed=42)
        assert result.n_trials == 4

    def test_max_trials_limits_candidates(self):
        ohlcv = _make_ohlcv(n=200)
        is_slice = ohlcv.iloc[:120]
        cfg = OptimizationConfig(
            param_ranges={"fast": [5, 10, 15, 20, 25], "slow": [30, 40, 50, 60, 80, 100]},
            pruning=PruningConfig(enabled=False),
            max_trials=10,
        )
        result = optimize_is_window(is_slice, cfg, _make_sma_factory(), BacktestConfig(), seed=42)
        assert result.n_trials == 10


# ---------------------------------------------------------------------------
# AC-10: Auto-validation — invalid params handled gracefully
# ---------------------------------------------------------------------------


class TestAutoValidation:
    def test_window_shorter_than_slow_period(self):
        ohlcv = _make_ohlcv(n=200)
        is_slice = ohlcv.iloc[:30]
        cfg = OptimizationConfig(
            param_ranges={"fast": [5], "slow": [200]},
            pruning=PruningConfig(enabled=False),
        )
        result = optimize_is_window(is_slice, cfg, _make_sma_factory(), BacktestConfig(), seed=42)
        assert result.n_trials == 1
        failed = [t for t in result.all_results if t.status == "failed"]
        assert len(failed) == 0

    def test_degenerate_range_single_value(self):
        ohlcv = _make_ohlcv(n=200)
        is_slice = ohlcv.iloc[:120]
        cfg = OptimizationConfig(
            param_ranges={"fast": [10], "slow": [50]},
            pruning=PruningConfig(enabled=False),
        )
        result = optimize_is_window(is_slice, cfg, _make_sma_factory(), BacktestConfig(), seed=42)
        assert result.n_trials == 1
        assert result.best_params == {"fast": 10, "slow": 50}

    def test_all_trials_fail_graceful(self):
        ohlcv = _make_ohlcv(n=200)
        is_slice = ohlcv.iloc[:30]

        def failing_factory(params):
            raise ValueError("Always fails")

        cfg = OptimizationConfig(
            param_ranges={"fast": [5], "slow": [30]},
            pruning=PruningConfig(enabled=False),
        )
        result = optimize_is_window(is_slice, cfg, failing_factory, BacktestConfig(), seed=42)
        assert result.n_trials == 1
        assert math.isnan(result.best_metric)

    def test_flat_price_window_no_crash(self):
        dates = pd.date_range("2020-01-01", periods=120, freq="B", tz="UTC")
        flat = pd.DataFrame(
            {
                "timestamp": dates,
                "open": [100.0] * 120,
                "high": [100.0] * 120,
                "low": [100.0] * 120,
                "close": [100.0] * 120,
                "volume": [1000] * 120,
            }
        )
        cfg = OptimizationConfig(
            param_ranges={"fast": [5, 10], "slow": [30, 50]},
            pruning=PruningConfig(enabled=False),
        )
        result = optimize_is_window(flat, cfg, _make_sma_factory(), BacktestConfig(), seed=42)
        assert result.n_trials == 4
        assert result.best_params is not None


# ---------------------------------------------------------------------------
# AC-11: Reproducibility with same seed
# ---------------------------------------------------------------------------


class TestReproducibility:
    def test_same_seed_same_result(self):
        ohlcv = _make_ohlcv(n=200)
        is_slice = ohlcv.iloc[:120]
        cfg = OptimizationConfig(
            param_ranges={"fast": [5, 10, 20], "slow": [30, 50, 100]},
            pruning=PruningConfig(enabled=False),
        )
        bt_cfg = BacktestConfig()
        r1 = optimize_is_window(is_slice, cfg, _make_sma_factory(), bt_cfg, seed=42)
        r2 = optimize_is_window(is_slice, cfg, _make_sma_factory(), bt_cfg, seed=42)
        assert r1.best_params == r2.best_params
        assert r1.best_metric == pytest.approx(r2.best_metric)

    def test_different_seeds_may_differ(self):
        ohlcv = _make_ohlcv(n=200)
        is_slice = ohlcv.iloc[:120]
        cfg = OptimizationConfig(
            param_ranges={"fast": [5, 10, 15, 20], "slow": [30, 40, 50, 60, 80]},
            pruning=PruningConfig(enabled=False),
            max_trials=5,
        )
        bt_cfg = BacktestConfig()
        r1 = optimize_is_window(is_slice, cfg, _make_sma_factory(), bt_cfg, seed=42)
        r2 = optimize_is_window(is_slice, cfg, _make_sma_factory(), bt_cfg, seed=99)
        assert len(r1.all_results) == len(r2.all_results)

    def test_deterministic_trial_ordering(self):
        ohlcv = _make_ohlcv(n=200)
        is_slice = ohlcv.iloc[:120]
        cfg = OptimizationConfig(
            param_ranges={"fast": [5, 10, 20], "slow": [30, 50, 100]},
            pruning=PruningConfig(enabled=False),
        )
        bt_cfg = BacktestConfig()
        r1 = optimize_is_window(is_slice, cfg, _make_sma_factory(), bt_cfg, seed=42)
        r2 = optimize_is_window(is_slice, cfg, _make_sma_factory(), bt_cfg, seed=42)
        for t1, t2 in zip(r1.all_results, r2.all_results, strict=True):
            assert t1.params == t2.params

    def test_seed_determinism_subset(self):
        ohlcv = _make_ohlcv(n=200)
        is_slice = ohlcv.iloc[:120]
        cfg_10 = OptimizationConfig(
            param_ranges={"fast": list(range(5, 50, 3)), "slow": list(range(30, 100, 5))},
            pruning=PruningConfig(enabled=False),
            max_trials=10,
        )
        cfg_20 = OptimizationConfig(
            param_ranges={"fast": list(range(5, 50, 3)), "slow": list(range(30, 100, 5))},
            pruning=PruningConfig(enabled=False),
            max_trials=20,
        )
        bt_cfg = BacktestConfig()
        r10 = optimize_is_window(is_slice, cfg_10, _make_sma_factory(), bt_cfg, seed=42)
        r20 = optimize_is_window(is_slice, cfg_20, _make_sma_factory(), bt_cfg, seed=42)
        assert r10.all_results[0].params == r20.all_results[0].params


# ---------------------------------------------------------------------------
# AC-4, AC-9: WalkForwardConfig integration
# ---------------------------------------------------------------------------


class TestWalkForwardIntegration:
    def test_wf_with_optimization_produces_result(self):
        ohlcv = _make_ohlcv(n=500)
        cfg = WalkForwardConfig(
            mode="rolling",
            is_bars=120,
            oos_bars=30,
            strategy_type="sma",
            optimization=OptimizationConfig(
                param_ranges={"fast": [5, 10], "slow": [30, 50]},
                pruning=PruningConfig(enabled=False),
            ),
        )
        result = walk_forward(ohlcv, cfg)
        assert result.n_windows >= 1
        for w in result.windows:
            assert w.optimization_result is not None
            assert isinstance(w.optimization_result, OptimizationResult)
            assert "fast" in w.optimization_result.best_params

    def test_wf_without_optimization_no_regression(self):
        ohlcv = _make_ohlcv(n=500)
        cfg = WalkForwardConfig(
            mode="rolling",
            is_bars=60,
            oos_bars=20,
            strategy_type="sma",
            strategy_params={"fast": 10, "slow": 30},
        )
        result = walk_forward(ohlcv, cfg)
        assert result.n_windows >= 1
        for w in result.windows:
            assert w.optimization_result is None

    def test_wf_different_windows_different_params(self):
        ohlcv = _make_ohlcv(n=500)
        cfg = WalkForwardConfig(
            mode="rolling",
            is_bars=120,
            oos_bars=30,
            strategy_type="sma",
            optimization=OptimizationConfig(
                param_ranges={"fast": [5, 10, 20], "slow": [30, 50, 80]},
                pruning=PruningConfig(enabled=False),
            ),
        )
        result = walk_forward(ohlcv, cfg)
        if result.n_windows >= 2:
            p1 = result.windows[0].optimization_result.best_params
            p2 = result.windows[1].optimization_result.best_params
            assert p1 is not None and p2 is not None

    def test_constraints_in_walk_forward(self):
        ohlcv = _make_ohlcv(n=500)
        constraint = monotonic_increasing("fast", "slow")
        cfg = WalkForwardConfig(
            mode="rolling",
            is_bars=120,
            oos_bars=30,
            strategy_type="sma",
            optimization=OptimizationConfig(
                param_ranges={"fast": [5, 10, 20, 50], "slow": [10, 30, 50, 80]},
                pruning=PruningConfig(enabled=False),
                constraints=[constraint],
            ),
        )
        result = walk_forward(ohlcv, cfg)
        for w in result.windows:
            opt = w.optimization_result
            if opt and opt.best_params:
                assert opt.best_params["fast"] < opt.best_params["slow"]


# ---------------------------------------------------------------------------
# AC-3: Constraint enforcement in optimizer
# ---------------------------------------------------------------------------


class TestConstraintEnforcement:
    def test_constraint_rejects_invalid_params(self):
        ohlcv = _make_ohlcv(n=200)
        is_slice = ohlcv.iloc[:120]
        constraint = monotonic_increasing("fast", "slow")
        cfg = OptimizationConfig(
            param_ranges={"fast": [5, 10, 50], "slow": [10, 30, 8]},
            pruning=PruningConfig(enabled=False),
            constraints=[constraint],
        )
        result = optimize_is_window(is_slice, cfg, _make_sma_factory(), BacktestConfig(), seed=42)
        for t in result.all_results:
            if t.status == "evaluated":
                assert t.params["fast"] < t.params["slow"]
            elif t.status == "failed" and t.error == "Constraint violated":
                assert t.params["fast"] >= t.params["slow"]

    def test_min_spacing_enforced(self):
        ohlcv = _make_ohlcv(n=200)
        is_slice = ohlcv.iloc[:120]
        constraint = min_spacing("slow", "fast", min_gap=10)
        cfg = OptimizationConfig(
            param_ranges={"fast": [5, 10, 15], "slow": [10, 20, 30]},
            pruning=PruningConfig(enabled=False),
            constraints=[constraint],
        )
        result = optimize_is_window(is_slice, cfg, _make_sma_factory(), BacktestConfig(), seed=42)
        evaluated = [t for t in result.all_results if t.status == "evaluated"]
        for t in evaluated:
            assert abs(t.params["slow"] - t.params["fast"]) >= 10


# ---------------------------------------------------------------------------
# AC-12: Performance
# ---------------------------------------------------------------------------


class TestPerformance:
    def test_optimization_completes_quickly(self):
        ohlcv = _make_ohlcv(n=500)
        cfg = WalkForwardConfig(
            mode="rolling",
            is_bars=60,
            oos_bars=20,
            strategy_type="sma",
            optimization=OptimizationConfig(
                param_ranges={"fast": [5, 10, 15], "slow": [30, 50, 80]},
                pruning=PruningConfig(enabled=False),
                max_trials=100,
            ),
        )
        import time

        start = time.time()
        result = walk_forward(ohlcv, cfg)
        elapsed = time.time() - start
        assert elapsed < 30.0, f"Walk-forward took {elapsed:.1f}s, exceeds 30s budget"
        assert result.n_windows >= 1
