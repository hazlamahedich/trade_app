from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class WFWindowResponse(BaseModel):
    window_idx: int
    is_start: str
    is_end: str
    oos_start: str
    oos_end: str
    is_sharpe: float
    oos_sharpe: float
    is_return: float
    oos_return: float
    params: dict[str, Any] | None = None


class WFDiagnosticsResponse(BaseModel):
    risk_adj_wfe: float
    expected_value: float
    oos_p_value: float | None = None
    parameter_decay: float | None = None
    dsr: float | None = None
    dsr_significant: bool = False
    dsr_warning: str | None = None
    hints: dict[str, str] = {}


class WFResultResponse(BaseModel):
    run_id: str
    wfe: float
    wfe_status: Literal["healthy", "caution", "unreliable"]
    equity: list[dict[str, Any]]
    baseline: list[dict[str, Any]]
    windows: list[WFWindowResponse]
    diagnostics: WFDiagnosticsResponse | None = None
    regime_variance: float = 0.0
