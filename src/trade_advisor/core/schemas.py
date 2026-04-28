"""Response envelope schemas for the trade_advisor API.

- ``SuccessResponse`` wraps data in ``{"data": ...}``.
- ``ErrorResponse`` wraps errors in ``{"error": {"code": "...", "message": "..."}}``.
- ``PaginatedResponse`` adds pagination metadata.

All ``Decimal`` fields serialize to ``str`` via ``PlainSerializer``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SuccessResponse(BaseModel):
    data: Any


class ErrorDetail(BaseModel):
    code: str
    message: str
    correlation_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail


class PaginationMeta(BaseModel):
    cursor: str | None = None
    total_count: int = Field(ge=0)


class PaginatedResponse(BaseModel):
    data: list[Any]
    meta: PaginationMeta
