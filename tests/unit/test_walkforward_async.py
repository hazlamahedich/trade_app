"""Unit tests for InProcessTaskRunner, async walk-forward runner, and SSE events."""

from __future__ import annotations

import asyncio
import json

import numpy as np
import pandas as pd
import pytest

from trade_advisor.backtest.walkforward.async_runner import async_run_walkforward
from trade_advisor.backtest.walkforward.engine import (
    WalkForwardConfig,
    walk_forward,
)
from trade_advisor.infra.tasks import (
    BackgroundTask,
    InProcessTaskRunner,
    TaskStatus,
)
from trade_advisor.web.sse import (
    WalkForwardCancelledEvent,
    WalkForwardCompletedEvent,
    WalkForwardProgressEvent,
)


def _make_ohlcv(n: int = 500, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2020-01-01", periods=n, freq="B", tz="UTC")
    close = 100.0 + np.cumsum(rng.standard_normal(n) * 0.5)
    high = close + np.abs(rng.standard_normal(n) * 0.3)
    low = close - np.abs(rng.standard_normal(n) * 0.3)
    opn = close + rng.standard_normal(n) * 0.2
    volume = np.abs(rng.standard_normal(n) * 1_000_000) + 100_000
    return pd.DataFrame(
        {
            "timestamp": dates,
            "open": opn,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


def _wf_config() -> WalkForwardConfig:
    return WalkForwardConfig(
        mode="rolling",
        is_bars=60,
        oos_bars=20,
        strategy_params={"fast": 20, "slow": 50},
    )


class TestInProcessTaskRunnerSubmit:
    async def test_submit_returns_run_id(self):
        runner = InProcessTaskRunner()
        results = []

        async def _handler(task, *, on_progress=None, cancel_check=None):
            results.append(task.run_id)

        task = BackgroundTask(task_type="test", run_id="r1")
        run_id = await runner.submit(task, handler=_handler)
        assert run_id == "r1"
        await asyncio.sleep(0.1)
        assert "r1" in results

    async def test_submit_status_transitions(self):
        runner = InProcessTaskRunner()

        async def _handler(task, *, on_progress=None, cancel_check=None):
            await asyncio.sleep(0.05)

        task = BackgroundTask(task_type="test", run_id="r2")
        await runner.submit(task, handler=_handler)
        await asyncio.sleep(0.2)
        handle = await runner.status("r2")
        assert handle.status == TaskStatus.COMPLETED
        assert handle.completed_at is not None

    async def test_status_raises_for_unknown(self):
        runner = InProcessTaskRunner()
        with pytest.raises(KeyError):
            await runner.status("nonexistent")


class TestInProcessTaskRunnerCancel:
    async def test_cancel_sets_cancelled_status(self):
        runner = InProcessTaskRunner()

        async def _handler(task, *, on_progress=None, cancel_check=None):
            for _ in range(100):
                await asyncio.sleep(0.01)
                if cancel_check and cancel_check():
                    return

        task = BackgroundTask(task_type="test", run_id="r3")
        await runner.submit(task, handler=_handler)
        await asyncio.sleep(0.05)
        await runner.cancel("r3")
        await asyncio.sleep(0.1)
        handle = await runner.status("r3")
        assert handle.status == TaskStatus.CANCELLED


class TestAsyncRunWalkforward:
    async def test_fires_progress_per_window(self):
        ohlcv = _make_ohlcv()
        config = _wf_config()
        events: list[WalkForwardProgressEvent] = []

        def on_progress(event: WalkForwardProgressEvent) -> None:
            events.append(event)

        result = await async_run_walkforward(ohlcv, config, on_progress=on_progress, run_id="test")
        assert result.n_windows > 0
        assert len(events) == result.n_windows

    async def test_progress_ordered_by_window_idx(self):
        ohlcv = _make_ohlcv()
        config = _wf_config()
        events: list[WalkForwardProgressEvent] = []

        def on_progress(event: WalkForwardProgressEvent) -> None:
            events.append(event)

        await async_run_walkforward(ohlcv, config, on_progress=on_progress, run_id="test")
        idxs = [e.window_idx for e in events]
        assert idxs == sorted(idxs)
        assert idxs == list(range(len(idxs)))

    async def test_cancel_stops_processing(self):
        ohlcv = _make_ohlcv(n=500)
        config = _wf_config()
        events: list[WalkForwardProgressEvent] = []
        cancel_flag = False

        def on_progress(event: WalkForwardProgressEvent) -> None:
            events.append(event)

        def cancel_check() -> bool:
            return cancel_flag

        async def _run():
            nonlocal cancel_flag
            await async_run_walkforward(
                ohlcv,
                config,
                on_progress=on_progress,
                cancel_check=cancel_check,
                run_id="test",
            )

        task = asyncio.create_task(_run())
        await asyncio.sleep(0.1)
        cancel_flag = True
        await asyncio.sleep(0.1)
        await task
        assert len(events) < config.is_bars + config.oos_bars

    async def test_result_matches_sync_engine(self):
        ohlcv = _make_ohlcv()
        config = _wf_config()

        sync_result = walk_forward(ohlcv, config)
        async_result = await async_run_walkforward(ohlcv, config, run_id="test")

        assert sync_result.n_windows == async_result.n_windows
        assert sync_result.discarded_bars == async_result.discarded_bars


class TestSSEEventSerialization:
    def test_progress_event_json_round_trip(self):
        evt = WalkForwardProgressEvent(
            run_id="test",
            timestamp="2026-01-01T00:00:00Z",
            window_idx=0,
            total_windows=6,
            is_sharpe=1.2,
            oos_sharpe=0.8,
            oos_return=0.05,
            status="OK",
        )
        data = json.loads(evt.model_dump_json())
        assert data["event_type"] == "wf_progress"
        restored = WalkForwardProgressEvent.model_validate(data)
        assert restored == evt

    def test_completed_event_json_round_trip(self):
        evt = WalkForwardCompletedEvent(
            run_id="test",
            timestamp="2026-01-01T00:00:00Z",
            n_windows=6,
            discarded_bars=12,
        )
        data = json.loads(evt.model_dump_json())
        assert data["event_type"] == "wf_completed"
        restored = WalkForwardCompletedEvent.model_validate(data)
        assert restored == evt

    def test_cancelled_event_json_round_trip(self):
        evt = WalkForwardCancelledEvent(
            run_id="test",
            timestamp="2026-01-01T00:00:00Z",
            reason="User requested",
        )
        data = json.loads(evt.model_dump_json())
        assert data["event_type"] == "wf_cancelled"
        restored = WalkForwardCancelledEvent.model_validate(data)
        assert restored == evt
