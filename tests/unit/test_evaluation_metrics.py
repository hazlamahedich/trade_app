from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from trade_advisor.evaluation.metrics import Metrics, compute_metrics, drawdown_series, max_drawdown


def _make_returns(values):
    return pd.Series(values, dtype="float64")


class TestComputeMetricsEmpty:
    @pytest.mark.test_id("1.5-UNIT-001")
    @pytest.mark.p1
    def test_empty_series_returns_zeros(self):
        m = compute_metrics(pd.Series([], dtype="float64"))
        assert m.total_return == 0.0
        assert m.cagr == 0.0
        assert m.sharpe == 0.0
        assert m.n_bars == 0

    @pytest.mark.test_id("1.5-UNIT-002")
    @pytest.mark.p2
    def test_all_nan_returns_zeros(self):
        m = compute_metrics(pd.Series([np.nan, np.nan]))
        assert m.total_return == 0.0
        assert m.n_bars == 0


class TestCAGR:
    @pytest.mark.test_id("1.5-UNIT-003")
    @pytest.mark.p1
    def test_negative_final_equity_returns_negative_one(self):
        r = _make_returns([-0.9, -0.5])
        m = compute_metrics(r)
        assert m.cagr == -1.0

    @pytest.mark.test_id("1.5-UNIT-004")
    @pytest.mark.p1
    def test_single_bar(self):
        r = _make_returns([0.05])
        m = compute_metrics(r)
        assert m.cagr != 0.0
        assert m.total_return == pytest.approx(0.05, abs=1e-10)

    @pytest.mark.test_id("1.5-UNIT-005")
    @pytest.mark.p2
    def test_non_finite_equity(self):
        r = _make_returns([0.0, 0.0, 0.0])
        m = compute_metrics(r)
        assert isinstance(m.cagr, float)


class TestSharpe:
    @pytest.mark.test_id("1.5-UNIT-006")
    @pytest.mark.p1
    def test_with_nonzero_rf(self):
        r = _make_returns([0.01, -0.005, 0.02, 0.003, -0.001])
        m = compute_metrics(r, rf=0.02)
        assert isinstance(m.sharpe, float)
        assert np.isfinite(m.sharpe)

    @pytest.mark.test_id("1.5-UNIT-007")
    @pytest.mark.p1
    def test_zero_deviation_returns_zero(self):
        r = _make_returns([0.0, 0.0, 0.0])
        m = compute_metrics(r)
        assert m.sharpe == 0.0


class TestSortino:
    @pytest.mark.test_id("1.5-UNIT-008")
    @pytest.mark.p1
    def test_all_positive_returns(self):
        r = _make_returns([0.01, 0.02, 0.015, 0.03])
        m = compute_metrics(r)
        assert m.sortino == 0.0

    @pytest.mark.test_id("1.5-UNIT-009")
    @pytest.mark.p1
    def test_mixed_returns(self):
        r = _make_returns([0.01, -0.02, 0.03, -0.01, 0.005])
        m = compute_metrics(r)
        assert m.sortino != 0.0
        assert np.isfinite(m.sortino)


class TestCalmar:
    @pytest.mark.test_id("1.5-UNIT-010")
    @pytest.mark.p1
    def test_zero_drawdown(self):
        r = _make_returns([0.01, 0.01, 0.01])
        m = compute_metrics(r)
        assert m.calmar == 0.0


class TestWinRate:
    @pytest.mark.test_id("1.5-UNIT-011")
    @pytest.mark.p1
    def test_excludes_zero_returns(self):
        r = _make_returns([0.01, 0.0, -0.01])
        m = compute_metrics(r)
        assert m.win_rate == pytest.approx(0.5, abs=1e-10)

    @pytest.mark.test_id("1.5-UNIT-012")
    @pytest.mark.p2
    def test_all_zero_returns(self):
        r = _make_returns([0.0, 0.0, 0.0])
        m = compute_metrics(r)
        assert m.win_rate == 0.0


class TestMetricsToDict:
    @pytest.mark.test_id("1.5-UNIT-013")
    @pytest.mark.p1
    def test_round_trip_keys(self):
        m = Metrics(total_return=0.1, cagr=0.05, annual_vol=0.15, sharpe=1.0,
                     sortino=1.2, max_drawdown=-0.1, calmar=0.5, win_rate=0.6, n_bars=100)
        d = m.to_dict()
        assert set(d.keys()) == {
            "total_return", "cagr", "annual_vol", "sharpe", "sortino",
            "max_drawdown", "calmar", "win_rate", "n_bars",
        }
        assert d["n_bars"] == 100
        assert d["sharpe"] == 1.0


class TestMaxDrawdown:
    @pytest.mark.test_id("1.5-UNIT-014")
    @pytest.mark.p1
    def test_monotonically_increasing(self):
        equity = pd.Series([100, 110, 120, 130])
        assert max_drawdown(equity) == 0.0

    @pytest.mark.test_id("1.5-UNIT-015")
    @pytest.mark.p2
    def test_known_drawdown(self):
        equity = pd.Series([100, 110, 90, 95])
        dd = max_drawdown(equity)
        assert dd < 0
        assert dd == pytest.approx(-0.1818, abs=0.01)


class TestDrawdownSeries:
    @pytest.mark.test_id("1.5-UNIT-016")
    @pytest.mark.p1
    def test_always_non_positive(self):
        equity = pd.Series([100, 110, 90, 105, 80])
        dd = drawdown_series(equity)
        assert (dd <= 0).all()

    @pytest.mark.test_id("1.5-UNIT-017")
    @pytest.mark.p2
    def test_same_length_as_input(self):
        equity = pd.Series([100, 105, 95])
        dd = drawdown_series(equity)
        assert len(dd) == len(equity)


class TestAnnualVol:
    @pytest.mark.test_id("1.5-UNIT-018")
    @pytest.mark.p1
    def test_computation(self):
        r = _make_returns([0.01, -0.005, 0.02, -0.01, 0.003])
        m = compute_metrics(r, bars_per_year=252)
        expected_vol = float(r.std(ddof=0) * np.sqrt(252))
        assert m.annual_vol == pytest.approx(expected_vol, abs=1e-10)


class TestNBars:
    @pytest.mark.test_id("1.5-UNIT-019")
    @pytest.mark.p1
    def test_drops_nan(self):
        r = pd.Series([0.01, np.nan, 0.02, np.nan, 0.03])
        m = compute_metrics(r)
        assert m.n_bars == 3
