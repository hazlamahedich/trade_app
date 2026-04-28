"""ATDD red-phase: Story 2.9 — Strategy Lab & Backtest Viewer Web Pages.

Tests assert the expected end-state AFTER full Story 2.9 implementation.
All tests are SKIPPED (TDD red phase).

Remove @pytest.mark.skip when implementing Story 2.9.
"""

from __future__ import annotations

import pytest


class TestStory29StrategyLabWebPage:
    """Story 2.9: Strategy Lab page for configuring and running backtests."""

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.9 not yet implemented")
    async def test_strategy_lab_page_exists(self, async_client_with_data):
        response = await async_client_with_data.get("/strategy-lab")
        assert response.status_code == 200

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.9 not yet implemented")
    async def test_strategy_lab_shows_strategy_types(self, async_client_with_data):
        response = await async_client_with_data.get("/strategy-lab")
        assert "sma_cross" in response.text or "SMA" in response.text

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.9 not yet implemented")
    async def test_strategy_lab_configure_parameters(self, async_client_with_data):
        response = await async_client_with_data.get("/strategy-lab")
        assert "fast" in response.text.lower() or "lookback" in response.text.lower()

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.9 not yet implemented")
    async def test_strategy_lab_select_engine_mode(self, async_client_with_data):
        response = await async_client_with_data.get("/strategy-lab")
        assert "vectorized" in response.text.lower() or "event" in response.text.lower()

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.9 not yet implemented")
    async def test_strategy_lab_configure_cost_model(self, async_client_with_data):
        response = await async_client_with_data.get("/strategy-lab")
        assert "commission" in response.text.lower() or "cost" in response.text.lower()

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.9 not yet implemented")
    async def test_run_backtest_submits_via_htmx(self, async_client_with_data):
        response = await async_client_with_data.post(
            "/api/backtest/run",
            json={
                "strategy": "sma_cross",
                "params": {"fast": 20, "slow": 50},
                "symbol": "TEST",
                "interval": "1d",
            },
        )
        assert response.status_code in (200, 202)


class TestStory29BacktestViewer:
    """Story 2.9: Backtest Viewer page with results display."""

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.9 not yet implemented")
    async def test_backtest_viewer_page_exists(self, async_client_with_data):
        response = await async_client_with_data.get("/backtest-viewer")
        assert response.status_code == 200

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.9 not yet implemented")
    async def test_backtest_viewer_shows_metrics(self, async_client_with_data):
        response = await async_client_with_data.get("/backtest-viewer")
        assert "sharpe" in response.text.lower() or "return" in response.text.lower()

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.9 not yet implemented")
    async def test_backtest_viewer_equity_curve_render(self, async_client_with_data):
        response = await async_client_with_data.get("/backtest-viewer")
        assert "equity" in response.text.lower() or "chart" in response.text.lower()

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.9 not yet implemented")
    async def test_sse_progress_streaming(self, async_client_with_data):
        response = await async_client_with_data.get(
            "/api/backtest/stream",
            params={"strategy": "sma_cross", "fast": 20, "slow": 50},
        )
        assert response.status_code in (200, 202)

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.9 not yet implemented")
    async def test_page_load_under_3_seconds(self, async_client_with_data):
        import time

        start = time.monotonic()
        await async_client_with_data.get("/strategy-lab")
        elapsed = time.monotonic() - start
        assert elapsed < 3.0
