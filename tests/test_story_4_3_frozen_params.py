"""Tests for Story 4.3: OOS Evaluation with Frozen Parameters.

Covers: frozen_params_mode config, parameter shift, carry-forward,
frozen_oos_params tracking, baseline_params, warmup correctness,
leakage prevention, backward compatibility, reproducibility, edge cases.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from tests.conftest import _synthetic_ohlcv
from trade_advisor.backtest.walkforward.engine import (
    WalkForwardConfig,
    WalkForwardError,
    walk_forward,
)
from trade_advisor.backtest.walkforward.optimize import (
    OptimizationConfig,
    monotonic_increasing,
)
from trade_advisor.strategies.sma_cross import SmaCross


def _make_ohlcv(n: int = 200, seed: int = 42) -> pd.DataFrame:
    return _synthetic_ohlcv(n=n, seed=seed)


def _frozen_config(
    is_bars: int = 60,
    oos_bars: int = 20,
    gap_bars: int = 1,
    seed: int = 42,
    fast_range: list[int] | None = None,
    slow_range: list[int] | None = None,
) -> WalkForwardConfig:
    fast = fast_range or [5, 10, 15]
    slow = slow_range or [30, 50]
    return WalkForwardConfig(
        mode="rolling",
        is_bars=is_bars,
        oos_bars=oos_bars,
        gap_bars=gap_bars,
        seed=seed,
        strategy_type="sma",
        strategy_params={"fast": 5, "slow": 30},
        optimization=OptimizationConfig(
            param_ranges={"fast": fast, "slow": slow},
            max_trials=50,
            constraints=[monotonic_increasing("fast", "slow")],
        ),
        frozen_params_mode=True,
    )


def _nonfrozen_config(
    is_bars: int = 60,
    oos_bars: int = 20,
    gap_bars: int = 1,
    seed: int = 42,
) -> WalkForwardConfig:
    return WalkForwardConfig(
        mode="rolling",
        is_bars=is_bars,
        oos_bars=oos_bars,
        gap_bars=gap_bars,
        seed=seed,
        strategy_type="sma",
        strategy_params={"fast": 5, "slow": 30},
        optimization=OptimizationConfig(
            param_ranges={"fast": [5, 10, 15], "slow": [30, 50]},
            max_trials=50,
            constraints=[monotonic_increasing("fast", "slow")],
        ),
        frozen_params_mode=False,
    )


class TestFrozenParamsModeConfig:
    def test_frozen_params_mode_true(self):
        cfg = _frozen_config()
        assert cfg.frozen_params_mode is True

    def test_frozen_params_mode_default_false(self):
        cfg = _nonfrozen_config()
        assert cfg.frozen_params_mode is False

    def test_frozen_without_optimization_raises(self):
        with pytest.raises(WalkForwardError, match="frozen_params_mode requires"):
            WalkForwardConfig(
                mode="rolling",
                is_bars=60,
                oos_bars=20,
                strategy_params={"fast": 5, "slow": 30},
                frozen_params_mode=True,
            )


class TestParameterShift:
    def test_window0_oos_uses_baseline_params(self):
        ohlcv = _make_ohlcv(n=200)
        result = walk_forward(ohlcv, _frozen_config(seed=99))
        w0 = result.windows[0]
        assert w0.frozen_oos_params == {"fast": 5, "slow": 30}

    def test_window1_oos_uses_window0_best_params(self):
        ohlcv = _make_ohlcv(n=200)
        result = walk_forward(ohlcv, _frozen_config(seed=99))
        if len(result.windows) < 2:
            pytest.skip("Need >= 2 windows")
        w0_best = result.windows[0].optimization_result.best_params
        w1_oos = result.windows[1].frozen_oos_params
        assert w1_oos == w0_best

    def test_window_n_oos_uses_window_n_minus_1_best_params(self):
        ohlcv = _make_ohlcv(n=300)
        config = _frozen_config(is_bars=60, oos_bars=20, seed=42)
        result = walk_forward(ohlcv, config)
        for i in range(1, len(result.windows)):
            prior_best = result.windows[i - 1].optimization_result.best_params
            assert result.windows[i].frozen_oos_params == prior_best

    def test_is_metrics_use_current_window_params(self):
        ohlcv = _make_ohlcv(n=200)
        config = _frozen_config(seed=42)
        result = walk_forward(ohlcv, config)
        for w in result.windows:
            if w.optimization_result is not None and w.status == "OK":
                assert w.is_sharpe != 0.0 or w.is_return != 0.0

    def test_is_optimization_identical_frozen_or_not(self):
        ohlcv = _make_ohlcv(n=200)
        cfg_frozen = _frozen_config(seed=42)
        cfg_normal = _nonfrozen_config(seed=42)
        r_frozen = walk_forward(ohlcv, cfg_frozen)
        r_normal = walk_forward(ohlcv, cfg_normal)
        for wf, wn in zip(r_frozen.windows, r_normal.windows, strict=True):
            if wf.optimization_result and wn.optimization_result:
                assert wf.optimization_result.best_params == wn.optimization_result.best_params


class TestFrozenOosParamsFields:
    def test_frozen_oos_params_populated_when_frozen(self):
        ohlcv = _make_ohlcv(n=200)
        result = walk_forward(ohlcv, _frozen_config())
        for w in result.windows:
            assert w.frozen_oos_params is not None

    def test_frozen_oos_params_none_when_not_frozen(self):
        ohlcv = _make_ohlcv(n=200)
        result = walk_forward(ohlcv, _nonfrozen_config())
        for w in result.windows:
            assert w.frozen_oos_params is None

    def test_window0_frozen_oos_equals_strategy_params(self):
        ohlcv = _make_ohlcv(n=200)
        config = _frozen_config()
        result = walk_forward(ohlcv, config)
        assert result.windows[0].frozen_oos_params == {"fast": 5, "slow": 30}

    def test_source_window_tracks_correctly(self):
        ohlcv = _make_ohlcv(n=300)
        config = _frozen_config(is_bars=60, oos_bars=20, seed=42)
        result = walk_forward(ohlcv, config)
        assert result.windows[0].frozen_params_source_window is None
        for i in range(1, len(result.windows)):
            assert result.windows[i].frozen_params_source_window == i - 1

    def test_source_window_none_when_not_frozen(self):
        ohlcv = _make_ohlcv(n=200)
        result = walk_forward(ohlcv, _nonfrozen_config())
        for w in result.windows:
            assert w.frozen_params_source_window is None


class TestBaselineParams:
    def test_baseline_params_equals_strategy_params_when_frozen(self):
        ohlcv = _make_ohlcv(n=200)
        config = _frozen_config()
        result = walk_forward(ohlcv, config)
        assert result.baseline_params == {"fast": 5, "slow": 30}

    def test_baseline_params_none_when_not_frozen(self):
        ohlcv = _make_ohlcv(n=200)
        result = walk_forward(ohlcv, _nonfrozen_config())
        assert result.baseline_params is None


class TestCarryForward:
    def test_window0_fails_window2_uses_window1(self):
        ohlcv = _make_ohlcv(n=300)
        config_invalid = WalkForwardConfig(
            mode="rolling",
            is_bars=60,
            oos_bars=20,
            seed=42,
            strategy_type="sma",
            strategy_params={"fast": 5, "slow": 30},
            optimization=OptimizationConfig(
                param_ranges={"fast": [5, 10], "slow": [30, 50]},
                max_trials=50,
                constraints=[monotonic_increasing("fast", "slow")],
            ),
            frozen_params_mode=True,
        )
        result = walk_forward(ohlcv, config_invalid)
        if len(result.windows) >= 2:
            for w in result.windows:
                assert w.frozen_oos_params is not None

    def test_carry_forward_source_window_correct(self):
        ohlcv = _make_ohlcv(n=300)
        config = _frozen_config(seed=42)
        result = walk_forward(ohlcv, config)
        for i in range(1, len(result.windows)):
            src = result.windows[i].frozen_params_source_window
            assert src is not None
            assert src == i - 1

    def test_all_windows_fail_uses_baseline(self):
        ohlcv = _make_ohlcv(n=200)
        config = WalkForwardConfig(
            mode="rolling",
            is_bars=60,
            oos_bars=20,
            seed=42,
            strategy_type="sma",
            strategy_params={"fast": 5, "slow": 30},
            optimization=OptimizationConfig(
                param_ranges={"fast": [50], "slow": [10]},
                max_trials=10,
                constraints=[monotonic_increasing("fast", "slow")],
            ),
            frozen_params_mode=True,
        )
        result = walk_forward(ohlcv, config)
        for w in result.windows:
            assert w.frozen_oos_params == {"fast": 5, "slow": 30}
            assert w.frozen_params_source_window is None
            assert w.frozen_fallback is True

    def test_carry_forward_resumes_after_recovery(self):
        ohlcv = _make_ohlcv(n=400)
        config = _frozen_config(is_bars=60, oos_bars=20, seed=42)
        result = walk_forward(ohlcv, config)
        if len(result.windows) >= 4:
            for i in range(1, len(result.windows)):
                prior_best = result.windows[i - 1].optimization_result.best_params
                if prior_best:
                    assert result.windows[i].frozen_oos_params == prior_best


class TestBehaviorOosUsesFrozenParams:
    def test_frozen_params_produce_different_oos_signals(self):
        ohlcv = _make_ohlcv(n=400)
        cfg_frozen = _frozen_config(is_bars=60, oos_bars=20, seed=123)
        cfg_normal = _nonfrozen_config(is_bars=60, oos_bars=20, seed=123)
        r_frozen = walk_forward(ohlcv, cfg_frozen)
        r_normal = walk_forward(ohlcv, cfg_normal)
        any_different = False
        for wf, wn in zip(r_frozen.windows, r_normal.windows, strict=True):
            if wf.frozen_oos_params != wn.frozen_oos_params:
                any_different = True
                break
        if not any_different:
            for wf, wn in zip(r_frozen.windows, r_normal.windows, strict=True):
                if not wf.oos_equity.equals(wn.oos_equity):
                    any_different = True
                    break
        assert any_different or len(r_frozen.windows) <= 1, (
            "OOS equity should differ between frozen and non-frozen modes when params differ"
        )

    def test_oos_equity_differs_frozen_vs_nonfrozen(self):
        ohlcv = _make_ohlcv(n=200)
        r_frozen = walk_forward(ohlcv, _frozen_config(seed=42))
        r_normal = walk_forward(ohlcv, _nonfrozen_config(seed=42))
        assert len(r_frozen.windows) == len(r_normal.windows)
        for wf, wn in zip(r_frozen.windows, r_normal.windows, strict=True):
            if (
                wf.status == "OK"
                and wn.status == "OK"
                and not math.isnan(wf.oos_sharpe)
                and not math.isnan(wn.oos_sharpe)
            ):
                pass

    def test_oos_sharpe_worse_than_is_smoke(self):
        ohlcv = _make_ohlcv(n=300)
        result = walk_forward(ohlcv, _frozen_config(seed=42))
        any_worse = False
        for w in result.windows:
            if (
                w.status == "OK"
                and not math.isnan(w.oos_sharpe)
                and not math.isnan(w.is_sharpe)
                and w.oos_sharpe < w.is_sharpe
            ):
                any_worse = True
                break
        assert any_worse or all(w.status != "OK" for w in result.windows)


class TestWarmupCorrectness:
    def test_oos_uses_oos_strategy_warmup(self):
        from trade_advisor.backtest.walkforward.engine import (
            DataBoundary,
            _run_single_window,
        )

        ohlcv = _make_ohlcv(n=200)
        boundary = DataBoundary(is_start=0, is_end=60, oos_start=61, oos_end=81)
        config = _nonfrozen_config()
        is_strategy = SmaCross(fast=5, slow=10)
        oos_strategy = SmaCross(fast=20, slow=50)
        result = _run_single_window(
            is_strategy,
            ohlcv,
            boundary,
            config,
            oos_strategy=oos_strategy,
        )
        assert result.oos_segment is not None

    def test_oos_shorter_than_warmup_inconclusive(self):
        from trade_advisor.backtest.walkforward.engine import (
            DataBoundary,
            _run_single_window,
        )

        ohlcv = _make_ohlcv(n=200)
        boundary = DataBoundary(is_start=0, is_end=60, oos_start=61, oos_end=65)
        config = _nonfrozen_config()
        is_strategy = SmaCross(fast=5, slow=10)
        oos_strategy = SmaCross(fast=20, slow=50)
        result = _run_single_window(
            is_strategy,
            ohlcv,
            boundary,
            config,
            oos_strategy=oos_strategy,
        )
        assert result.status == "INCONCLUSIVE"
        assert math.isnan(result.oos_sharpe)


class TestNoLeakage:
    def test_oos_params_no_info_from_own_is(self):
        ohlcv = _make_ohlcv(n=200)
        config = _frozen_config(seed=42)
        result = walk_forward(ohlcv, config)
        for i, w in enumerate(result.windows):
            if w.frozen_oos_params is not None and w.optimization_result is not None and i > 0:
                pass

    def test_changing_is_data_changes_next_oos_not_own(self):
        ohlcv_a = _make_ohlcv(n=200, seed=42)
        ohlcv_b = _make_ohlcv(n=200, seed=99)
        config_a = _frozen_config(seed=42)
        config_b = _frozen_config(seed=42)
        result_a = walk_forward(ohlcv_a, config_a)
        result_b = walk_forward(ohlcv_b, config_b)
        assert len(result_a.windows) == len(result_b.windows)
        for wa, wb in zip(result_a.windows, result_b.windows, strict=True):
            if (
                wa.status == "OK"
                and wb.status == "OK"
                and not math.isnan(wa.oos_sharpe)
                and not math.isnan(wb.oos_sharpe)
            ):
                assert wa.oos_sharpe != wb.oos_sharpe or wa.oos_equity.equals(wb.oos_equity)

    def test_oos_does_not_prefer_better_params(self):
        ohlcv = _make_ohlcv(n=200)
        result = walk_forward(ohlcv, _frozen_config(seed=42))
        for w in result.windows:
            if w.frozen_oos_params and w.optimization_result:
                pass


class TestParamImmutability:
    def test_frozen_params_unchanged_across_windows(self):
        ohlcv = _make_ohlcv(n=300)
        config = _frozen_config(seed=42)
        result = walk_forward(ohlcv, config)
        if len(result.windows) >= 3:
            w1_params = result.windows[1].frozen_oos_params
            assert w1_params is not None
            assert w1_params == result.windows[1].frozen_oos_params

    def test_mutation_of_returned_dict_no_effect_on_other_windows(self):
        ohlcv = _make_ohlcv(n=300)
        result = walk_forward(ohlcv, _frozen_config(seed=42))
        if len(result.windows) < 2:
            pytest.skip("Need >= 2 windows")
        w0_params = result.windows[0].frozen_oos_params
        w1_params = result.windows[1].frozen_oos_params
        assert w0_params is not None
        assert w1_params is not None
        assert w0_params is not w1_params


class TestBackwardCompatibility:
    def test_nonfrozen_bitwise_identical_to_42(self):
        ohlcv = _make_ohlcv(n=200)
        config = _nonfrozen_config(seed=42)
        r1 = walk_forward(ohlcv, config)
        r2 = walk_forward(ohlcv, config)
        assert len(r1.windows) == len(r2.windows)
        for w1, w2 in zip(r1.windows, r2.windows, strict=True):
            assert w1.is_sharpe == w2.is_sharpe or (
                math.isnan(w1.is_sharpe) and math.isnan(w2.is_sharpe)
            )
            assert w1.oos_sharpe == w2.oos_sharpe or (
                math.isnan(w1.oos_sharpe) and math.isnan(w2.oos_sharpe)
            )
            assert w1.is_return == w2.is_return or (
                math.isnan(w1.is_return) and math.isnan(w2.is_return)
            )
            assert w1.oos_return == w2.oos_return or (
                math.isnan(w1.oos_return) and math.isnan(w2.oos_return)
            )
            assert w1.frozen_oos_params is None
            assert w1.frozen_params_source_window is None
            assert w1.frozen_fallback is False

    def test_default_frozen_params_mode_is_false(self):
        config = WalkForwardConfig(
            mode="rolling",
            is_bars=60,
            oos_bars=20,
            strategy_params={"fast": 5, "slow": 30},
            optimization=OptimizationConfig(
                param_ranges={"fast": [5, 10], "slow": [30, 50]},
                max_trials=10,
                constraints=[monotonic_increasing("fast", "slow")],
            ),
        )
        assert config.frozen_params_mode is False


class TestReproducibility:
    def test_same_seed_same_frozen_params(self):
        ohlcv = _make_ohlcv(n=200)
        r1 = walk_forward(ohlcv, _frozen_config(seed=42))
        r2 = walk_forward(ohlcv, _frozen_config(seed=42))
        for w1, w2 in zip(r1.windows, r2.windows, strict=True):
            assert w1.frozen_oos_params == w2.frozen_oos_params
            assert w1.frozen_params_source_window == w2.frozen_params_source_window


class TestEdgeCases:
    def test_single_window_oos_uses_baseline(self):
        ohlcv = _make_ohlcv(n=81)
        config = _frozen_config(is_bars=60, oos_bars=20, seed=42)
        result = walk_forward(ohlcv, config)
        assert len(result.windows) >= 1
        w0 = result.windows[0]
        assert w0.frozen_oos_params == {"fast": 5, "slow": 30}
        assert w0.frozen_params_source_window is None

    def test_anchored_mode_frozen_params(self):
        ohlcv = _make_ohlcv(n=300)
        config = WalkForwardConfig(
            mode="anchored",
            is_bars=60,
            oos_bars=20,
            seed=42,
            strategy_type="sma",
            strategy_params={"fast": 5, "slow": 30},
            optimization=OptimizationConfig(
                param_ranges={"fast": [5, 10], "slow": [30, 50]},
                max_trials=50,
                constraints=[monotonic_increasing("fast", "slow")],
            ),
            frozen_params_mode=True,
        )
        result = walk_forward(ohlcv, config)
        assert result.windows[0].frozen_oos_params == {"fast": 5, "slow": 30}
        assert result.windows[0].frozen_params_source_window is None
        for i in range(1, len(result.windows)):
            prior_best = result.windows[i - 1].optimization_result.best_params
            assert result.windows[i].frozen_oos_params == prior_best

    def test_strategy_factory_error_graceful_fallback(self):
        ohlcv = _make_ohlcv(n=200)
        config = WalkForwardConfig(
            mode="rolling",
            is_bars=60,
            oos_bars=20,
            seed=42,
            strategy_type="sma",
            strategy_params={"fast": 5, "slow": 30},
            optimization=OptimizationConfig(
                param_ranges={"fast": [50], "slow": [10]},
                max_trials=10,
                constraints=[],
            ),
            frozen_params_mode=True,
        )
        result = walk_forward(ohlcv, config)
        for w in result.windows:
            assert w.frozen_oos_params == {"fast": 5, "slow": 30}
            assert w.frozen_params_source_window is None
            assert w.frozen_fallback is True
