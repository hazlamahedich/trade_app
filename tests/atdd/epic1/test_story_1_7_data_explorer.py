"""ATDD red-phase: Story 1.7 — Data Explorer Web Page.

All tests are SKIPPED (TDD red phase). Remove when implementing Story 1.7.
"""
from __future__ import annotations

import pytest


class TestStory17DataExplorer:
    """Story 1.7: FastAPI Data Explorer page with HTMX."""

    @pytest.mark.skip(reason="ATDD red phase — Story 1.7 not implemented")
    def test_data_explorer_route_exists(self):
        from trade_advisor.web.routes.data import router

        assert router is not None

    @pytest.mark.skip(reason="ATDD red phase — Story 1.7 not implemented")
    def test_data_explorer_returns_html(self):
        from fastapi.testclient import TestClient

        from trade_advisor.main import app

        client = TestClient(app)
        response = client.get("/data/explorer")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    @pytest.mark.skip(reason="ATDD red phase — Story 1.7 not implemented")
    def test_cached_symbols_listed_with_metadata(self):
        from fastapi.testclient import TestClient

        from trade_advisor.main import app

        client = TestClient(app)
        response = client.get("/api/data/symbols")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if data:
            symbol_entry = data[0]
            assert "symbol" in symbol_entry
            assert "date_range" in symbol_entry or "start_date" in symbol_entry
            assert "bar_count" in symbol_entry
            assert "last_updated" in symbol_entry

    @pytest.mark.skip(reason="ATDD red phase — Story 1.7 not implemented")
    def test_symbol_detail_paginated_table(self):
        from fastapi.testclient import TestClient

        from trade_advisor.main import app

        client = TestClient(app)
        response = client.get("/api/data/symbols/SPY/bars?page=1&per_page=50")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "meta" in data
        assert data["meta"]["page"] == 1

    @pytest.mark.skip(reason="ATDD red phase — Story 1.7 not implemented")
    def test_anomaly_flags_visible_with_severity(self):
        from fastapi.testclient import TestClient

        from trade_advisor.main import app

        client = TestClient(app)
        response = client.get("/api/data/symbols/SPY/anomalies")
        assert response.status_code == 200
        data = response.json()
        if data:
            assert "severity" in data[0]

    @pytest.mark.skip(reason="ATDD red phase — Story 1.7 not implemented")
    def test_design_tokens_as_css_custom_properties(self):
        from pathlib import Path

        project_root = Path(__file__).resolve().parents[4]
        css_files = list((project_root / "src" / "trade_advisor" / "web" / "static").rglob("*.css"))
        if not css_files:
            pytest.skip("CSS files not created yet")
        for css_file in css_files:
            content = css_file.read_text()
            if "--" in content:
                assert "--color-healthy" in content or "--semantic" in content

    @pytest.mark.skip(reason="ATDD red phase — Story 1.7 not implemented")
    def test_first_launch_spy_prefetch(self):
        from fastapi.testclient import TestClient

        from trade_advisor.main import app

        client = TestClient(app)
        response = client.get("/api/data/first-launch")
        assert response.status_code == 200
        data = response.json()
        assert data.get("message") or data.get("welcome")
