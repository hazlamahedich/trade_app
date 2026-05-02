"""ATDD: Story 4.6 — Walk-Forward Results Web Page.

Tests assert the EXPECTED end-state for Story 4.6.
RED PHASE: These tests will fail until the WF Results web page is implemented.
"""

from __future__ import annotations

import pytest


class TestStory46WFResultsPage:
    """Story 4.6: Walk-forward results web page with WFE badge."""

    @pytest.mark.test_id("4.6-ATDD-001")
    @pytest.mark.p0
    async def test_wf_results_page_returns_200(self, wf_app_client):
        # Given: a completed walk-forward validation
        # When: navigating to the WF Results page
        response = await wf_app_client.get("/walkforward/run_wf_001")
        # Then: the page returns 200
        assert response.status_code == 200

    @pytest.mark.test_id("4.6-ATDD-002")
    @pytest.mark.p0
    async def test_wf_results_api_returns_window_data(self, wf_app_client):
        # Given: a completed walk-forward run
        # When: requesting the WF results API
        response = await wf_app_client.get("/api/walkforward/run_wf_001")
        # Then: window breakdown is returned
        assert response.status_code == 200
        data = response.json()
        assert "windows" in data or "n_windows" in data

    @pytest.mark.test_id("4.6-ATDD-003")
    @pytest.mark.p0
    async def test_api_returns_wfe_badge(self, wf_app_client):
        # Given: a walk-forward result with WFE computed
        # When: requesting the WF results API
        response = await wf_app_client.get("/api/walkforward/run_wf_001")
        # Then: WFE status is included with semantic color
        assert response.status_code == 200
        data = response.json()
        assert "wfe" in data or "wfe_status" in data

    @pytest.mark.test_id("4.6-ATDD-004")
    @pytest.mark.p1
    async def test_api_returns_per_window_breakdown(self, wf_app_client):
        # Given: a walk-forward result with multiple windows
        # When: requesting the WF results API
        response = await wf_app_client.get("/api/walkforward/run_wf_001")
        # Then: per-window IS/OOS metrics and parameter drift are shown
        assert response.status_code == 200
        data = response.json()
        if "windows" in data:
            assert len(data["windows"]) > 0
            window = data["windows"][0]
            assert "is_sharpe" in window or "is_metrics" in window

    @pytest.mark.test_id("4.6-ATDD-005")
    @pytest.mark.p1
    async def test_page_contains_oos_equity_curve(self, wf_app_client):
        # Given: a completed walk-forward validation
        # When: loading the WF results page
        response = await wf_app_client.get("/walkforward/run_wf_001")
        # Then: page contains OOS equity curve element
        assert response.status_code == 200
        content = response.text
        assert "equity" in content.lower() or "oos" in content.lower()

    @pytest.mark.test_id("4.6-ATDD-006")
    @pytest.mark.p2
    async def test_nonexistent_run_returns_404(self, wf_app_client):
        # Given: a run ID that doesn't exist
        # When: requesting WF results for non-existent run
        response = await wf_app_client.get("/api/walkforward/nonexistent_run")
        # Then: 404 is returned
        assert response.status_code == 404

    @pytest.mark.test_id("4.6-ATDD-007")
    @pytest.mark.p2
    async def test_wf_results_list_page(self, wf_app_client):
        # Given: multiple walk-forward runs
        # When: navigating to WF Results list
        response = await wf_app_client.get("/walkforward")
        # Then: list page returns 200
        assert response.status_code == 200
