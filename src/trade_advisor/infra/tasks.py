"""TaskRunner protocol and supporting types for background computations.

This module defines the Protocol and Pydantic models only.
Full implementation is deferred to Epic 2+.
"""

from __future__ import annotations

import enum
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
