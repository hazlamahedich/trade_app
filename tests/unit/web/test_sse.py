from __future__ import annotations

import pytest
from pydantic import ValidationError

from trade_advisor.web.sse import ErrorEvent, ProgressEvent, SSEEvent


class TestSSEEventModels:
    def test_progress_event_creation(self):
        evt = ProgressEvent(
            event_type="progress",
            run_id="test-run",
            timestamp="2024-01-01T00:00:00Z",
            current=1,
            total=10,
            message="Running",
        )
        assert evt.event_type == "progress"
        assert evt.current == 1
        assert evt.total == 10

    def test_error_event_creation(self):
        evt = ErrorEvent(
            event_type="error",
            run_id="test-run",
            timestamp="2024-01-01T00:00:00Z",
            error_code="DATA_ERROR",
            detail="Something went wrong",
        )
        assert evt.event_type == "error"
        assert evt.error_code == "DATA_ERROR"

    def test_progress_is_subclass_of_sse(self):
        assert issubclass(ProgressEvent, SSEEvent)

    def test_error_is_subclass_of_sse(self):
        assert issubclass(ErrorEvent, SSEEvent)

    def test_round_trip_serialization(self):
        evt = ProgressEvent(
            event_type="progress",
            run_id="test-run",
            timestamp="2024-01-01T00:00:00Z",
            current=5,
            total=10,
            message="Halfway",
        )
        json_str = evt.model_dump_json()
        restored = ProgressEvent.model_validate_json(json_str)
        assert restored == evt

    def test_invalid_event_type_rejected(self):
        with pytest.raises(ValidationError):
            ProgressEvent(
                event_type="INVALID TYPE",
                run_id="test",
                timestamp="2024-01-01T00:00:00Z",
                current=1,
                total=10,
            )

    def test_total_must_be_positive(self):
        with pytest.raises(ValidationError):
            ProgressEvent(
                event_type="progress",
                run_id="test",
                timestamp="2024-01-01T00:00:00Z",
                current=1,
                total=0,
            )

    def test_current_must_be_non_negative(self):
        with pytest.raises(ValidationError):
            ProgressEvent(
                event_type="progress",
                run_id="test",
                timestamp="2024-01-01T00:00:00Z",
                current=-1,
                total=10,
            )

    def test_missing_required_fields(self):
        with pytest.raises(ValidationError):
            SSEEvent()
