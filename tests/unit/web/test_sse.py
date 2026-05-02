from __future__ import annotations

import pytest
from pydantic import ValidationError

from trade_advisor.web.sse import (
    ErrorEvent,
    ProgressEvent,
    SSEEvent,
    WalkForwardCancelledEvent,
    WalkForwardCompletedEvent,
    WalkForwardProgressEvent,
)


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


class TestWalkForwardSSEEvents:
    def test_progress_event_creation(self):
        evt = WalkForwardProgressEvent(
            run_id="test",
            timestamp="2026-01-01T00:00:00Z",
            window_idx=0,
            total_windows=6,
            is_sharpe=1.2,
            oos_sharpe=0.8,
            oos_return=0.05,
            status="OK",
        )
        assert evt.event_type == "wf_progress"
        assert evt.window_idx == 0
        assert evt.total_windows == 6
        assert evt.is_sharpe == 1.2
        assert evt.oos_sharpe == 0.8
        assert evt.oos_return == 0.05
        assert evt.status == "OK"

    def test_progress_event_inconclusive(self):
        evt = WalkForwardProgressEvent(
            run_id="test",
            timestamp="2026-01-01T00:00:00Z",
            window_idx=2,
            total_windows=6,
            is_sharpe=0.5,
            oos_sharpe=float("nan"),
            oos_return=float("nan"),
            status="INCONCLUSIVE",
        )
        assert evt.status == "INCONCLUSIVE"

    def test_completed_event_creation(self):
        evt = WalkForwardCompletedEvent(
            run_id="test",
            timestamp="2026-01-01T00:00:00Z",
            n_windows=6,
            discarded_bars=12,
        )
        assert evt.event_type == "wf_completed"
        assert evt.n_windows == 6
        assert evt.discarded_bars == 12

    def test_completed_event_zero_windows_valid(self):
        evt = WalkForwardCompletedEvent(
            run_id="test",
            timestamp="2026-01-01T00:00:00Z",
            n_windows=0,
            discarded_bars=0,
        )
        assert evt.n_windows == 0

    def test_cancelled_event_creation(self):
        evt = WalkForwardCancelledEvent(
            run_id="test",
            timestamp="2026-01-01T00:00:00Z",
            reason="User requested cancellation",
        )
        assert evt.event_type == "wf_cancelled"
        assert evt.reason == "User requested cancellation"

    def test_progress_is_subclass_of_sse(self):
        assert issubclass(WalkForwardProgressEvent, SSEEvent)

    def test_completed_is_subclass_of_sse(self):
        assert issubclass(WalkForwardCompletedEvent, SSEEvent)

    def test_cancelled_is_subclass_of_sse(self):
        assert issubclass(WalkForwardCancelledEvent, SSEEvent)

    def test_progress_round_trip(self):
        evt = WalkForwardProgressEvent(
            run_id="test",
            timestamp="2026-01-01T00:00:00Z",
            window_idx=0,
            total_windows=6,
            is_sharpe=1.2,
            oos_sharpe=0.8,
            oos_return=0.05,
            status="OK",
        )
        data = evt.model_dump()
        assert data["event_type"] == "wf_progress"
        assert data["window_idx"] == 0
