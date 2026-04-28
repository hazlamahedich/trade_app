"""QTAError exception hierarchy with domain-specific subclasses.

Each exception carries an ``error_code``, ``http_status``, ``correlation_id``,
and ``details`` dict.  The ``to_error_response()`` method produces a structured
``ErrorResponse`` envelope.
"""

from __future__ import annotations

import uuid
from typing import Any, ClassVar

from trade_advisor.core.schemas import ErrorDetail, ErrorResponse


class QTAError(Exception):
    """Base exception for all trade_advisor domain errors."""

    error_code: ClassVar[str] = "QTA_ERROR"
    http_status: ClassVar[int] = 500

    def __init__(
        self,
        message: str = "",
        *,
        correlation_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.details = details or {}

    def to_error_response(self) -> ErrorResponse:
        """Convert to a structured ``ErrorResponse`` envelope."""
        return ErrorResponse(
            error=ErrorDetail(
                code=self.error_code,
                message=self.message,
                correlation_id=self.correlation_id,
                details=self.details,
            ),
        )


class DataError(QTAError):
    """Errors related to market data quality and access."""

    error_code: ClassVar[str] = "DATA_ERROR"
    http_status: ClassVar[int] = 500


class StaleDataError(DataError):
    """Data is stale but still usable — 200 with degraded payload."""

    error_code: ClassVar[str] = "STALE_DATA"
    http_status: ClassVar[int] = 200


class DataGapError(DataError):
    """Unexpected gap in time-series data."""

    error_code: ClassVar[str] = "DATA_GAP"
    http_status: ClassVar[int] = 502


class IntegrityError(DataError):
    """Data integrity violation — corrupted or tampered data."""

    error_code: ClassVar[str] = "INTEGRITY"
    http_status: ClassVar[int] = 500


class ComputationError(QTAError):
    """Errors during feature/statistical computation."""

    error_code: ClassVar[str] = "COMPUTATION_ERROR"
    http_status: ClassVar[int] = 500


class FeatureComputationError(ComputationError):
    """Failure computing a specific feature."""

    error_code: ClassVar[str] = "FEATURE_COMPUTATION"
    http_status: ClassVar[int] = 500


class ConvergenceError(ComputationError):
    """Numerical method failed to converge."""

    error_code: ClassVar[str] = "CONVERGENCE"
    http_status: ClassVar[int] = 500


class BiasDetectionError(QTAError):
    """Bias detected in strategy or data."""

    error_code: ClassVar[str] = "BIAS_DETECTION_ERROR"
    http_status: ClassVar[int] = 500


class LookaheadBiasError(BiasDetectionError):
    """Lookahead bias detected — strategy uses future information."""

    error_code: ClassVar[str] = "LOOKAHEAD_BIAS"
    http_status: ClassVar[int] = 500


class SurvivorshipBiasError(BiasDetectionError):
    """Survivorship bias detected — 200 with warning."""

    error_code: ClassVar[str] = "SURVIVORSHIP_BIAS"
    http_status: ClassVar[int] = 200


class ConfigurationError(QTAError):
    """Invalid or missing configuration."""

    error_code: ClassVar[str] = "CONFIG"
    http_status: ClassVar[int] = 503


class BoundaryViolationError(QTAError):
    """Decimal/float boundary crossed improperly — potential leak."""

    error_code: ClassVar[str] = "LEAK_DETECTED"
    http_status: ClassVar[int] = 500


class InsufficientHistoryError(QTAError):
    """Not enough historical data for the requested operation."""

    error_code: ClassVar[str] = "INSUFFICIENT_HISTORY"
    http_status: ClassVar[int] = 422
