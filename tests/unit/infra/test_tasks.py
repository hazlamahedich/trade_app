"""Tests for infra/tasks.py — TaskRunner Protocol + types."""

from __future__ import annotations

from datetime import datetime

from trade_advisor.infra.tasks import (
    BackgroundTask,
    ProgressEvent,
    TaskHandle,
    TaskRunner,
    TaskStatus,
)


class TestTaskStatusEnum:
    def test_task_status_enum_values(self):
        expected = {
            "PENDING",
            "RUNNING",
            "COMPLETED",
            "FAILED",
            "CANCELLED",
            "TIMED_OUT",
            "INTERRUPTED",
        }
        actual = {s.value for s in TaskStatus}
        assert actual == expected

    def test_all_seven_statuses(self):
        assert len(TaskStatus) == 7


class TestBackgroundTask:
    def test_background_task_serialization(self):
        task = BackgroundTask(
            task_type="backtest",
            config={"symbol": "SPY"},
            run_id="run-123",
            submitted_at=datetime(2026, 1, 1),
        )
        data = task.model_dump()
        round_tripped = BackgroundTask.model_validate(data)
        assert round_tripped.task_type == "backtest"
        assert round_tripped.config == {"symbol": "SPY"}
        assert round_tripped.run_id == "run-123"

    def test_background_task_defaults(self):
        task = BackgroundTask(task_type="test", run_id="r1")
        assert task.config == {}
        assert task.submitted_at is not None


class TestProgressEvent:
    def test_progress_event_serialization(self):
        event = ProgressEvent(
            run_id="run-1",
            current=5,
            total=100,
            message="processing",
            timestamp=datetime(2026, 1, 1),
        )
        data = event.model_dump()
        rt = ProgressEvent.model_validate(data)
        assert rt.run_id == "run-1"
        assert rt.current == 5
        assert rt.total == 100
        assert rt.message == "processing"

    def test_progress_event_defaults(self):
        event = ProgressEvent(run_id="r1")
        assert event.current == 0
        assert event.total == 0
        assert event.message == ""


class TestTaskHandle:
    def test_task_handle_serialization(self):
        handle = TaskHandle(
            run_id="run-1",
            status=TaskStatus.COMPLETED,
            submitted_at=datetime(2026, 1, 1),
            completed_at=datetime(2026, 1, 2),
        )
        data = handle.model_dump()
        rt = TaskHandle.model_validate(data)
        assert rt.run_id == "run-1"
        assert rt.status == TaskStatus.COMPLETED
        assert rt.completed_at is not None

    def test_task_handle_defaults(self):
        handle = TaskHandle(run_id="r1")
        assert handle.status == TaskStatus.PENDING
        assert handle.completed_at is None


class TestTaskRunnerProtocol:
    async def test_task_runner_protocol_compliance(self):
        class DummyRunner:
            async def submit(self, task, *, on_progress=None):
                return task.run_id

            async def cancel(self, run_id):
                pass

            async def status(self, run_id):
                return TaskHandle(run_id=run_id, status=TaskStatus.COMPLETED)

        runner = DummyRunner()
        assert isinstance(runner, TaskRunner)
        task = BackgroundTask(task_type="test", run_id="r1")
        result = await runner.submit(task)
        assert result == "r1"
        handle = await runner.status("r1")
        assert handle.status == TaskStatus.COMPLETED
