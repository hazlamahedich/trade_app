"""Story 4.4 — OOS Equity Curve Stitching & Efficiency Ratio: comprehensive tests."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from tests.helpers import _synthetic_ohlcv
from trade_advisor.backtest.walkforward.engine import (
    DataBoundary,
    WalkForwardConfig,
    WalkForwardResult,
    WindowResult,
)
from trade_advisor.backtest.walkforward.stitch import (
    StitchedOOSResult,
    WFEThresholds,
    build_stitched_result,
    compute_expected_value,
    compute_wfe,
    compute_wfe_from_result,
    stitch_oos_equity,
    wfe_status,
)


def _make_window(
    idx: int,
    is_return: float = 0.10,
    oos_return: float = 0.05,
    is_bars: int = 20,
    oos_bars: int = 10,
    status: str = "OK",
    is_sharpe: float = 1.0,
    oos_sharpe: float = 0.8,
) -> WindowResult:
    rng = np.random.default_rng(42 + idx)
    is_equity = pd.Series(100_000 + np.cumsum(rng.standard_normal(is_bars) * 500))
    oos_equity = (
        pd.Series(100_000 + np.cumsum(rng.standard_normal(oos_bars) * 300))
        if status == "OK"
        else pd.Series(dtype="float64")
    )
    start = idx * (is_bars + 1 + oos_bars)
    return WindowResult(
        boundary=DataBoundary(
            is_start=start,
            is_end=start + is_bars,
            oos_start=start + is_bars + 1,
            oos_end=start + is_bars + 1 + oos_bars,
        ),
        is_segment=pd.DataFrame({"close": range(is_bars)}),
        oos_segment=pd.DataFrame({"close": range(oos_bars)}),
        is_equity=is_equity,
        oos_equity=oos_equity,
        is_sharpe=is_sharpe,
        oos_sharpe=oos_sharpe,
        is_return=is_return,
        oos_return=oos_return,
        status=status,
    )


def _make_wf_result(
    n_windows: int = 3,
    is_returns: list[float] | None = None,
    oos_returns: list[float] | None = None,
    statuses: list[str] | None = None,
    frozen: bool = False,
) -> WalkForwardResult:
    windows = []
    for i in range(n_windows):
        ir = is_returns[i] if is_returns else 0.10
        oor = oos_returns[i] if oos_returns else 0.05
        st = statuses[i] if statuses else "OK"
        windows.append(_make_window(i, is_return=ir, oos_return=oor, status=st))
    return WalkForwardResult(
        n_windows=n_windows,
        windows=windows,
        config=WalkForwardConfig(
            mode="rolling",
            is_bars=20,
            oos_bars=10,
            seed=42,
            frozen_params_mode=frozen,
        ),
    )


# ---------------------------------------------------------------------------
# P0 Edge Cases: division-by-zero, NaN, negative
# ---------------------------------------------------------------------------


class TestDivisionByZeroAndNegative:
    @pytest.mark.test_id("4.4-NEW-001")
    @pytest.mark.p0
    def test_compute_wfe_zero_is_return(self):
        assert compute_wfe(0.15, 0.0) == 0.0

    @pytest.mark.test_id("4.4-NEW-002")
    @pytest.mark.p0
    def test_compute_wfe_negative_oos_positive_is(self):
        result = compute_wfe(-0.05, 0.20)
        assert result < 0.0

    @pytest.mark.test_id("4.4-NEW-003")
    @pytest.mark.p0
    def test_compute_wfe_both_negative(self):
        result = compute_wfe(-0.05, -0.10)
        assert result > 0.0

    @pytest.mark.test_id("4.4-NEW-004")
    @pytest.mark.p0
    def test_stitch_handles_nan_in_series(self):
        # Use values close to 100k for realistic returns
        s1 = pd.Series([100_000.0, 101_000.0, float("nan")], index=[1, 2, 3])
        s2 = pd.Series([100_000.0, 102_000.0], index=[4, 5])
        stitched = stitch_oos_equity([s1, s2], initial_cash=100_000.0)
        assert len(stitched) == 4
        assert stitched.index.is_monotonic_increasing
        assert not stitched.isna().any()
        # Initial cash * (1 + 0.01) * (1 + 0.0) * (1 + 0.02) = 100k * 1.01 * 1.02 = 103,020
        assert stitched.iloc[-1] == pytest.approx(103_020.0)

    @pytest.mark.test_id("4.4-NEW-005")
    @pytest.mark.p0
    def test_all_inconclusive_windows(self):
        result = _make_wf_result(
            n_windows=3,
            is_returns=[0.1, 0.1, 0.1],
            oos_returns=[0.05, 0.05, 0.05],
            statuses=["INCONCLUSIVE", "INCONCLUSIVE", "INCONCLUSIVE"],
        )
        wfe, status, per_fold, _, _ = compute_wfe_from_result(result)
        assert wfe == 0.0
        assert status == "unreliable"
        assert per_fold == []

    @pytest.mark.test_id("4.4-NEW-006")
    @pytest.mark.p0
    def test_three_window_stitch_length(self):
        # segments all start at initial_cash
        segments = [pd.Series([100_000.0, 101_000.0], index=[i*10, i*10+1]) for i in range(3)]
        stitched = stitch_oos_equity(segments, initial_cash=100_000.0)
        assert len(stitched) == 6


# ---------------------------------------------------------------------------
# WFE Computation
# ---------------------------------------------------------------------------


class TestWFEComputation:
    @pytest.mark.test_id("4.4-NEW-007")
    @pytest.mark.p0
    def test_wfe_basic_ratio(self):
        assert compute_wfe(0.10, 0.20) == pytest.approx(0.5)

    @pytest.mark.test_id("4.4-NEW-008")
    @pytest.mark.p0
    def test_wfe_zero_oos_return(self):
        assert compute_wfe(0.0, 0.20) == pytest.approx(0.0)

    @pytest.mark.test_id("4.4-NEW-009")
    @pytest.mark.p1
    def test_compound_not_simple_sum(self):
        result = _make_wf_result(
            n_windows=2,
            is_returns=[0.10, 0.10],
            oos_returns=[0.05, 0.05],
        )
        wfe, _, _, _, _ = compute_wfe_from_result(result)
        is_compound = (1.10 * 1.10) - 1.0
        oos_compound = (1.05 * 1.05) - 1.0
        expected = oos_compound / is_compound
        assert wfe == pytest.approx(expected)

    @pytest.mark.test_id("4.4-NEW-010")
    @pytest.mark.p1
    def test_per_fold_wfe_list(self):
        result = _make_wf_result(
            n_windows=3,
            is_returns=[0.20, 0.10, 0.30],
            oos_returns=[0.10, 0.05, 0.15],
        )
        _, _, per_fold, _, _ = compute_wfe_from_result(result)
        assert len(per_fold) == 3
        assert per_fold[0] == pytest.approx(0.10 / 0.20)
        assert per_fold[1] == pytest.approx(0.05 / 0.10)
        assert per_fold[2] == pytest.approx(0.15 / 0.30)


# ---------------------------------------------------------------------------
# WFE Status Boundary
# ---------------------------------------------------------------------------


class TestWFEStatusBoundary:
    @pytest.mark.test_id("4.4-NEW-011")
    @pytest.mark.p1
    def test_boundary_healthy(self):
        assert wfe_status(0.7, total_is_return=0.1, total_oos_return=0.07) == "healthy"

    @pytest.mark.test_id("4.4-NEW-012")
    @pytest.mark.p1
    def test_boundary_caution(self):
        assert wfe_status(0.5, total_is_return=0.1, total_oos_return=0.05) == "caution"

    @pytest.mark.test_id("4.4-NEW-013")
    @pytest.mark.p1
    def test_just_below_caution(self):
        assert wfe_status(0.49, total_is_return=0.1, total_oos_return=0.049) == "unreliable"

    @pytest.mark.test_id("4.4-NEW-014")
    @pytest.mark.p1
    def test_negative_wfe_unreliable(self):
        assert wfe_status(-0.1, total_is_return=0.1, total_oos_return=-0.01) == "unreliable"

    @pytest.mark.test_id("4.4-NEW-015")
    @pytest.mark.p1
    def test_custom_thresholds(self):
        assert wfe_status(0.6, thresholds=WFEThresholds(healthy_min=0.8), total_is_return=0.1, total_oos_return=0.06) == "caution"

    def test_double_negative_unreliable(self):
        # Both lost money, WFE is positive 0.8, but result is unreliable
        assert wfe_status(0.8, total_is_return=-0.1, total_oos_return=-0.08) == "unreliable"


# ---------------------------------------------------------------------------
# Stitching Correctness
# ---------------------------------------------------------------------------


class TestStitchingCorrectness:
    @pytest.mark.test_id("4.4-NEW-016")
    @pytest.mark.p1
    def test_single_window_stitch(self):
        s = pd.Series([100_100.0, 100_200.0, 100_300.0], index=[10, 20, 30])
        result = stitch_oos_equity([s], initial_cash=100_000.0)
        pd.testing.assert_series_equal(result, s.rename("equity"))

    @pytest.mark.test_id("4.4-NEW-017")
    @pytest.mark.p1
    def test_gaps_preserved(self):
        s1 = pd.Series([101_000.0, 102_000.0], index=[1, 2])
        s2 = pd.Series([101_000.0, 102_000.0], index=[5, 6])
        stitched = stitch_oos_equity([s1, s2], initial_cash=100_000.0)
        assert list(stitched.index) == [1, 2, 5, 6]

    @pytest.mark.test_id("4.4-NEW-018")
    @pytest.mark.p1
    def test_empty_segments_contribute_zero(self):
        s1 = pd.Series([101_000.0, 102_000.0], index=[1, 2])
        s_empty = pd.Series(dtype="float64")
        s2 = pd.Series([101_000.0, 102_000.0], index=[5, 6])
        stitched = stitch_oos_equity([s1, s_empty, s2], initial_cash=100_000.0)
        assert len(stitched) == 4

    @pytest.mark.test_id("4.4-NEW-019")
    @pytest.mark.p1
    def test_sorted_no_duplicates(self):
        segments = [
            pd.Series([100_300.0], index=[30]),
            pd.Series([100_100.0], index=[10]),
            pd.Series([100_200.0], index=[20]),
        ]
        stitched = stitch_oos_equity(segments, initial_cash=100_000.0)
        assert stitched.index.is_monotonic_increasing
        assert not stitched.index.has_duplicates


# ---------------------------------------------------------------------------
# Expected Value
# ---------------------------------------------------------------------------


class TestExpectedValue:
    @pytest.mark.test_id("4.4-NEW-020")
    @pytest.mark.p1
    def test_known_returns_ev(self):
        returns = [0.02, -0.01, 0.03, 0.0, -0.02] # Include 0.0
        ev = compute_expected_value(returns)
        assert ev == pytest.approx(np.mean(returns), abs=1e-10)

    @pytest.mark.test_id("4.4-NEW-021")
    @pytest.mark.p1
    def test_series_input(self):
        s = pd.Series([0.01, -0.02, 0.03])
        ev = compute_expected_value(s)
        assert ev == pytest.approx(s.mean(), abs=1e-10)

    @pytest.mark.test_id("4.4-NEW-022")
    @pytest.mark.p2
    def test_all_zero_returns(self):
        assert compute_expected_value([0.0, 0.0, 0.0]) == 0.0


# ---------------------------------------------------------------------------
# build_stitched_result Integration
# ---------------------------------------------------------------------------


class TestBuildStitchedResult:
    @pytest.mark.test_id("4.4-NEW-023")
    @pytest.mark.p0
    def test_full_integration_all_fields_populated(self):
        ohlcv = _synthetic_ohlcv(n=200)
        result = _make_wf_result(n_windows=3)
        stitched = build_stitched_result(result, ohlcv)
        assert isinstance(stitched, StitchedOOSResult)
        assert isinstance(stitched.stitched_equity, pd.Series)
        assert len(stitched.stitched_equity) > 0
        assert isinstance(stitched.total_oos_return, float)
        assert isinstance(stitched.total_is_return, float)
        assert isinstance(stitched.wfe, float)
        assert stitched.wfe_status in ("healthy", "caution", "unreliable")
        assert isinstance(stitched.wfe_per_fold, list)
        assert len(stitched.wfe_per_fold) == 3
        assert isinstance(stitched.expected_value_per_trade, float)
        assert isinstance(stitched.n_oos_trades, int)
        assert isinstance(stitched.window_0_oos_is_baseline, bool)

    @pytest.mark.test_id("4.4-NEW-024")
    @pytest.mark.p0
    def test_window_0_baseline_flag_frozen(self):
        from trade_advisor.backtest.walkforward.optimize import OptimizationConfig

        ohlcv = _synthetic_ohlcv(n=200)
        config = WalkForwardConfig(
            mode="rolling",
            is_bars=20,
            oos_bars=10,
            seed=42,
            frozen_params_mode=True,
            optimization=OptimizationConfig(param_ranges={"fast": [5, 10], "slow": [20, 30]}),
        )
        windows = [_make_window(i) for i in range(3)]
        result = WalkForwardResult(
            n_windows=3,
            windows=windows,
            config=config,
        )
        stitched = build_stitched_result(result, ohlcv)
        assert stitched.window_0_oos_is_baseline is True

    @pytest.mark.test_id("4.4-NEW-025")
    @pytest.mark.p1
    def test_baseline_starts_at_same_value(self):
        ohlcv = _synthetic_ohlcv(n=200)
        result = _make_wf_result(n_windows=3)
        stitched = build_stitched_result(result, ohlcv)
        if len(stitched.baseline_equity) > 0:
            # Scale should match stitched_equity first value
            assert stitched.baseline_equity.iloc[0] == pytest.approx(stitched.stitched_equity.iloc[0])

    @pytest.mark.test_id("4.4-NEW-026")
    @pytest.mark.p1
    def test_reproducibility(self):
        ohlcv = _synthetic_ohlcv(n=200)
        result = _make_wf_result(n_windows=3)
        r1 = build_stitched_result(result, ohlcv)
        r2 = build_stitched_result(result, ohlcv)
        assert r1.wfe == r2.wfe
        assert r1.wfe_status == r2.wfe_status
        assert r1.expected_value_per_trade == r2.expected_value_per_trade
        assert len(r1.wfe_per_fold) == len(r2.wfe_per_fold)
        for a, b in zip(r1.wfe_per_fold, r2.wfe_per_fold, strict=True):
            assert a == b


    @pytest.mark.test_id("4.4-NEW-027")
    @pytest.mark.p1
    def test_per_fold_length_matches_ok_windows(self):
        ohlcv = _synthetic_ohlcv(n=200)
        result = _make_wf_result(
            n_windows=4,
            statuses=["OK", "INCONCLUSIVE", "OK", "OK"],
            oos_returns=[0.05, 0.0, 0.08, 0.06],
            is_returns=[0.10, 0.0, 0.15, 0.12],
        )
        stitched = build_stitched_result(result, ohlcv)
        assert len(stitched.wfe_per_fold) == 3


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    @pytest.mark.test_id("4.4-NEW-028")
    @pytest.mark.p1
    def test_single_window_stitch_is_just_that_window(self):
        result = _make_wf_result(n_windows=1)
        valid = [w for w in result.windows if w.status == "OK"]
        stitched = stitch_oos_equity([w.oos_equity for w in valid], initial_cash=100_000.0)
        pd.testing.assert_series_equal(
            stitched.reset_index(drop=True),
            valid[0].oos_equity.reset_index(drop=True).rename("equity"),
        )

    @pytest.mark.test_id("4.4-NEW-029")
    @pytest.mark.p2
    def test_tiny_returns_no_overflow(self):
        tiny = 1e-12
        wfe = compute_wfe(tiny, tiny)
        assert math.isfinite(wfe)
        assert wfe == pytest.approx(1.0)

    @pytest.mark.test_id("4.4-NEW-030")
    @pytest.mark.p2
    def test_anchored_mode_stitch(self):
        ohlcv = _synthetic_ohlcv(n=200)
        windows = [_make_window(i) for i in range(3)]
        config = WalkForwardConfig(
            mode="anchored",
            is_bars=20,
            oos_bars=10,
            seed=42,
        )
        result = WalkForwardResult(
            n_windows=3,
            windows=windows,
            config=config,
        )
        stitched = build_stitched_result(result, ohlcv)
        assert len(stitched.stitched_equity) > 0


# ---------------------------------------------------------------------------
# ATDD-compatible tests (direct compute_wfe / wfe_status / EV tests)
# ---------------------------------------------------------------------------


class TestATDDCompat:
    def test_atdd_002_wfe_basic(self):
        total_is = 0.20
        total_oos = 0.10
        assert compute_wfe(total_oos, total_is) == pytest.approx(0.5)

    def test_atdd_003_healthy(self):
        assert wfe_status(0.75, total_is_return=0.20, total_oos_return=0.15) == "healthy"

    def test_atdd_004_caution(self):
        assert wfe_status(0.6, total_is_return=0.20, total_oos_return=0.12) == "caution"

    def test_atdd_005_unreliable(self):
        assert wfe_status(0.3, total_is_return=0.20, total_oos_return=0.06) == "unreliable"

    def test_atdd_007_ev_mean(self):
        trades = [0.02, -0.01, 0.03, -0.005, 0.015, -0.02, 0.01]
        assert compute_expected_value(trades) == pytest.approx(np.mean(trades), abs=1e-10)

    def test_atdd_008_negative_ev(self):
        assert compute_expected_value([-0.05, -0.03, -0.02, -0.01]) < 0

    def test_atdd_009_empty_ev(self):
        assert compute_expected_value([]) == 0.0
