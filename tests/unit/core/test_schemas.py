"""Unit tests for core/schemas.py — response envelopes and Decimal serialization."""

from __future__ import annotations

from trade_advisor.core.schemas import (
    ErrorDetail,
    ErrorResponse,
    PaginatedResponse,
    PaginationMeta,
    SuccessResponse,
)


class TestSuccessResponse:
    def test_basic(self):
        r = SuccessResponse(data={"price": 100})
        assert r.data == {"price": 100}

    def test_serialization(self):
        r = SuccessResponse(data=[1, 2, 3])
        d = r.model_dump(mode="json")
        assert d == {"data": [1, 2, 3]}


class TestErrorDetail:
    def test_basic(self):
        ed = ErrorDetail(code="TEST", message="hello")
        assert ed.code == "TEST"
        assert ed.message == "hello"


class TestErrorResponse:
    def test_basic(self):
        er = ErrorResponse(error=ErrorDetail(code="ERR", message="fail"))
        assert er.error.code == "ERR"
        assert er.error.message == "fail"

    def test_serialization(self):
        er = ErrorResponse(error=ErrorDetail(code="ERR", message="fail"))
        d = er.model_dump(mode="json")
        assert d == {
            "error": {"code": "ERR", "message": "fail", "correlation_id": None, "details": {}}
        }

    def test_json_string(self):
        er = ErrorResponse(error=ErrorDetail(code="ERR", message="fail"))
        j = er.model_dump_json()
        assert '"code"' in j
        assert '"message"' in j


class TestPaginationMeta:
    def test_with_cursor(self):
        m = PaginationMeta(cursor="abc", total_count=42)
        assert m.cursor == "abc"
        assert m.total_count == 42

    def test_without_cursor(self):
        m = PaginationMeta(total_count=10)
        assert m.cursor is None
        assert m.total_count == 10


class TestPaginatedResponse:
    def test_basic(self):
        r = PaginatedResponse(
            data=[{"id": 1}],
            meta=PaginationMeta(cursor=None, total_count=1),
        )
        assert len(r.data) == 1
        assert r.meta.total_count == 1

    def test_serialization(self):
        r = PaginatedResponse(
            data=[],
            meta=PaginationMeta(cursor="next", total_count=0),
        )
        d = r.model_dump(mode="json")
        assert d["meta"]["cursor"] == "next"
        assert d["meta"]["total_count"] == 0
