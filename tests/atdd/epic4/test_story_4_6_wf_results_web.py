"""ATDD: Story 4.6 — Walk-Forward Results Web Page.

Tests assert the EXPECTED end-state for Story 4.6:
dedicated WF results page, API contract, WFE/DSR badges, equity curve,
per-window breakdown, and error handling.
"""

from __future__ import annotations

import pytest


class TestStory46WFResultsPage:
    """Story 4.6: Walk-forward results web page with WFE badge."""

    @pytest.mark.test_id("4.6-ATDD-001")
    @pytest.mark.p0
    async def test_wf_results_page_returns_200(self, wf_app_client):
        # Given: a completed walk-forward run seeded in the DB
        # When: navigating to the WF Results detail page
        response = await wf_app_client.get("/walkforward/run_wf_001")
        # Then: the page returns 200 with the HTMX/React shell
        assert response.status_code == 200
        html = response.text
        assert "Walk-Forward" in html

    @pytest.mark.test_id("4.6-ATDD-002")
    @pytest.mark.p0
    async def test_wf_results_api_returns_window_data(self, wf_app_client):
        # Given: a completed walk-forward run with 5 windows in the DB
        # When: requesting the WF results API
        response = await wf_app_client.get("/api/walkforward/run_wf_001")
        # Then: the API returns window breakdown with WFResultResponse shape
        assert response.status_code == 200
        data = response.json()
        assert "windows" in data
        assert isinstance(data["windows"], list)
        assert len(data["windows"]) == 5

    @pytest.mark.test_id("4.6-ATDD-003")
    @pytest.mark.p0
    async def test_api_returns_wfe_and_status(self, wf_app_client):
        # Given: a walk-forward result with WFE computed
        # When: requesting the WF results API
        response = await wf_app_client.get("/api/walkforward/run_wf_001")
        # Then: WFE value and semantic status are returned
        assert response.status_code == 200
        data = response.json()
        assert "wfe" in data
        assert "wfe_status" in data
        assert isinstance(data["wfe"], float)
        assert data["wfe_status"] in ("healthy", "caution", "unreliable")

    @pytest.mark.test_id("4.6-ATDD-004")
    @pytest.mark.p1
    async def test_api_returns_per_window_breakdown(self, wf_app_client):
        # Given: a walk-forward result with multiple windows
        # When: requesting the WF results API
        response = await wf_app_client.get("/api/walkforward/run_wf_001")
        # Then: per-window IS/OOS metrics and parameter drift data are present
        assert response.status_code == 200
        data = response.json()
        windows = data["windows"]
        assert len(windows) > 0
        window = windows[0]
        assert "is_sharpe" in window
        assert "oos_sharpe" in window
        assert "is_return" in window
        assert "oos_return" in window
        assert "params" in window
        assert isinstance(window["params"], dict)
        assert "fast" in window["params"]

    @pytest.mark.test_id("4.6-ATDD-005")
    @pytest.mark.p1
    async def test_page_contains_oos_equity_curve_island(self, wf_app_client):
        # Given: a completed walk-forward validation
        # When: loading the WF results detail page
        response = await wf_app_client.get("/walkforward/run_wf_001")
        # Then: page contains the Preact island for the equity curve chart
        assert response.status_code == 200
        html = response.text
        assert 'data-island="walkForwardChart"' in html
        assert "run_wf_001" in html

    @pytest.mark.test_id("4.6-ATDD-006")
    @pytest.mark.p1
    async def test_api_returns_equity_and_baseline_curves(self, wf_app_client):
        # Given: a completed walk-forward run with stitched equity data
        # When: requesting the WF results API
        response = await wf_app_client.get("/api/walkforward/run_wf_001")
        # Then: equity and baseline curves are present in the response
        assert response.status_code == 200
        data = response.json()
        assert "equity" in data
        assert "baseline" in data
        assert isinstance(data["equity"], list)
        assert isinstance(data["baseline"], list)

    @pytest.mark.test_id("4.6-ATDD-007")
    @pytest.mark.p1
    async def test_api_returns_diagnostics_with_dsr(self, wf_app_client):
        # Given: a walk-forward result with DSR from Story 4.5
        # When: requesting the WF results API
        response = await wf_app_client.get("/api/walkforward/run_wf_001")
        # Then: diagnostics block includes DSR and risk-adjusted WFE
        assert response.status_code == 200
        data = response.json()
        assert "diagnostics" in data
        diag = data["diagnostics"]
        assert "dsr" in diag
        assert "dsr_significant" in diag
        assert "risk_adj_wfe" in diag

    @pytest.mark.test_id("4.6-ATDD-008")
    @pytest.mark.p2
    async def test_api_returns_regime_variance(self, wf_app_client):
        # Given: a walk-forward result with regime variance computed
        # When: requesting the WF results API
        response = await wf_app_client.get("/api/walkforward/run_wf_001")
        # Then: regime variance indicator is present
        assert response.status_code == 200
        data = response.json()
        assert "regime_variance" in data
        assert isinstance(data["regime_variance"], float)

    @pytest.mark.test_id("4.6-ATDD-009")
    @pytest.mark.p2
    async def test_nonexistent_run_returns_404(self, wf_app_client):
        # Given: a run ID that doesn't exist in the DB
        # When: requesting WF results API for non-existent run
        response = await wf_app_client.get("/api/walkforward/nonexistent_run")
        # Then: 404 is returned
        assert response.status_code == 404

    @pytest.mark.test_id("4.6-ATDD-010")
    @pytest.mark.p0
    async def test_wf_results_list_page(self, wf_app_client):
        # Given: the application is running
        # When: navigating to /walkforward (list view, no run_id)
        response = await wf_app_client.get("/walkforward")
        # Then: the list/start page returns 200
        assert response.status_code == 200
        html = response.text
        assert "Walk-Forward" in html

    @pytest.mark.test_id("4.6-ATDD-011")
    @pytest.mark.p1
    async def test_page_contains_window_breakdown_island(self, wf_app_client):
        # Given: a completed walk-forward validation
        # When: loading the WF results detail page
        response = await wf_app_client.get("/walkforward/run_wf_001")
        # Then: page contains the Preact island for window table
        assert response.status_code == 200
        html = response.text
        assert 'data-island="windowTable"' in html

    @pytest.mark.test_id("4.6-ATDD-012")
    @pytest.mark.p1
    async def test_page_contains_audit_mode_toggle(self, wf_app_client):
        # Given: a completed walk-forward validation (AC-7)
        # When: loading the WF results detail page
        response = await wf_app_client.get("/walkforward/run_wf_001")
        # Then: page contains the Quant Audit Mode toggle
        assert response.status_code == 200
        html = response.text
        assert "audit-mode" in html.lower() or "audit" in html.lower()
