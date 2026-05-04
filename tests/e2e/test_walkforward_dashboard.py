from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from trade_advisor.backtest.walkforward.stitch import (
    ExtendedWalkforwardResult,
    WalkforwardDiagnostics,
)
from trade_advisor.main import app
from trade_advisor.web.routes.walkforward import _create_run

pytestmark = pytest.mark.e2e

client = TestClient(app)


class TestWalkForwardDashboard:
    @pytest.mark.test_id("4.6-E2E-001")
    @pytest.mark.p1
    def test_walkforward_dashboard_flow(self):
        run_id = "test_run_123"
        state = _create_run(run_id)

        # Mock result
        dates = pd.date_range("2026-01-01", periods=2, freq="D")
        state.result = ExtendedWalkforwardResult(
            stitched_equity=pd.Series([1.0, 1.1], index=dates),
            total_oos_return=0.1,
            total_is_return=0.2,
            wfe=0.8,
            wfe_status="healthy",
            wfe_per_fold=[0.8, 0.8],
            baseline_equity=pd.Series([1.0, 1.05], index=dates),
            expected_return_per_active_bar=0.01,
            n_active_bars_oos=2,
            diagnostics=WalkforwardDiagnostics(
                risk_adj_wfe=0.8, expected_value=0.01, dsr=0.05, dsr_significant=True, regime_variance=0.15
            ),
        )
        state.result.regime_variance = 0.15
        state.raw_result = None
        state.completed.set()

        # 1. Check the initial dashboard HTML load
        html_resp = client.get(f"/walkforward/{run_id}")
        assert html_resp.status_code == 200
        html = html_resp.text
        assert "Walk-Forward Validation" in html
        assert 'data-island="walkForwardChart"' in html
        assert 'data-island="windowTable"' in html

        # 2. Test that the results endpoint works and returns correct JSON structure
        results_resp = client.get(f"/api/walkforward/{run_id}")
        assert results_resp.status_code == 200
        json_data = results_resp.json()
        assert json_data["wfe"] == 0.8
        assert json_data["wfe_status"] == "healthy"
        assert json_data["diagnostics"]["dsr_significant"] is True
        assert json_data["regime_variance"] == 0.15
