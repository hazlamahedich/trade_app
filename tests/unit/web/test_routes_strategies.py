from __future__ import annotations

import pytest

from trade_advisor.web.routes.strategies import (
    _safe_float,
    _safe_int,
    _safe_symbol,
    _validate_inputs,
)


class TestSafeInt:
    def test_none_returns_fallback(self):
        assert _safe_int(None, 42) == 42

    def test_valid_string(self):
        assert _safe_int("10", 0) == 10

    def test_invalid_string_returns_fallback(self):
        assert _safe_int("abc", 7) == 7

    def test_float_string_returns_fallback(self):
        assert _safe_int("3.7", 0) == 0


class TestSafeFloat:
    def test_none_returns_fallback(self):
        assert _safe_float(None, 1.0) == 1.0

    def test_valid_string(self):
        assert _safe_float("3.14", 0.0) == pytest.approx(3.14)

    def test_invalid_string_returns_fallback(self):
        assert _safe_float("bad", 2.0) == 2.0


class TestSafeSymbol:
    def test_none_returns_fallback(self):
        assert _safe_symbol(None, "SPY") == "SPY"

    def test_valid_symbol_uppercased(self):
        assert _safe_symbol("aapl", "SPY") == "AAPL"

    def test_symbol_with_dots(self):
        assert _safe_symbol("BRK.B", "SPY") == "BRK.B"

    def test_symbol_with_dashes(self):
        assert _safe_symbol("GC-F", "SPY") == "GC-F"

    def test_xss_rejected(self):
        assert _safe_symbol("<script>", "SPY") == "SPY"

    def test_sql_injection_rejected(self):
        assert _safe_symbol("DROP TABLE", "SPY") == "SPY"

    def test_spaces_rejected(self):
        assert _safe_symbol("AA PL", "SPY") == "SPY"


class TestValidateInputs:
    def test_valid_inputs_return_none(self):
        assert (
            _validate_inputs("SPY", 20, 50, "2020-01-01", "2025-01-01", 100000, 0.001, 0.0005)
            is None
        )

    def test_empty_symbol(self):
        assert "Symbol" in (
            _validate_inputs("", 20, 50, "2020-01-01", "2025-01-01", 100000, 0.001, 0.0005) or ""
        )

    def test_fast_equals_slow(self):
        result = _validate_inputs("SPY", 20, 20, "2020-01-01", "2025-01-01", 100000, 0.001, 0.0005)
        assert result is not None and "less than" in result

    def test_fast_greater_than_slow(self):
        result = _validate_inputs("SPY", 50, 20, "2020-01-01", "2025-01-01", 100000, 0.001, 0.0005)
        assert result is not None

    def test_zero_fast(self):
        result = _validate_inputs("SPY", 0, 50, "2020-01-01", "2025-01-01", 100000, 0.001, 0.0005)
        assert result is not None and "positive" in result.lower()

    def test_zero_initial_cash(self):
        result = _validate_inputs("SPY", 20, 50, "2020-01-01", "2025-01-01", 0, 0.001, 0.0005)
        assert result is not None and "positive" in result.lower()

    def test_infinite_cash(self):
        result = _validate_inputs(
            "SPY", 20, 50, "2020-01-01", "2025-01-01", float("inf"), 0.001, 0.0005
        )
        assert result is not None and "finite" in result.lower()

    def test_negative_commission(self):
        result = _validate_inputs("SPY", 20, 50, "2020-01-01", "2025-01-01", 100000, -0.01, 0.0005)
        assert result is not None and "non-negative" in result.lower()

    def test_commission_over_one(self):
        result = _validate_inputs("SPY", 20, 50, "2020-01-01", "2025-01-01", 100000, 1.5, 0.0005)
        assert result is not None and "1.0" in result

    def test_slippage_over_one(self):
        result = _validate_inputs("SPY", 20, 50, "2020-01-01", "2025-01-01", 100000, 0.001, 1.5)
        assert result is not None and "1.0" in result

    def test_commission_exactly_one_ok(self):
        assert (
            _validate_inputs("SPY", 20, 50, "2020-01-01", "2025-01-01", 100000, 1.0, 0.0005) is None
        )

    def test_invalid_dates(self):
        result = _validate_inputs("SPY", 20, 50, "not-a-date", "also-bad", 100000, 0.001, 0.0005)
        assert result is not None and "date" in result.lower()

    def test_start_after_end(self):
        result = _validate_inputs("SPY", 20, 50, "2025-01-01", "2020-01-01", 100000, 0.001, 0.0005)
        assert result is not None and "before" in result.lower()

    def test_start_equals_end(self):
        result = _validate_inputs("SPY", 20, 50, "2023-01-01", "2023-01-01", 100000, 0.001, 0.0005)
        assert result is not None
