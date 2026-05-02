"""Story 4.1a: Walk-Forward Engine — Sync Core (Rolling & Anchored Modes).

Tests cover all acceptance criteria from the story specification:
- AC-1 through AC-13
- 9 adopted ATDD tests + 13 new tests = 22 total
"""

from __future__ import annotations

import math

import pandas as pd
import pytest
from pydantic import ValidationError

from tests.helpers import _synthetic_ohlcv
from trade_advisor.backtest.walkforward.engine import (
    DataBoundary,
    WalkForwardConfig,
    WalkForwardError,
    _generate_anchored_boundaries,
    _generate_rolling_boundaries,
    walk_forward,
)


@pytest.fixture
def ohlcv_500() -> pd.DataFrame:
    return _synthetic_ohlcv(n=500, seed=42)


# ---------------------------------------------------------------------------
# AC-1: WalkForwardConfig is a typed pydantic model
# ---------------------------------------------------------------------------


class TestWalkForwardConfig:
    @pytest.mark.test_id("4.1a-ATDD-003")
    def test_config_defaults(self):
        cfg = WalkForwardConfig(mode="rolling", is_bars=60, oos_bars=20)
        assert cfg.gap_bars == 1
        assert cfg.seed == 42
        assert cfg.strategy_type == "sma"
        assert cfg.strategy_params == {}
        assert isinstance(cfg.backtest, object)

    @pytest.mark.test_id("4.1a-ATDD-003b")
    def test_config_rejects_invalid_mode(self):
        with pytest.raises(ValidationError):
            WalkForwardConfig(mode="expanding", is_bars=60, oos_bars=20)

    @pytest.mark.test_id("4.1a-NEW-012")
    def test_config_rejects_zero_is_bars(self):
        with pytest.raises(ValidationError):
            WalkForwardConfig(mode="rolling", is_bars=0, oos_bars=20)

    @pytest.mark.test_id("4.1a-NEW-012b")
    def test_config_rejects_zero_oos_bars(self):
        with pytest.raises(ValidationError):
            WalkForwardConfig(mode="rolling", is_bars=60, oos_bars=0)


# ---------------------------------------------------------------------------
# AC-2: DataBoundary is a frozen dataclass with invariant validation
# ---------------------------------------------------------------------------


class TestDataBoundary:
    @pytest.mark.test_id("4.1a-NEW-008")
    def test_oos_start_must_be_gte_is_end(self):
        with pytest.raises(WalkForwardError):
            DataBoundary(is_start=0, is_end=60, oos_start=59, oos_end=80)

    @pytest.mark.test_id("4.1a-NEW-008b")
    def test_valid_boundary(self):
        b = DataBoundary(is_start=0, is_end=60, oos_start=61, oos_end=81)
        assert b.is_start == 0
        assert b.is_end == 60
        assert b.oos_start == 61
        assert b.oos_end == 81

    @pytest.mark.test_id("4.1a-NEW-009")
    def test_is_start_must_be_non_negative(self):
        with pytest.raises(WalkForwardError):
            DataBoundary(is_start=-1, is_end=60, oos_start=61, oos_end=81)

    @pytest.mark.test_id("4.1a-NEW-010")
    def test_frozen_cannot_mutate(self):
        b = DataBoundary(is_start=0, is_end=60, oos_start=61, oos_end=81)
        with pytest.raises(AttributeError):
            b.is_start = 1

    def test_is_end_must_be_gt_is_start(self):
        with pytest.raises(WalkForwardError):
            DataBoundary(is_start=60, is_end=60, oos_start=61, oos_end=81)

    def test_oos_end_must_be_gt_oos_start(self):
        with pytest.raises(WalkForwardError):
            DataBoundary(is_start=0, is_end=60, oos_start=61, oos_end=61)


# ---------------------------------------------------------------------------
# AC-3: Rolling mode produces fixed-width IS windows with gap
# ---------------------------------------------------------------------------


class TestRollingMode:
    @pytest.mark.test_id("4.1a-ATDD-001")
    def test_rolling_produces_windows(self, ohlcv_500):
        cfg = WalkForwardConfig(mode="rolling", is_bars=60, oos_bars=20)
        result = walk_forward(ohlcv_500, cfg)
        assert result.n_windows > 0

    @pytest.mark.test_id("4.1a-ATDD-001b")
    def test_rolling_fixed_width_is(self, ohlcv_500):
        cfg = WalkForwardConfig(mode="rolling", is_bars=60, oos_bars=20)
        result = walk_forward(ohlcv_500, cfg)
        for w in result.windows:
            assert w.boundary.is_end - w.boundary.is_start == 60

    @pytest.mark.test_id("4.1a-ATDD-001c")
    def test_rolling_fixed_width_oos(self, ohlcv_500):
        cfg = WalkForwardConfig(mode="rolling", is_bars=60, oos_bars=20)
        result = walk_forward(ohlcv_500, cfg)
        for w in result.windows:
            assert w.boundary.oos_end - w.boundary.oos_start == 20

    @pytest.mark.test_id("4.1a-NEW-003")
    def test_rolling_gap_enforced(self, ohlcv_500):
        cfg = WalkForwardConfig(mode="rolling", is_bars=60, oos_bars=20)
        result = walk_forward(ohlcv_500, cfg)
        for w in result.windows:
            assert w.boundary.oos_start == w.boundary.is_end + cfg.gap_bars

    @pytest.mark.test_id("4.1a-ATDD-005")
    def test_rolling_all_is_same_length(self, ohlcv_500):
        cfg = WalkForwardConfig(mode="rolling", is_bars=60, oos_bars=20)
        result = walk_forward(ohlcv_500, cfg)
        is_lengths = [w.boundary.is_end - w.boundary.is_start for w in result.windows]
        assert len(set(is_lengths)) == 1


# ---------------------------------------------------------------------------
# AC-4: Anchored mode produces expanding IS windows from bar 0
# ---------------------------------------------------------------------------


class TestAnchoredMode:
    @pytest.mark.test_id("4.1a-ATDD-002")
    def test_anchored_expanding_is(self, ohlcv_500):
        cfg = WalkForwardConfig(mode="anchored", is_bars=60, oos_bars=20)
        result = walk_forward(ohlcv_500, cfg)
        assert result.n_windows > 0
        for w in result.windows:
            assert w.boundary.is_start == 0

    @pytest.mark.test_id("4.1a-ATDD-002b")
    def test_anchored_monotonically_expanding(self, ohlcv_500):
        cfg = WalkForwardConfig(mode="anchored", is_bars=60, oos_bars=20)
        result = walk_forward(ohlcv_500, cfg)
        is_lengths = [w.boundary.is_end - w.boundary.is_start for w in result.windows]
        for i in range(1, len(is_lengths)):
            assert is_lengths[i] >= is_lengths[i - 1]


# ---------------------------------------------------------------------------
# AC-5: No data leakage — IS data never bleeds into OOS
# ---------------------------------------------------------------------------


class TestDataLeakage:
    @pytest.mark.test_id("4.1a-NEW-001")
    def test_oos_slice_excludes_is_data(self, ohlcv_500):
        cfg = WalkForwardConfig(mode="rolling", is_bars=60, oos_bars=20)
        result = walk_forward(ohlcv_500, cfg)
        for w in result.windows:
            is_timestamps = set(w.is_segment["timestamp"].values)
            oos_timestamps = set(w.oos_segment["timestamp"].values)
            assert is_timestamps.isdisjoint(oos_timestamps), (
                "IS and OOS segments share timestamps — data leakage!"
            )

    @pytest.mark.test_id("4.1a-NEW-002")
    def test_oos_slice_only_contains_oos_bars(self, ohlcv_500):
        cfg = WalkForwardConfig(mode="rolling", is_bars=60, oos_bars=20)
        result = walk_forward(ohlcv_500, cfg)
        for w in result.windows:
            assert len(w.oos_segment) == cfg.oos_bars


# ---------------------------------------------------------------------------
# AC-6: No overlapping OOS segments
# ---------------------------------------------------------------------------


class TestNoOverlappingOOS:
    @pytest.mark.test_id("4.1a-ATDD-006")
    def test_no_overlapping_oos(self, ohlcv_500):
        cfg = WalkForwardConfig(mode="rolling", is_bars=60, oos_bars=20)
        result = walk_forward(ohlcv_500, cfg)
        for i in range(1, len(result.windows)):
            assert result.windows[i].boundary.oos_start > result.windows[i - 1].boundary.oos_end


# ---------------------------------------------------------------------------
# AC-7: Deterministic with same seed
# ---------------------------------------------------------------------------


class TestDeterminism:
    @pytest.mark.test_id("4.1a-ATDD-004")
    def test_deterministic_same_seed(self, ohlcv_500):
        cfg = WalkForwardConfig(mode="rolling", is_bars=60, oos_bars=20, seed=42)
        result_a = walk_forward(ohlcv_500, cfg)
        result_b = walk_forward(ohlcv_500, cfg)
        assert result_a.n_windows == result_b.n_windows
        for wa, wb in zip(result_a.windows, result_b.windows, strict=True):
            assert wa.boundary == wb.boundary
            pd.testing.assert_series_equal(wa.oos_equity, wb.oos_equity)
            if math.isnan(wa.is_sharpe):
                assert math.isnan(wb.is_sharpe)
            else:
                assert wa.is_sharpe == wb.is_sharpe
            if math.isnan(wa.oos_sharpe):
                assert math.isnan(wb.oos_sharpe)
            else:
                assert wa.oos_sharpe == wb.oos_sharpe


# ---------------------------------------------------------------------------
# AC-8: Window metrics are finite and sane
# ---------------------------------------------------------------------------


class TestMetrics:
    @pytest.mark.test_id("4.1a-ATDD-007")
    def test_metrics_finite(self, ohlcv_500):
        cfg = WalkForwardConfig(mode="rolling", is_bars=60, oos_bars=20)
        result = walk_forward(ohlcv_500, cfg)
        for w in result.windows:
            if w.status == "OK":
                assert math.isfinite(w.is_sharpe), f"is_sharpe not finite: {w.is_sharpe}"
                assert math.isfinite(w.oos_sharpe), f"oos_sharpe not finite: {w.oos_sharpe}"
                assert math.isfinite(w.is_return), f"is_return not finite: {w.is_return}"
                assert math.isfinite(w.oos_return), f"oos_return not finite: {w.oos_return}"

    @pytest.mark.test_id("4.1a-ATDD-007b")
    def test_metrics_have_has_all_attributes(self, ohlcv_500):
        cfg = WalkForwardConfig(mode="rolling", is_bars=60, oos_bars=20)
        result = walk_forward(ohlcv_500, cfg)
        for w in result.windows:
            assert hasattr(w, "is_sharpe")
            assert hasattr(w, "oos_sharpe")
            assert hasattr(w, "is_return")
            assert hasattr(w, "oos_return")


# ---------------------------------------------------------------------------
# AC-9: Empty OOS window produces INCONCLUSIVE marker
# ---------------------------------------------------------------------------


class TestInconclusiveWindow:
    @pytest.mark.test_id("4.1a-NEW-011")
    def test_empty_oos_inconclusive_with_flat_strategy(self):
        from unittest.mock import MagicMock, patch

        ohlcv = _synthetic_ohlcv(n=500, seed=42)
        cfg = WalkForwardConfig(mode="rolling", is_bars=60, oos_bars=20)
        flat_strategy = MagicMock()
        flat_strategy.warmup_period = 0
        flat_strategy.generate_signals.side_effect = lambda sl: pd.Series(
            0.0, index=sl.index, dtype="float64", name="signal"
        )
        with patch(
            "trade_advisor.backtest.walkforward.engine._resolve_strategy",
            return_value=flat_strategy,
        ):
            result = walk_forward(ohlcv, cfg)
        assert result.n_windows > 0
        for w in result.windows:
            assert w.status == "INCONCLUSIVE"
            assert math.isnan(w.oos_sharpe)
            assert math.isnan(w.oos_return)

    @pytest.mark.test_id("4.1a-NEW-011b")
    def test_normal_strategy_produces_ok_windows(self):
        ohlcv = _synthetic_ohlcv(n=500, seed=42)
        cfg = WalkForwardConfig(
            mode="rolling",
            is_bars=60,
            oos_bars=20,
            strategy_params={"fast": 5, "slow": 10},
        )
        result = walk_forward(ohlcv, cfg)
        assert result.n_windows > 0
        has_ok = any(w.status == "OK" for w in result.windows)
        assert has_ok


# ---------------------------------------------------------------------------
# AC-10: Insufficient data raises WalkForwardError
# ---------------------------------------------------------------------------


class TestInsufficientData:
    @pytest.mark.test_id("4.1a-ATDD-008")
    def test_insufficient_data_raises_error(self):
        ohlcv = _synthetic_ohlcv(n=120, seed=42)
        cfg = WalkForwardConfig(mode="rolling", is_bars=200, oos_bars=50)
        with pytest.raises(WalkForwardError, match=r"Need >= \d+ bars, got \d+"):
            walk_forward(ohlcv, cfg)

    @pytest.mark.test_id("4.1a-NEW-005")
    def test_one_bar_short_raises_error(self):
        is_bars, oos_bars, gap_bars = 60, 20, 1
        total = is_bars + gap_bars + oos_bars
        ohlcv = _synthetic_ohlcv(n=total - 1, seed=42)
        cfg = WalkForwardConfig(mode="rolling", is_bars=is_bars, oos_bars=oos_bars)
        with pytest.raises(WalkForwardError):
            walk_forward(ohlcv, cfg)


# ---------------------------------------------------------------------------
# AC-11: Invalid mode rejected at construction
# ---------------------------------------------------------------------------


class TestInvalidMode:
    @pytest.mark.test_id("4.1a-ATDD-009")
    def test_invalid_mode_rejected(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            WalkForwardConfig(mode="invalid_mode", is_bars=60, oos_bars=20)


# ---------------------------------------------------------------------------
# AC-12: Strategy resolution from registry
# ---------------------------------------------------------------------------


class TestStrategyResolution:
    def test_sma_strategy_resolved(self, ohlcv_500):
        cfg = WalkForwardConfig(
            mode="rolling",
            is_bars=60,
            oos_bars=20,
            strategy_type="sma",
            strategy_params={"fast": 20, "slow": 50},
        )
        result = walk_forward(ohlcv_500, cfg)
        assert result.n_windows > 0

    def test_unknown_strategy_raises_error(self, ohlcv_500):
        cfg = WalkForwardConfig(
            mode="rolling",
            is_bars=60,
            oos_bars=20,
            strategy_type="nonexistent",
        )
        with pytest.raises(WalkForwardError, match="Unknown strategy_type"):
            walk_forward(ohlcv_500, cfg)


# ---------------------------------------------------------------------------
# AC-13: Remainder bars after last complete window are discarded
# ---------------------------------------------------------------------------


class TestDiscardedBars:
    @pytest.mark.test_id("4.1a-ATDD-013")
    def test_discarded_bars(self, ohlcv_500):
        cfg = WalkForwardConfig(mode="rolling", is_bars=60, oos_bars=20)
        result = walk_forward(ohlcv_500, cfg)
        stride = cfg.is_bars + cfg.gap_bars + cfg.oos_bars
        expected_windows = 500 // stride
        expected_discarded = 500 % stride
        assert result.n_windows == expected_windows
        assert result.discarded_bars == expected_discarded


# ---------------------------------------------------------------------------
# Boundary condition tests
# ---------------------------------------------------------------------------


class TestBoundaryConditions:
    @pytest.mark.test_id("4.1a-NEW-004")
    def test_exact_fit_one_window(self):
        is_bars, oos_bars, gap_bars = 60, 20, 1
        total = is_bars + gap_bars + oos_bars
        ohlcv = _synthetic_ohlcv(n=total, seed=42)
        cfg = WalkForwardConfig(mode="rolling", is_bars=is_bars, oos_bars=oos_bars)
        result = walk_forward(ohlcv, cfg)
        assert result.n_windows == 1
        assert result.discarded_bars == 0

    @pytest.mark.test_id("4.1a-NEW-006")
    def test_minimum_oos_bars(self):
        is_bars, oos_bars, gap_bars = 60, 1, 1
        total = is_bars + gap_bars + oos_bars
        ohlcv = _synthetic_ohlcv(n=total, seed=42)
        cfg = WalkForwardConfig(mode="rolling", is_bars=is_bars, oos_bars=oos_bars)
        result = walk_forward(ohlcv, cfg)
        assert result.n_windows == 1

    @pytest.mark.test_id("4.1a-NEW-007")
    def test_very_large_is_bars(self):
        ohlcv = _synthetic_ohlcv(n=500, seed=42)
        cfg = WalkForwardConfig(mode="rolling", is_bars=499, oos_bars=1)
        with pytest.raises(WalkForwardError):
            walk_forward(ohlcv, cfg)

    @pytest.mark.test_id("4.1a-NEW-013")
    def test_empty_dataframe_raises_error(self):
        ohlcv = pd.DataFrame()
        cfg = WalkForwardConfig(mode="rolling", is_bars=60, oos_bars=20)
        with pytest.raises(WalkForwardError):
            walk_forward(ohlcv, cfg)


# ---------------------------------------------------------------------------
# Boundary generation unit tests
# ---------------------------------------------------------------------------


class TestBoundaryGeneration:
    def test_rolling_boundaries_correct_count(self):
        boundaries = _generate_rolling_boundaries(500, 60, 20, 1)
        stride = 60 + 1 + 20
        assert len(boundaries) == 500 // stride

    def test_anchored_boundaries_is_start_always_zero(self):
        boundaries = _generate_anchored_boundaries(500, 60, 20, 1)
        for b in boundaries:
            assert b.is_start == 0

    def test_anchored_boundaries_expanding(self):
        boundaries = _generate_anchored_boundaries(500, 60, 20, 1)
        is_ends = [b.is_end for b in boundaries]
        for i in range(1, len(is_ends)):
            assert is_ends[i] > is_ends[i - 1]
