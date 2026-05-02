"""ATDD: Story 4.1 — Walk-Forward Engine (Rolling & Anchored Modes).

Updated for Story 4.1a: Uses sync WalkForwardConfig + walk_forward() API.
Story 4.1b: SSE streaming tests (ATDD-010, ATDD-011).
"""

from __future__ import annotations

import json
import math

import pandas as pd
import pytest
from pydantic import ValidationError

from trade_advisor.backtest.walkforward.engine import (
    WalkForwardConfig,
    WalkForwardError,
    walk_forward,
)


class TestStory41WalkForwardEngine:
    """Story 4.1: Walk-forward validation in rolling and anchored modes."""

    @pytest.mark.test_id("4.1-ATDD-001")
    @pytest.mark.p0
    def test_rolling_mode_produces_windows(self, wf_ohlcv):
        cfg = WalkForwardConfig(
            mode="rolling",
            is_bars=60,
            oos_bars=20,
            strategy_params={"fast": 20, "slow": 50},
        )
        result = walk_forward(wf_ohlcv, cfg)
        assert result.n_windows > 0
        for window in result.windows:
            assert window.is_segment is not None
            assert window.oos_segment is not None
            assert len(window.is_segment) == 60
            assert len(window.oos_segment) == 20

    @pytest.mark.test_id("4.1-ATDD-002")
    @pytest.mark.p0
    def test_anchored_mode_expanding_window(self, wf_ohlcv):
        cfg = WalkForwardConfig(
            mode="anchored",
            is_bars=60,
            oos_bars=20,
            strategy_params={"fast": 20, "slow": 50},
        )
        result = walk_forward(wf_ohlcv, cfg)
        assert result.n_windows > 0
        is_lengths = [w.boundary.is_end - w.boundary.is_start for w in result.windows]
        for i in range(1, len(is_lengths)):
            assert is_lengths[i] >= is_lengths[i - 1]

    @pytest.mark.test_id("4.1-ATDD-003")
    @pytest.mark.p0
    def test_window_sizes_configurable(self, wf_ohlcv):
        cfg = WalkForwardConfig(
            mode="rolling",
            is_bars=40,
            oos_bars=10,
            strategy_params={"fast": 20, "slow": 50},
        )
        result = walk_forward(wf_ohlcv, cfg)
        for window in result.windows:
            assert len(window.is_segment) == 40
            assert len(window.oos_segment) == 10

    @pytest.mark.test_id("4.1-ATDD-004")
    @pytest.mark.p0
    def test_deterministic_with_same_seed(self, wf_ohlcv):
        cfg = WalkForwardConfig(
            mode="rolling",
            is_bars=60,
            oos_bars=20,
            seed=42,
            strategy_params={"fast": 20, "slow": 50},
        )
        result_a = walk_forward(wf_ohlcv, cfg)
        result_b = walk_forward(wf_ohlcv, cfg)
        assert result_a.n_windows == result_b.n_windows
        for wa, wb in zip(result_a.windows, result_b.windows, strict=True):
            assert wa.boundary == wb.boundary
            pd.testing.assert_series_equal(wa.oos_equity, wb.oos_equity)
            if math.isnan(wa.is_sharpe):
                assert math.isnan(wb.is_sharpe)
            else:
                assert wa.is_sharpe == wb.is_sharpe

    @pytest.mark.test_id("4.1-ATDD-005")
    @pytest.mark.p1
    def test_rolling_mode_fixed_width_windows(self, wf_ohlcv):
        cfg = WalkForwardConfig(
            mode="rolling",
            is_bars=60,
            oos_bars=20,
            strategy_params={"fast": 20, "slow": 50},
        )
        result = walk_forward(wf_ohlcv, cfg)
        is_lengths = [len(w.is_segment) for w in result.windows]
        assert len(set(is_lengths)) == 1

    @pytest.mark.test_id("4.1-ATDD-006")
    @pytest.mark.p1
    def test_no_overlapping_oos_segments(self, wf_ohlcv):
        cfg = WalkForwardConfig(
            mode="rolling",
            is_bars=60,
            oos_bars=20,
            strategy_params={"fast": 20, "slow": 50},
        )
        result = walk_forward(wf_ohlcv, cfg)
        for i in range(1, len(result.windows)):
            assert result.windows[i].boundary.oos_start > result.windows[i - 1].boundary.oos_end

    @pytest.mark.test_id("4.1-ATDD-007")
    @pytest.mark.p1
    def test_result_contains_window_metrics(self, wf_ohlcv):
        cfg = WalkForwardConfig(
            mode="rolling",
            is_bars=60,
            oos_bars=20,
            strategy_params={"fast": 20, "slow": 50},
        )
        result = walk_forward(wf_ohlcv, cfg)
        for window in result.windows:
            assert hasattr(window, "is_sharpe")
            assert hasattr(window, "oos_sharpe")
            assert hasattr(window, "is_return")
            assert hasattr(window, "oos_return")

    @pytest.mark.test_id("4.1-ATDD-008")
    @pytest.mark.p1
    def test_insufficient_data_raises_error(self, wf_ohlcv_short):
        cfg = WalkForwardConfig(mode="rolling", is_bars=200, oos_bars=50)
        with pytest.raises(WalkForwardError):
            walk_forward(wf_ohlcv_short, cfg)

    @pytest.mark.test_id("4.1-ATDD-009")
    @pytest.mark.p1
    def test_mode_validation_rejects_invalid(self):
        with pytest.raises(ValidationError):
            WalkForwardConfig(mode="invalid_mode", is_bars=60, oos_bars=20)


class TestStory41WalkForwardSSE:
    """Story 4.1b: SSE progress streaming for walk-forward runs."""

    @pytest.mark.test_id("4.1-ATDD-010")
    @pytest.mark.p1
    async def test_sse_streams_window_progress(self, wf_sse_client):
        response = await wf_sse_client.post(
            "/walkforward/run",
            data={
                "mode": "rolling",
                "is_bars": 60,
                "oos_bars": 20,
                "fast": 20,
                "slow": 50,
            },
        )
        assert response.status_code == 202
        run_id = response.json()["run_id"]

        events = await _collect_sse_events(wf_sse_client, run_id, timeout=15.0)

        progress_events = [e for e in events if e.get("event_type") == "wf_progress"]
        assert len(progress_events) > 0, "Expected at least one wf_progress event"

        completed_events = [e for e in events if e.get("event_type") == "wf_completed"]
        assert len(completed_events) >= 1, "Expected at least one wf_completed event"

    @pytest.mark.test_id("4.1-ATDD-011")
    @pytest.mark.p1
    async def test_sse_event_contains_window_metrics(self, wf_sse_client):
        response = await wf_sse_client.post(
            "/walkforward/run",
            data={
                "mode": "rolling",
                "is_bars": 60,
                "oos_bars": 20,
                "fast": 20,
                "slow": 50,
            },
        )
        assert response.status_code == 202
        run_id = response.json()["run_id"]

        events = await _collect_sse_events(wf_sse_client, run_id, timeout=15.0)

        progress_events = [e for e in events if e.get("event_type") == "wf_progress"]
        assert len(progress_events) > 0

        first = progress_events[0]
        assert "window_idx" in first
        assert "is_sharpe" in first
        assert "oos_sharpe" in first


async def _collect_sse_events(
    client,
    run_id: str,
    timeout: float = 10.0,
) -> list[dict]:
    events: list[dict] = []
    try:
        async with client.stream(
            "GET", f"/walkforward/run/{run_id}/stream", timeout=timeout
        ) as stream:
            async for line in stream.aiter_lines():
                if line.startswith("data:"):
                    payload = line[5:].strip()
                    if payload:
                        events.append(json.loads(payload))
                if any(
                    e.get("event_type") in ("wf_completed", "wf_cancelled", "error") for e in events
                ):
                    break
    except Exception:
        pass
    return events
