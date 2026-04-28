"""ATDD red-phase: Story 2.11 — Remix Button & Auto-Suggested Variants.

Tests assert the expected end-state AFTER full Story 2.11 implementation.
All tests are SKIPPED (TDD red phase).

Remove @pytest.mark.skip when implementing Story 2.11.
"""

from __future__ import annotations

import pytest


class TestStory211RemixButton:
    """Story 2.11: Fork any backtest result with one click."""

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.11 not yet implemented")
    async def test_remix_creates_preconfigured_copy(self, async_client_with_data):
        response = await async_client_with_data.post(
            "/api/backtest/run",
            json={
                "strategy": "sma_cross",
                "params": {"fast": 20, "slow": 50},
                "symbol": "TEST",
            },
        )
        run_id = response.json().get("run_id")
        remix_resp = await async_client_with_data.post(
            f"/api/backtest/{run_id}/remix",
        )
        assert remix_resp.status_code in (200, 201)
        data = remix_resp.json()
        assert data["params"]["fast"] == 20
        assert data["params"]["slow"] == 50

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.11 not yet implemented")
    async def test_remix_auto_suggests_variants(self, async_client_with_data):
        response = await async_client_with_data.post(
            "/api/backtest/run",
            json={
                "strategy": "sma_cross",
                "params": {"fast": 20, "slow": 50},
                "symbol": "TEST",
            },
        )
        run_id = response.json().get("run_id")
        suggestions = await async_client_with_data.get(
            f"/api/backtest/{run_id}/suggestions",
        )
        assert suggestions.status_code == 200
        data = suggestions.json()
        assert len(data.get("variants", [])) >= 2

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.11 not yet implemented")
    async def test_remix_event_tracked(self, async_client_with_data):
        response = await async_client_with_data.post(
            "/api/backtest/run",
            json={
                "strategy": "sma_cross",
                "params": {"fast": 20, "slow": 50},
                "symbol": "TEST",
            },
        )
        run_id = response.json().get("run_id")
        await async_client_with_data.post(f"/api/backtest/{run_id}/remix")
        events = await async_client_with_data.get("/api/events/remix")
        assert events.status_code == 200

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.11 not yet implemented")
    async def test_remix_original_never_modified(self, async_client_with_data):
        response = await async_client_with_data.post(
            "/api/backtest/run",
            json={
                "strategy": "sma_cross",
                "params": {"fast": 20, "slow": 50},
                "symbol": "TEST",
            },
        )
        run_id = response.json().get("run_id")
        original = await async_client_with_data.get(f"/api/backtest/{run_id}")
        original_data = original.json()

        await async_client_with_data.post(
            f"/api/backtest/{run_id}/remix",
            json={"params": {"fast": 14}},
        )
        after = await async_client_with_data.get(f"/api/backtest/{run_id}")
        assert after.json() == original_data

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.11 not yet implemented")
    async def test_undo_available_within_10_seconds(self, async_client_with_data):
        response = await async_client_with_data.post(
            "/api/backtest/run",
            json={
                "strategy": "sma_cross",
                "params": {"fast": 20, "slow": 50},
                "symbol": "TEST",
            },
        )
        run_id = response.json().get("run_id")
        remix = await async_client_with_data.post(f"/api/backtest/{run_id}/remix")
        remix_id = remix.json().get("run_id")
        undo = await async_client_with_data.delete(f"/api/backtest/{remix_id}")
        assert undo.status_code in (200, 204)
