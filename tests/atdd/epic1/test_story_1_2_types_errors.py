"""ATDD red-phase: Story 1.2 — Core Type System & Error Taxonomy.

All tests are SKIPPED (TDD red phase). Remove when implementing Story 1.2.
"""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal


class TestStory12CoreTypes:
    """Story 1.2: Shared types, Decimal conventions, structured error hierarchy."""

    def test_precision_policy_exists(self):
        from trade_advisor.core.types import PrecisionPolicy

        assert PrecisionPolicy is not None

    def test_decimal_convention_round_half_even(self):
        from trade_advisor.core.types import quantize

        val = Decimal("2.225")
        result = quantize(val)
        assert result == result.quantize(Decimal("0.0000000001"), rounding=ROUND_HALF_EVEN)

    def test_decimal_10_decimal_places(self):
        from trade_advisor.core.types import quantize

        val = Decimal("1.123456789012345")
        result = quantize(val)
        assert abs(result - Decimal("1.1234567890")) < Decimal("1e-11")

    def test_qta_error_hierarchy(self):
        from trade_advisor.core.errors import (
            BoundaryViolationError,
            ComputationError,
            ConfigurationError,
            DataError,
            IntegrityError,
            QTAError,
            StaleDataError,
        )

        assert issubclass(DataError, QTAError)
        assert issubclass(StaleDataError, DataError)
        assert issubclass(IntegrityError, DataError)
        assert issubclass(ComputationError, QTAError)
        assert issubclass(ConfigurationError, QTAError)
        assert issubclass(BoundaryViolationError, QTAError)

    def test_error_http_status_mapping(self):
        from trade_advisor.core.errors import IntegrityError, StaleDataError

        assert IntegrityError.http_status == 500
        assert StaleDataError.http_status == 200

    def test_success_response_envelope(self):
        from trade_advisor.core.schemas import SuccessResponse

        resp = SuccessResponse(data={"price": "100.00"})
        assert resp.data == {"price": "100.00"}

    def test_error_response_envelope(self):
        from trade_advisor.core.schemas import ErrorResponse

        resp = ErrorResponse(error={"code": "CONFIG", "message": "missing"})
        assert resp.error.code == "CONFIG"

    def test_structured_json_logging(self):
        from trade_advisor.core.logging import setup_logging

        setup_logging()
