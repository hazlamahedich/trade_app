from __future__ import annotations

import math

import pytest

from trade_advisor.backtest.metrics._helpers import _annualization_factor, _simple_returns


class TestAnnualizationFactor:
    @pytest.mark.test_id("1.5-UNIT-001")
    @pytest.mark.p2
    def test_default_freq(self):
        config = type("Cfg", (), {})()
        result = _annualization_factor(config)
        assert result == pytest.approx(math.sqrt(252), abs=1e-10)

    @pytest.mark.test_id("1.5-UNIT-002")
    @pytest.mark.p2
    def test_daily_freq(self):
        config = type("Cfg", (), {"freq": "1D"})()
        assert _annualization_factor(config) == pytest.approx(math.sqrt(252), abs=1e-10)

    @pytest.mark.test_id("1.5-UNIT-003")
    @pytest.mark.p2
    def test_weekly_freq(self):
        config = type("Cfg", (), {"freq": "1W"})()
        assert _annualization_factor(config) == pytest.approx(math.sqrt(52), abs=1e-10)

    @pytest.mark.test_id("1.5-UNIT-004")
    @pytest.mark.p2
    def test_monthly_freq(self):
        config = type("Cfg", (), {"freq": "1M"})()
        assert _annualization_factor(config) == pytest.approx(math.sqrt(12), abs=1e-10)

    @pytest.mark.test_id("1.5-UNIT-005")
    @pytest.mark.p2
    def test_hourly_freq(self):
        config = type("Cfg", (), {"freq": "1H"})()
        assert _annualization_factor(config) == pytest.approx(math.sqrt(252 * 6.5), abs=1e-10)

    @pytest.mark.test_id("1.5-UNIT-006")
    @pytest.mark.p2
    def test_unknown_freq_falls_back_to_daily(self):
        config = type("Cfg", (), {"freq": "5m"})()
        assert _annualization_factor(config) == pytest.approx(math.sqrt(252), abs=1e-10)


class TestSimpleReturns:
    @pytest.mark.test_id("1.5-UNIT-007")
    @pytest.mark.p2
    def test_passthrough(self):
        import pandas as pd

        returns = pd.Series([0.01, -0.02, 0.03])
        result_obj = type("Res", (), {"returns": returns})()
        out = _simple_returns(result_obj)
        assert out is returns
