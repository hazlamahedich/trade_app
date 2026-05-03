"""ATDD: Story 4.3 — OOS Evaluation with Frozen Parameters.

Acceptance tests verifying the walk-forward frozen params protocol.
Uses the actual WalkForwardConfig / walk_forward() API.
"""

from __future__ import annotations

import math

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


def _frozen_cfg(**overrides) -> WalkForwardConfig:
    defaults = {
        "mode": "rolling",
        "is_bars": 60,
        "oos_bars": 20,
        "gap_bars": 1,
        "seed": 42,
        "strategy_type": "sma",
        "strategy_params": {"fast": 5, "slow": 30},
        "optimization": OptimizationConfig(
            param_ranges={"fast": [5, 10, 15], "slow": [30, 50]},
            max_trials=50,
            constraints=[monotonic_increasing("fast", "slow")],
        ),
        "frozen_params_mode": True,
    }
    defaults.update(overrides)
    return WalkForwardConfig(**defaults)


class TestStory43FrozenParams:
    @pytest.mark.test_id("4.3-ATDD-001")
    @pytest.mark.p0
    def test_frozen_without_optimization_raises(self):
        with pytest.raises(WalkForwardError, match="frozen_params_mode requires"):
            WalkForwardConfig(
                mode="rolling",
                is_bars=60,
                oos_bars=20,
                strategy_params={"fast": 5, "slow": 30},
                frozen_params_mode=True,
            )

    @pytest.mark.test_id("4.3-ATDD-002")
    @pytest.mark.p0
    def test_oos_uses_prior_window_best_params(self):
        ohlcv = _synthetic_ohlcv(n=300)
        result = walk_forward(ohlcv, _frozen_cfg())
        for i in range(1, len(result.windows)):
            prior_best = result.windows[i - 1].optimization_result.best_params
            assert result.windows[i].frozen_oos_params == prior_best, (
                f"Window {i} OOS params should equal window {i - 1} IS best_params"
            )

    @pytest.mark.test_id("4.3-ATDD-003")
    @pytest.mark.p0
    def test_window0_oos_uses_baseline(self):
        ohlcv = _synthetic_ohlcv(n=200)
        result = walk_forward(ohlcv, _frozen_cfg())
        w0 = result.windows[0]
        assert w0.frozen_oos_params == {"fast": 5, "slow": 30}
        assert w0.frozen_params_source_window is None

    @pytest.mark.test_id("4.3-ATDD-004")
    @pytest.mark.p0
    def test_nonfrozen_identical_to_story42(self):

        ohlcv = _synthetic_ohlcv(n=200)
        cfg_nonfrozen = WalkForwardConfig(
            mode="rolling",
            is_bars=60,
            oos_bars=20,
            seed=42,
            strategy_type="sma",
            strategy_params={"fast": 5, "slow": 30},
            optimization=OptimizationConfig(
                param_ranges={"fast": [5, 10, 15], "slow": [30, 50]},
                max_trials=50,
                constraints=[monotonic_increasing("fast", "slow")],
            ),
            frozen_params_mode=False,
        )
        r1 = walk_forward(ohlcv, cfg_nonfrozen)
        r2 = walk_forward(ohlcv, cfg_nonfrozen)
        assert len(r1.windows) == len(r2.windows)
        for w1, w2 in zip(r1.windows, r2.windows, strict=True):
            assert w1.is_sharpe == w2.is_sharpe or (
                math.isnan(w1.is_sharpe) and math.isnan(w2.is_sharpe)
            )
            assert w1.oos_sharpe == w2.oos_sharpe or (
                math.isnan(w1.oos_sharpe) and math.isnan(w2.oos_sharpe)
            )
            assert w1.frozen_oos_params is None
            assert w1.frozen_params_source_window is None

    @pytest.mark.test_id("4.3-ATDD-005")
    @pytest.mark.p1
    def test_async_runner_raises_with_frozen(self):
        import asyncio

        from trade_advisor.backtest.walkforward.async_runner import async_run_walkforward

        ohlcv = _synthetic_ohlcv(n=200)
        config = _frozen_cfg()

        with pytest.raises(WalkForwardError, match="frozen_params_mode requires sequential"):
            asyncio.run(async_run_walkforward(ohlcv, config))

    @pytest.mark.test_id("4.3-ATDD-006")
    @pytest.mark.p1
    def test_all_windows_frozen_fields_populated(self):
        ohlcv = _synthetic_ohlcv(n=300)
        result = walk_forward(ohlcv, _frozen_cfg())
        assert len(result.windows) >= 2
        for i, w in enumerate(result.windows):
            assert w.frozen_oos_params is not None
            if i == 0:
                assert w.frozen_params_source_window is None
            else:
                assert isinstance(w.frozen_params_source_window, int)
            assert w.frozen_fallback is False

    @pytest.mark.test_id("4.3-ATDD-007")
    @pytest.mark.p1
    def test_fallback_window_has_degraded_fields(self):
        ohlcv = _synthetic_ohlcv(n=200)
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
            assert w.status in {"DEGRADED", "INCONCLUSIVE"}
            assert math.isnan(w.is_sharpe)
            assert len(w.is_equity) == 0
