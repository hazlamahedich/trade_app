"""Unit tests for core/errors.py — hierarchy, HTTP status, error codes, to_error_response."""

from __future__ import annotations

import pytest

from trade_advisor.core.errors import (
    BiasDetectionError,
    BoundaryViolationError,
    ComputationError,
    ConfigurationError,
    ConvergenceError,
    DataError,
    DataGapError,
    FeatureComputationError,
    InsufficientHistoryError,
    IntegrityError,
    LookaheadBiasError,
    QTAError,
    StaleDataError,
    SurvivorshipBiasError,
)


class TestQTAErrorBase:
    def test_is_exception(self):
        assert issubclass(QTAError, Exception)

    def test_default_error_code(self):
        assert QTAError.error_code == "QTA_ERROR"

    def test_default_http_status(self):
        assert QTAError.http_status == 500

    def test_correlation_id_auto_generated(self):
        e = QTAError("test")
        assert e.correlation_id is not None
        assert len(e.correlation_id) > 0

    def test_correlation_id_custom(self):
        e = QTAError("test", correlation_id="abc-123")
        assert e.correlation_id == "abc-123"

    def test_details_default_empty(self):
        e = QTAError("test")
        assert e.details == {}

    def test_details_custom(self):
        e = QTAError("test", details={"key": "value"})
        assert e.details == {"key": "value"}

    def test_to_error_response(self):
        e = QTAError("something went wrong")
        resp = e.to_error_response()
        assert resp.error.code == "QTA_ERROR"
        assert resp.error.message == "something went wrong"

    def test_message_stored(self):
        e = QTAError("hello")
        assert e.message == "hello"


class TestHierarchyIsinstance:
    @pytest.mark.parametrize(
        "sub, parent",
        [
            (StaleDataError, DataError),
            (DataGapError, DataError),
            (IntegrityError, DataError),
            (DataError, QTAError),
            (FeatureComputationError, ComputationError),
            (ConvergenceError, ComputationError),
            (ComputationError, QTAError),
            (LookaheadBiasError, BiasDetectionError),
            (SurvivorshipBiasError, BiasDetectionError),
            (BiasDetectionError, QTAError),
            (ConfigurationError, QTAError),
            (BoundaryViolationError, QTAError),
            (InsufficientHistoryError, QTAError),
        ],
    )
    def test_isinstance_checks(self, sub, parent):
        e = sub("test")
        assert isinstance(e, parent)
        assert isinstance(e, QTAError)


class TestHttpStatusMapping:
    @pytest.mark.parametrize(
        "cls, expected_status",
        [
            (IntegrityError, 500),
            (StaleDataError, 200),
            (DataGapError, 502),
            (ConvergenceError, 500),
            (FeatureComputationError, 500),
            (LookaheadBiasError, 500),
            (SurvivorshipBiasError, 200),
            (ConfigurationError, 503),
            (BoundaryViolationError, 500),
            (InsufficientHistoryError, 422),
        ],
    )
    def test_http_status(self, cls, expected_status):
        assert cls.http_status == expected_status


class TestErrorCodeStrings:
    @pytest.mark.parametrize(
        "cls, expected_code",
        [
            (IntegrityError, "INTEGRITY"),
            (StaleDataError, "STALE_DATA"),
            (DataGapError, "DATA_GAP"),
            (ConvergenceError, "CONVERGENCE"),
            (FeatureComputationError, "FEATURE_COMPUTATION"),
            (LookaheadBiasError, "LOOKAHEAD_BIAS"),
            (SurvivorshipBiasError, "SURVIVORSHIP_BIAS"),
            (ConfigurationError, "CONFIG"),
            (BoundaryViolationError, "LEAK_DETECTED"),
            (InsufficientHistoryError, "INSUFFICIENT_HISTORY"),
        ],
    )
    def test_error_code(self, cls, expected_code):
        assert cls.error_code == expected_code


class TestCorrelationIdPropagation:
    def test_subclass_inherits_correlation_id(self):
        cid = "test-correlation-123"
        e = LookaheadBiasError("oops", correlation_id=cid)
        assert e.correlation_id == cid
        resp = e.to_error_response()
        assert resp.error.code == "LOOKAHEAD_BIAS"

    def test_details_propagation(self):
        e = InsufficientHistoryError(
            "need 200 bars",
            details={"required": 200, "available": 50},
        )
        assert e.details["required"] == 200
        assert e.details["available"] == 50
