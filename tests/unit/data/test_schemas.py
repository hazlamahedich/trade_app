from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pandas as pd
import pytest
from pydantic import ValidationError

from trade_advisor.data.schemas import Bar


def _valid_bar(**overrides) -> Bar:
    defaults = dict(
        symbol="TEST",
        timestamp=pd.Timestamp("2024-01-01", tz="UTC"),
        resolution=timedelta(days=1),
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100.5"),
        volume=Decimal("1000000"),
    )
    defaults.update(overrides)
    return Bar(**defaults)


class TestBarModelValid:
    def test_valid_bar(self):
        bar = _valid_bar()
        assert bar.symbol == "TEST"
        assert bar.open == Decimal("100")

    def test_all_equal_prices(self):
        bar = _valid_bar(
            open=Decimal("100"), high=Decimal("100"), low=Decimal("100"), close=Decimal("100")
        )
        assert bar.high == Decimal("100")

    def test_volume_zero_valid(self):
        bar = _valid_bar(volume=Decimal("0"))
        assert bar.volume == Decimal("0")

    def test_optional_fields_default_none(self):
        bar = _valid_bar()
        assert bar.vwap is None
        assert bar.trade_count is None

    def test_optional_fields_set(self):
        bar = _valid_bar(vwap=Decimal("100.25"), trade_count=500)
        assert bar.vwap == Decimal("100.25")
        assert bar.trade_count == 500

    def test_high_equals_max_open_close(self):
        bar = _valid_bar(
            open=Decimal("99"), high=Decimal("100.5"), low=Decimal("98"), close=Decimal("100.5")
        )
        assert bar.high >= bar.close

    def test_low_equals_min_open_close(self):
        bar = _valid_bar(
            open=Decimal("100"), high=Decimal("101"), low=Decimal("99"), close=Decimal("99")
        )
        assert bar.low <= bar.close


class TestBarHighValidator:
    def test_high_less_than_close_raises(self):
        with pytest.raises(ValidationError, match="high.*must be >= max"):
            _valid_bar(high=Decimal("99"), close=Decimal("100.5"))

    def test_high_less_than_open_raises(self):
        with pytest.raises(ValidationError, match="high.*must be >= max"):
            _valid_bar(
                high=Decimal("98"), low=Decimal("95"), open=Decimal("100"), close=Decimal("99")
            )

    def test_high_equals_close_valid(self):
        bar = _valid_bar(high=Decimal("100.5"))
        assert bar.high == Decimal("100.5")


class TestBarLowValidator:
    def test_low_greater_than_open_raises(self):
        with pytest.raises(ValidationError, match="low.*must be <= min"):
            _valid_bar(
                high=Decimal("105"), low=Decimal("102"), open=Decimal("100"), close=Decimal("101")
            )

    def test_low_greater_than_close_raises(self):
        with pytest.raises(ValidationError, match="low.*must be <= min"):
            _valid_bar(low=Decimal("101"), open=Decimal("99"), close=Decimal("100"))

    def test_low_equals_open_valid(self):
        bar = _valid_bar(low=Decimal("100"), open=Decimal("100"))
        assert bar.low == Decimal("100")


class TestBarPositivePrices:
    def test_negative_open_raises(self):
        with pytest.raises(ValidationError, match="positive"):
            _valid_bar(open=Decimal("-1"))

    def test_negative_high_raises(self):
        with pytest.raises(ValidationError, match="positive"):
            _valid_bar(high=Decimal("-1"))

    def test_negative_low_raises(self):
        with pytest.raises(ValidationError, match="positive"):
            _valid_bar(low=Decimal("-1"))

    def test_negative_close_raises(self):
        with pytest.raises(ValidationError, match="positive"):
            _valid_bar(close=Decimal("-1"))

    def test_zero_open_raises(self):
        with pytest.raises(ValidationError, match="positive"):
            _valid_bar(open=Decimal("0"))

    def test_zero_high_raises(self):
        with pytest.raises(ValidationError, match="positive"):
            _valid_bar(high=Decimal("0"))

    def test_zero_low_raises(self):
        with pytest.raises(ValidationError, match="positive"):
            _valid_bar(low=Decimal("0"))

    def test_zero_close_raises(self):
        with pytest.raises(ValidationError, match="positive"):
            _valid_bar(close=Decimal("0"))

    def test_nan_in_float_raises(self):
        with pytest.raises(ValidationError):
            _valid_bar(open=Decimal("nan"))

    def test_infinity_raises(self):
        with pytest.raises(ValidationError):
            _valid_bar(close=Decimal("inf"))


class TestBarFrozen:
    def test_frozen_model(self):
        bar = _valid_bar()
        with pytest.raises(ValidationError):
            bar.symbol = "CHANGED"
