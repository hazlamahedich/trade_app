"""TaskRunner protocol and supporting types for background computations.

This module defines the Protocol, Pydantic models, and the InProcessTaskRunner
concrete implementation for single-process background task execution.
"""

from __future__ import annotations

import asyncio
import enum
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class TaskStatus(enum.StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"
    INTERRUPTED = "INTERRUPTED"


class BackgroundTask(BaseModel):
    task_type: str
    config: dict[str, Any] = Field(default_factory=dict)
    run_id: str
    submitted_at: datetime = Field(default_factory=datetime.now)


class ProgressEvent(BaseModel):
    run_id: str
    current: int = 0
    total: int = 0
    message: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)


class TaskHandle(BaseModel):
    run_id: str
    status: TaskStatus = TaskStatus.PENDING
    submitted_at: datetime = Field(default_factory=datetime.now)
    completed_at: datetime | None = None


@runtime_checkable
class TaskRunner(Protocol):
    async def submit(
        self,
        task: BackgroundTask,
        *,
        on_progress: Any | None = None,
    ) -> str: ...

    async def cancel(self, run_id: str) -> None: ...

    async def status(self, run_id: str) -> TaskHandle: ...


@dataclass
class _TaskState:
    task: BackgroundTask
    handle: TaskHandle
    cancel_requested: bool = False
    on_progress: Callable[..., Any] | None = None
    _async_task: asyncio.Task[None] | None = field(default=None, repr=False)


class InProcessTaskRunner:
    """Concrete TaskRunner using asyncio for single-process execution."""

    def __init__(self) -> None:
        self._tasks: dict[str, _TaskState] = {}

    async def submit(
        self,
        task: BackgroundTask,
        *,
        handler: Callable[..., Any],
        on_progress: Callable[..., Any] | None = None,
    ) -> str:
        run_id = task.run_id or uuid.uuid4().hex[:12]
        if task.run_id != run_id:
            task = task.model_copy(update={"run_id": run_id})

        handle = TaskHandle(
            run_id=run_id,
            status=TaskStatus.PENDING,
            submitted_at=task.submitted_at,
        )
        state = _TaskState(
            task=task,
            handle=handle,
            on_progress=on_progress,
        )
        self._tasks[run_id] = state

        async_task = asyncio.create_task(self._execute(run_id, handler))
        state._async_task = async_task

        return run_id

    async def cancel(self, run_id: str) -> None:
        state = self._tasks.get(run_id)
        if state is None:
            return
        state.cancel_requested = True
        if state._async_task is not None and not state._async_task.done():
            state._async_task.cancel()

    async def status(self, run_id: str) -> TaskHandle:
        state = self._tasks.get(run_id)
        if state is None:
            raise KeyError(f"Unknown run_id: {run_id}")
        return state.handle

    async def _execute(
        self,
        run_id: str,
        handler: Callable[..., Any],
    ) -> None:
        state = self._tasks[run_id]
        state.handle.status = TaskStatus.RUNNING
        try:
            await handler(
                state.task,
                on_progress=state.on_progress,
                cancel_check=lambda: state.cancel_requested,
            )
            if state.cancel_requested:
                state.handle.status = TaskStatus.CANCELLED
            else:
                state.handle.status = TaskStatus.COMPLETED
        except asyncio.CancelledError:
            state.handle.status = TaskStatus.CANCELLED
            state.handle.completed_at = datetime.now()
            raise
        except Exception:
            state.handle.status = TaskStatus.FAILED
        finally:
            if state.handle.completed_at is None:
                state.handle.completed_at = datetime.now()
