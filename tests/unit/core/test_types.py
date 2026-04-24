"""Unit tests for core/types.py — PrecisionPolicy, type aliases, conversion functions."""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal

import pytest

from tests.unit.core.fixtures import (
    ASSET_CLASS_QUANTIZATION_ORACLE,
    ROUND_HALF_EVEN_ORACLE,
)
from trade_advisor.core.types import (
    CRYPTO,
    EQUITY,
    FX,
    BasisPoints,
    Currency,
    Notional,
    PrecisionPolicy,
    Price,
    Quantity,
    Returns,
    Side,
    Signal,
    decimal_to_str,
    from_float,
    log_to_simple,
    simple_to_log,
    to_float,
)


class TestPrecisionPolicy:
    def test_equity_tick_size(self):
        assert EQUITY.tick_size == Decimal("0.01")
        assert EQUITY.label == "EQUITY"

    def test_fx_tick_size(self):
        assert FX.tick_size == Decimal("0.0001")
        assert FX.label == "FX"

    def test_crypto_tick_size(self):
        assert CRYPTO.tick_size == Decimal("0.00000001")
        assert CRYPTO.label == "CRYPTO"

    @pytest.mark.parametrize(
        "input_val, tick_size, label, expected",
        ASSET_CLASS_QUANTIZATION_ORACLE,
    )
    def test_quantization_oracle(self, input_val, tick_size, label, expected):
        policy = PrecisionPolicy(tick_size=Decimal(tick_size), label=label)
        result = policy.quantize(Decimal(input_val))
        assert result == Decimal(expected)

    def test_quantize_uses_round_half_even(self):
        result = EQUITY.quantize(Decimal("1.005"))
        assert result == Decimal("1.00")

    def test_precision_policy_frozen(self):
        with pytest.raises(AttributeError):
            EQUITY.tick_size = Decimal("0.001")  # type: ignore[misc]

    def test_tick_size_must_be_positive(self):
        with pytest.raises(ValueError, match="positive"):
            PrecisionPolicy(tick_size=Decimal("0"), label="BAD")

    def test_tick_size_negative_raises(self):
        with pytest.raises(ValueError, match="positive"):
            PrecisionPolicy(tick_size=Decimal("-0.01"), label="BAD")


class TestRoundHalfEvenOracle:
    @pytest.mark.parametrize("input_val, expected", ROUND_HALF_EVEN_ORACLE)
    def test_bankers_rounding_oracle(self, input_val, expected):
        result = Decimal(input_val).quantize(Decimal(10) ** -10, rounding=ROUND_HALF_EVEN)
        assert format(result, "f") == expected


class TestDecimalToStr:
    def test_serialization_precision(self):
        assert decimal_to_str(Decimal("1.23456789015")) == "1.2345678902"

    def test_trailing_zeros(self):
        assert decimal_to_str(Decimal("1.00")) == "1.0000000000"

    def test_negative(self):
        result = decimal_to_str(Decimal("-1.5"))
        assert result.startswith("-")

    def test_nan_raises(self):
        with pytest.raises(ValueError, match="non-finite"):
            decimal_to_str(Decimal("NaN"))

    def test_inf_raises(self):
        with pytest.raises(ValueError, match="non-finite"):
            decimal_to_str(Decimal("Infinity"))


class TestFromFloat:
    def test_basic_conversion(self):
        d = from_float(1.5)
        assert d == Decimal("1.5")

    def test_high_precision(self):
        d = from_float(0.1)
        assert d == Decimal("0.1")

    def test_nan_raises(self):
        with pytest.raises(ValueError, match="non-finite"):
            from_float(float("nan"))

    def test_inf_raises(self):
        with pytest.raises(ValueError, match="non-finite"):
            from_float(float("inf"))


class TestToFloat:
    def test_basic_conversion(self):
        f = to_float(Decimal("1.5"))
        assert f == 1.5
        assert isinstance(f, float)

    def test_precision_loss_documented(self):
        f = to_float(Decimal("0.123456789012345678"))
        assert isinstance(f, float)

    def test_nan_raises(self):
        with pytest.raises(ValueError, match="non-finite"):
            to_float(Decimal("NaN"))

    def test_inf_raises(self):
        with pytest.raises(ValueError, match="non-finite"):
            to_float(Decimal("Infinity"))


class TestFloatRoundTrip:
    def test_round_trip_common_values(self):
        for v in [0.0, 1.0, -1.0, 100.5, 0.001]:
            assert to_float(from_float(v)) == v


class TestReturnConversions:
    def test_log_to_simple_zero(self):
        result = log_to_simple(Decimal("0"))
        assert abs(result) < Decimal("1e-15")

    def test_simple_to_log_zero(self):
        result = simple_to_log(Decimal("0"))
        assert abs(result) < Decimal("1e-15")

    def test_log_simple_round_trip(self):
        log_ret = Decimal("0.05")
        simple = log_to_simple(log_ret)
        back = simple_to_log(simple)
        assert abs(back - log_ret) < Decimal("1e-12")

    def test_simple_log_round_trip(self):
        simple_ret = Decimal("0.10")
        log_val = simple_to_log(simple_ret)
        back = log_to_simple(log_val)
        assert abs(back - simple_ret) < Decimal("1e-12")

    def test_log_to_simple_overflow_raises(self):
        with pytest.raises(ValueError, match="overflow"):
            log_to_simple(Decimal("701"))

    def test_simple_to_log_domain_error(self):
        with pytest.raises(ValueError, match="domain error"):
            simple_to_log(Decimal("-1"))

    def test_simple_to_log_below_minus_one_raises(self):
        with pytest.raises(ValueError, match="domain error"):
            simple_to_log(Decimal("-1.5"))


class TestTypeAliases:
    def test_price_is_decimal(self):
        p: Price = Decimal("100.50")
        assert isinstance(p, Decimal)

    def test_quantity_is_decimal(self):
        q: Quantity = Decimal("10")
        assert isinstance(q, Decimal)

    def test_notional_is_decimal(self):
        n: Notional = Decimal("1005.00")
        assert isinstance(n, Decimal)

    def test_returns_is_decimal(self):
        r: Returns = Decimal("0.05")
        assert isinstance(r, Decimal)

    def test_basis_points_is_decimal(self):
        bp: BasisPoints = Decimal("5.0")
        assert isinstance(bp, Decimal)

    def test_signal_literal(self):
        s1: Signal = 1
        s0: Signal = 0
        sm: Signal = -1
        assert s1 == 1
        assert s0 == 0
        assert sm == -1

    def test_side_literal(self):
        long: Side = "long"
        short: Side = "short"
        assert long == "long"
        assert short == "short"

    def test_currency_literal(self):
        usd: Currency = "USD"
        assert usd == "USD"
