"""Tests for web/routes/data.py — Data Explorer endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from trade_advisor.core.errors import DataError
from trade_advisor.infra.db import DatabaseManager


def _create_test_app(mock_db: AsyncMock) -> FastAPI:
    application = FastAPI()

    async def override_get_db():
        yield mock_db

    from trade_advisor.main import get_db
    from trade_advisor.web.routes.data import router as data_router

    application.dependency_overrides[get_db] = override_get_db
    application.include_router(data_router)
    return application


@pytest.fixture
def mock_db():
    return AsyncMock(spec=DatabaseManager)


@pytest.fixture
def client(mock_db):
    application = _create_test_app(mock_db)
    return TestClient(application)


class TestDataExplorer:
    def test_empty_data_explorer(self, client, mock_db):
        mock_db.read = AsyncMock(return_value=[[0]])
        resp = client.get("/data")
        assert resp.status_code == 200

    def test_data_explorer_with_symbols(self, client, mock_db):
        mock_db.read = AsyncMock(
            side_effect=[
                [[5]],
                [
                    (
                        "SPY",
                        "1d",
                        1000,
                        datetime(2020, 1, 1, tzinfo=UTC),
                        datetime(2024, 1, 1, tzinfo=UTC),
                        datetime(2024, 6, 1, tzinfo=UTC),
                        False,
                        True,
                    )
                ],
            ]
        )
        resp = client.get("/data")
        assert resp.status_code == 200
        assert "SPY" in resp.text

    def test_data_explorer_htmx(self, client, mock_db):
        mock_db.read = AsyncMock(return_value=[[0]])
        resp = client.get("/data", headers={"HX-Request": "true"})
        assert resp.status_code == 200

    def test_data_explorer_db_error(self, client, mock_db):
        mock_db.read = AsyncMock(side_effect=DataError("connection failed"))
        resp = client.get("/data")
        assert resp.status_code == 200

    def test_data_explorer_unexpected_error(self, client, mock_db):
        mock_db.read = AsyncMock(side_effect=RuntimeError("unexpected"))
        resp = client.get("/data")
        assert resp.status_code == 200


class TestSymbolDetail:
    def test_symbol_detail(self, client, mock_db):
        mock_db.read = AsyncMock(
            side_effect=[
                [[5]],
                [
                    (
                        datetime(2024, 1, 1, tzinfo=UTC),
                        100.0,
                        101.0,
                        99.0,
                        100.5,
                        100.5,
                        1000000,
                        "yahoo",
                        1.0,
                        1.0,
                    ),
                ],
                [],
            ]
        )
        resp = client.get("/data/symbol/SPY")
        assert resp.status_code == 200

    def test_symbol_detail_no_data(self, client, mock_db):
        mock_db.read = AsyncMock(return_value=[[0]])
        resp = client.get("/data/symbol/NOEXIST")
        assert resp.status_code == 200

    def test_symbol_detail_pagination(self, client, mock_db):
        mock_db.read = AsyncMock(
            side_effect=[
                [[100]],
                [],
            ]
        )
        resp = client.get("/data/symbol/SPY?page=2&size=10")
        assert resp.status_code == 200

    def test_symbol_detail_with_interval(self, client, mock_db):
        mock_db.read = AsyncMock(return_value=[[0]])
        resp = client.get("/data/symbol/SPY?interval=1h")
        assert resp.status_code == 200

    def test_symbol_detail_db_read_error(self, client, mock_db):
        mock_db.read = AsyncMock(side_effect=[DataError("read error")])
        resp = client.get("/data/symbol/SPY")
        assert resp.status_code == 200


class TestFetchSymbol:
    def test_fetch_invalid_symbol(self, client, mock_db):
        resp = client.post("/data/fetch", data={"symbol": "BAD!SYMBOL@#"})
        assert resp.status_code == 200

    def test_fetch_too_long_symbol(self, client, mock_db):
        resp = client.post("/data/fetch", data={"symbol": "A" * 25})
        assert resp.status_code == 200


class TestHelperFunctions:
    def test_format_ts_utc_none(self):
        from trade_advisor.web.routes.data import _format_ts_utc

        assert _format_ts_utc(None) == "N/A"

    def test_format_ts_utc_string(self):
        from trade_advisor.web.routes.data import _format_ts_utc

        result = _format_ts_utc("2024-01-01T00:00:00+00:00")
        assert "2024-01-01" in result

    def test_format_ts_utc_datetime(self):
        from trade_advisor.web.routes.data import _format_ts_utc

        result = _format_ts_utc(datetime(2024, 6, 15, 12, 30, tzinfo=UTC))
        assert "2024-06-15" in result

    def test_format_ts_utc_naive_datetime(self):
        from trade_advisor.web.routes.data import _format_ts_utc

        result = _format_ts_utc(datetime(2024, 6, 15, 12, 30))
        assert "2024-06-15" in result

    def test_format_ts_utc_other_type(self):
        from trade_advisor.web.routes.data import _format_ts_utc

        result = _format_ts_utc(42)
        assert result == "42"

    def test_adj_label_null_adj(self):
        from trade_advisor.web.routes.data import _adj_label

        assert _adj_label(True, False) == "Raw (unadjusted)"

    def test_adj_label_adjusted(self):
        from trade_advisor.web.routes.data import _adj_label

        assert _adj_label(False, True) == "Adjusted"

    def test_adj_label_no_diff(self):
        from trade_advisor.web.routes.data import _adj_label

        assert _adj_label(False, False) == "Adjusted (no diff)"

    def test_is_htmx(self):
        from trade_advisor.web.routes.data import _is_htmx

        mock_request = MagicMock()
        mock_request.headers.get.return_value = "true"
        assert _is_htmx(mock_request) is True

        mock_request.headers.get.return_value = None
        assert _is_htmx(mock_request) is False
