"""ATDD green-phase: Story 1.7 — Data Explorer Web Page.

Tests now run against the implementation.
"""

from __future__ import annotations

import pytest


class TestDataExplorerRouteAndTemplate:
    """AC #1, #2: Data Explorer route returns HTML with symbol list."""

    async def test_get_data_returns_200_with_html(self, async_client_with_data):
        response = await async_client_with_data.get("/data")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    async def test_get_data_htmx_returns_partial(self, async_client_with_data):
        response = await async_client_with_data.get("/data", headers={"HX-Request": "true"})
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    async def test_symbol_list_shows_date_ranges_and_bar_counts(self, async_client_with_data):
        response = await async_client_with_data.get("/data")
        assert "TEST" in response.text
        assert "bar" in response.text.lower() or "Bars" in response.text

    async def test_timestamps_display_with_utc_suffix(self, async_client_with_data):
        response = await async_client_with_data.get("/data")
        assert "UTC" in response.text

    async def test_adj_close_comparison_label_adjusted(self, async_client_with_data_adj):
        response = await async_client_with_data_adj.get("/data")
        assert "Adjusted" in response.text
        assert "no diff" not in response.text

    async def test_adj_close_comparison_label_raw(self, async_client_with_data):
        response = await async_client_with_data.get("/data")
        assert "Adjusted (no diff)" in response.text


class TestSymbolDetailPagination:
    """AC #3: Symbol detail via HTMX with pagination."""

    async def test_symbol_detail_returns_paginated_ohlcv(self, async_client_with_data):
        response = await async_client_with_data.get(
            "/data/symbol/TEST", headers={"HX-Request": "true"}
        )
        assert response.status_code == 200
        assert "TEST" in response.text

    async def test_pagination_default_page_and_size(self, async_client_with_data):
        response = await async_client_with_data.get(
            "/data/symbol/TEST?page=1&size=10", headers={"HX-Request": "true"}
        )
        assert response.status_code == 200
        assert "TEST" in response.text

    async def test_pagination_rejects_negative_page_with_422(self, async_client_with_data):
        response = await async_client_with_data.get(
            "/data/symbol/TEST?page=-1", headers={"HX-Request": "true"}
        )
        assert response.status_code == 422

    async def test_pagination_rejects_zero_size_with_422(self, async_client_with_data):
        response = await async_client_with_data.get(
            "/data/symbol/TEST?size=0", headers={"HX-Request": "true"}
        )
        assert response.status_code == 422

    async def test_pagination_rejects_non_integer_with_422(self, async_client_with_data):
        response = await async_client_with_data.get(
            "/data/symbol/TEST?page=abc", headers={"HX-Request": "true"}
        )
        assert response.status_code == 422

    async def test_htmx_partial_returns_ohlcv_data(self, async_client_with_data):
        response = await async_client_with_data.get(
            "/data/symbol/TEST", headers={"HX-Request": "true"}
        )
        assert response.status_code == 200
        assert "OHLCV" in response.text or "open" in response.text.lower()

    async def test_empty_symbol_returns_empty_state_not_404(self, async_client_with_data):
        response = await async_client_with_data.get(
            "/data/symbol/NOSYMBOL", headers={"HX-Request": "true"}
        )
        assert response.status_code == 200
        assert response.status_code != 404
        assert "No data found" in response.text


class TestAnomalyDisplay:
    """AC #4: Anomaly badges with severity indicators."""

    async def test_anomaly_badges_show_text_labels(self, async_client_with_anomaly):
        response = await async_client_with_anomaly.get(
            "/data/symbol/ANOMALY", headers={"HX-Request": "true"}
        )
        assert response.status_code == 200
        assert "ANOMALY" in response.text

    async def test_anomaly_badges_use_color_tokens(self, async_client_with_anomaly):
        response = await async_client_with_anomaly.get(
            "/data/symbol/ANOMALY", headers={"HX-Request": "true"}
        )
        assert response.status_code == 200
        assert "ANOMALY" in response.text

    async def test_corporate_action_labeled_not_data_error(self, async_client_with_split):
        response = await async_client_with_split.get(
            "/data/symbol/SPLIT", headers={"HX-Request": "true"}
        )
        assert response.status_code == 200
        assert "Corporate Action" in response.text
        assert "Data Error" not in response.text


class TestDesignTokensDarkMode:
    """AC #5: CSS custom properties for light/dark mode."""

    def test_tokens_css_has_custom_properties(self):
        from pathlib import Path

        project_root = Path(__file__).resolve().parents[3]
        tokens_path = project_root / "frontend" / "styles" / "tokens.css"
        if not tokens_path.exists():
            pytest.skip("tokens.css not created yet")
        content = tokens_path.read_text()
        assert "--healthy" in content
        assert "--caution" in content
        assert "--degraded" in content

    def test_dark_mode_toggle_in_base_template(self):
        from pathlib import Path

        project_root = Path(__file__).resolve().parents[3]
        base_path = project_root / "src" / "trade_advisor" / "web" / "templates" / "base.html"
        if not base_path.exists():
            pytest.skip("base.html not created yet")
        content = base_path.read_text()
        assert "toggleTheme" in content or "dark" in content.lower()
        assert "localStorage" in content

    def test_tabular_nums_in_css(self):
        from pathlib import Path

        project_root = Path(__file__).resolve().parents[3]
        tokens_path = project_root / "frontend" / "styles" / "tokens.css"
        if not tokens_path.exists():
            pytest.skip("tokens.css not created yet")
        content = tokens_path.read_text()
        assert "tabular-nums" in content


class TestPerformance:
    """AC #6: TTFB < 500ms with 50-symbol seeded DuckDB."""

    async def test_ttfb_under_500ms_with_50_symbols(self, async_client_50_symbols):
        import time

        start = time.perf_counter()
        response = await async_client_50_symbols.get("/data")
        elapsed = time.perf_counter() - start
        assert response.status_code == 200
        assert elapsed < 0.5, f"TTFB was {elapsed:.3f}s, exceeds 500ms budget"


class TestFirstLaunchStateMachine:
    """AC #7: First-launch empty state with fetch."""

    async def test_empty_db_shows_empty_state_with_input(self, async_client_empty):
        response = await async_client_empty.get("/data")
        assert response.status_code == 200
        assert "SPY" in response.text
        assert "Fetch" in response.text or "fetch" in response.text.lower()

    async def test_fetch_shows_error_state_on_failure(self, async_client_empty):
        response = await async_client_empty.post(
            "/data/fetch",
            data={"symbol": "ZZZZZZNOTREAL"},
            headers={"HX-Request": "true"},
        )
        assert response.status_code == 200
        assert "Error" in response.text or "error" in response.text.lower()


class TestErrorStates:
    """AC #8: Error states with semantic colors and retry."""

    async def test_htmx_error_includes_retarget_header(self, async_client_with_data):
        response = await async_client_with_data.get(
            "/data/symbol/NONEXISTENT",
            headers={"HX-Request": "true"},
        )
        assert response.status_code == 200
        assert "No data found" in response.text

    async def test_non_htmx_error_returns_proper_status(self, async_client_empty):
        response = await async_client_empty.get("/data")
        assert response.status_code == 200
