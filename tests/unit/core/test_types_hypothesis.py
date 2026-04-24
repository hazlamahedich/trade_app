"""Property-based tests for core/types.py using Hypothesis."""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given, settings
from hypothesis.strategies import decimals as st_decimals
from hypothesis.strategies import floats as st_floats

from trade_advisor.core.types import (
    CRYPTO,
    EQUITY,
    FX,
    decimal_to_str,
    from_float,
    to_float,
)


class TestSerializationIdempotency:
    @given(d=st_decimals(min_value=Decimal("-1e10"), max_value=Decimal("1e10")))
    @settings(max_examples=200)
    def test_double_serialize_is_idempotent(self, d: Decimal):
        first = decimal_to_str(d)
        second = decimal_to_str(Decimal(first))
        assert first == second


class TestQuantizationIdempotency:
    @given(
        d=st_decimals(
            min_value=Decimal("0.01"),
            max_value=Decimal("100000"),
            places=18,
        )
    )
    @settings(max_examples=200)
    def test_equity_quantize_idempotent(self, d: Decimal):
        q1 = EQUITY.quantize(d)
        q2 = EQUITY.quantize(q1)
        assert q1 == q2

    @given(
        d=st_decimals(
            min_value=Decimal("0.0001"),
            max_value=Decimal("100000"),
            places=18,
        )
    )
    @settings(max_examples=200)
    def test_fx_quantize_idempotent(self, d: Decimal):
        q1 = FX.quantize(d)
        q2 = FX.quantize(q1)
        assert q1 == q2

    @given(
        d=st_decimals(
            min_value=Decimal("0.00000001"),
            max_value=Decimal("100000"),
            places=18,
        )
    )
    @settings(max_examples=200)
    def test_crypto_quantize_idempotent(self, d: Decimal):
        q1 = CRYPTO.quantize(d)
        q2 = CRYPTO.quantize(q1)
        assert q1 == q2


class TestFloatRoundTrip:
    @given(
        f=st_floats(
            min_value=-1e10,
            max_value=1e10,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    @settings(max_examples=200)
    def test_from_float_to_float_round_trip(self, f: float):
        d = from_float(f)
        back = to_float(d)
        assert back == f


class TestDecimalArithmeticCommutativity:
    @given(
        a=st_decimals(min_value=Decimal("-1e5"), max_value=Decimal("1e5")),
        b=st_decimals(min_value=Decimal("-1e5"), max_value=Decimal("1e5")),
    )
    @settings(max_examples=200)
    def test_addition_commutative(self, a: Decimal, b: Decimal):
        assert a + b == b + a

    @given(
        a=st_decimals(min_value=Decimal("0.001"), max_value=Decimal("1e5")),
        b=st_decimals(min_value=Decimal("0.001"), max_value=Decimal("1e5")),
    )
    @settings(max_examples=200)
    def test_multiplication_commutative(self, a: Decimal, b: Decimal):
        assert a * b == b * a
