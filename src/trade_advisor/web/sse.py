from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SSEEvent(BaseModel):
    event_type: str = Field(..., pattern=r"^[a-z_]+$")
    run_id: str
    timestamp: str


class ProgressEvent(SSEEvent):
    event_type: Literal["progress"] = "progress"
    current: int = Field(..., ge=0)
    total: int = Field(..., ge=1)
    message: str = ""


class ErrorEvent(SSEEvent):
    event_type: Literal["error"] = "error"
    error_code: str = ""
    detail: str = ""


# TODO: ResultEvent — Story 1.7
