from __future__ import annotations

from typing import Any, Literal

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


class StrategyForkedEvent(SSEEvent):
    event_type: Literal["strategy_forked"] = "strategy_forked"
    source_run_id: str
    variant_params: dict[str, Any] = {}


class WalkForwardProgressEvent(SSEEvent):
    event_type: Literal["wf_progress"] = "wf_progress"
    window_idx: int = Field(..., ge=0)
    total_windows: int = Field(..., ge=1)
    is_sharpe: float
    oos_sharpe: float
    oos_return: float
    status: Literal["OK", "INCONCLUSIVE", "DEGRADED"]
    message: str = ""


class WalkForwardCompletedEvent(SSEEvent):
    event_type: Literal["wf_completed"] = "wf_completed"
    n_windows: int = Field(..., ge=0)
    discarded_bars: int = Field(..., ge=0)


class WalkForwardCancelledEvent(SSEEvent):
    event_type: Literal["wf_cancelled"] = "wf_cancelled"
    reason: str = ""


# TODO: ResultEvent — Story 1.7
