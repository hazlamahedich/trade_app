"""Walk-forward validation web routes — async submission + SSE streaming."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse, StreamingResponse

from trade_advisor.backtest.walkforward.async_runner import async_run_walkforward
from trade_advisor.backtest.walkforward.engine import WalkForwardConfig
from trade_advisor.infra.tasks import BackgroundTask, InProcessTaskRunner
from trade_advisor.web.sse import (
    ErrorEvent,
    WalkForwardCancelledEvent,
    WalkForwardCompletedEvent,
    WalkForwardProgressEvent,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/walkforward")

_runner = InProcessTaskRunner()


@dataclass
class _RunState:
    events: list[Any] = field(default_factory=list)
    queues: list[asyncio.Queue[Any]] = field(default_factory=list)
    completed: asyncio.Event = field(default_factory=asyncio.Event)
    cancelled: bool = False
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


_runs: dict[str, _RunState] = {}


def _get_run(run_id: str) -> _RunState | None:
    return _runs.get(run_id)


def _create_run(run_id: str) -> _RunState:
    state = _RunState()
    _runs[run_id] = state
    return state


def _build_wf_handler(
    ohlcv_data: Any,
    run_id: str,
) -> Any:
    async def _handler(
        task: BackgroundTask,
        *,
        on_progress: Any | None = None,
        cancel_check: Any | None = None,
    ) -> None:
        cfg = WalkForwardConfig(**task.config)
        state = _get_run(run_id)
        if state is None:
            return

        def _emit(event: Any) -> None:
            state.events.append(event)
            for q in state.queues:
                q.put_nowait(event)

        def _on_progress(event: WalkForwardProgressEvent) -> None:
            if on_progress is not None:
                on_progress(event)
            _emit(event)

        try:
            result = await async_run_walkforward(
                ohlcv_data,
                cfg,
                on_progress=_on_progress,
                cancel_check=cancel_check,
                run_id=run_id,
            )

            if cancel_check and cancel_check():
                return

            completed = WalkForwardCompletedEvent(
                run_id=run_id,
                timestamp=datetime.now(UTC).isoformat(),
                n_windows=result.n_windows,
                discarded_bars=result.discarded_bars,
            )
            _emit(completed)
        except Exception:
            _emit(ErrorEvent(
                run_id=run_id,
                timestamp=datetime.now(UTC).isoformat(),
                detail="Walk-forward run failed",
            ))
        finally:
            state.completed.set()

    return _handler


@router.post("/run")
async def start_run(
    request: Request,
    mode: str = Form("rolling"),
    is_bars: int = Form(60),
    oos_bars: int = Form(20),
    gap_bars: int = Form(1),
    strategy_type: str = Form("sma"),
    fast: int = Form(20),
    slow: int = Form(50),
    seed: int = Form(42),
) -> JSONResponse:
    from trade_advisor.main import get_db

    db = await get_db(request)

    symbol = "SPY"
    interval = "1d"
    rows = await db.read(
        "SELECT timestamp, open, high, low, close, adj_close, volume "
        "FROM ohlcv_cache WHERE symbol = ? AND interval = ? ORDER BY timestamp ASC",
        (symbol, interval),
    )
    if not rows:
        return JSONResponse(
            {"error": f"No cached data for {symbol}/{interval}"},
            status_code=400,
        )

    import pandas as pd

    df = pd.DataFrame(
        rows, columns=["timestamp", "open", "high", "low", "close", "adj_close", "volume"]
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    ohlcv = df.sort_values("timestamp")

    run_id = uuid.uuid4().hex[:12]
    config = WalkForwardConfig(
        mode=mode,  # type: ignore[arg-type]
        is_bars=is_bars,
        oos_bars=oos_bars,
        gap_bars=gap_bars,
        seed=seed,
        strategy_type=strategy_type,
        strategy_params={"fast": fast, "slow": slow},
    )

    _create_run(run_id)

    handler = _build_wf_handler(ohlcv, run_id)

    task = BackgroundTask(
        task_type="walkforward",
        config=config.model_dump(),
        run_id=run_id,
    )

    try:
        await _runner.submit(task, handler=handler)
    except Exception:
        _runs.pop(run_id, None)
        raise

    return JSONResponse({"run_id": run_id}, status_code=202)


@router.get("/run/{run_id}/stream")
async def stream_progress(run_id: str) -> StreamingResponse:
    state = _get_run(run_id)
    if state is None:
        return StreamingResponse(
            _error_generator(f"Unknown run_id: {run_id}"),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    queue: asyncio.Queue[Any] = asyncio.Queue()

    async with state.lock:
        for event in state.events:
            queue.put_nowait(event)
        state.queues.append(queue)

    async def _event_generator() -> AsyncIterator[str]:
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                except TimeoutError:
                    yield ": heartbeat\n\n"
                    continue

                payload = event.model_dump(mode="json")
                event_name = f"ta:walkforward:{event.event_type.replace('wf_', '')}"
                yield f"event: {event_name}\ndata: {json.dumps(payload)}\n\n"

                if isinstance(
                    event, (WalkForwardCompletedEvent, WalkForwardCancelledEvent, ErrorEvent)
                ):
                    break
        except asyncio.CancelledError:
            pass
        finally:
            async with state.lock:
                if queue in state.queues:
                    state.queues.remove(queue)
                if not state.queues and state.completed.is_set():
                    _runs.pop(run_id, None)

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _error_generator(message: str) -> AsyncIterator[str]:
    evt = ErrorEvent(run_id="", timestamp=datetime.now(UTC).isoformat(), detail=message)
    payload = evt.model_dump(mode="json")
    yield f"event: ta:walkforward:error\ndata: {json.dumps(payload)}\n\n"


@router.post("/run/{run_id}/cancel")
async def cancel_run(run_id: str) -> JSONResponse:
    state = _get_run(run_id)
    if state is None:
        return JSONResponse({"error": f"Unknown run_id: {run_id}"}, status_code=404)

    if state.completed.is_set() or state.cancelled:
        return JSONResponse({"status": "already_completed", "run_id": run_id})

    state.cancelled = True
    await _runner.cancel(run_id)

    ts = datetime.now(UTC).isoformat()
    cancel_event = WalkForwardCancelledEvent(
        run_id=run_id,
        timestamp=ts,
        reason="User requested cancellation",
    )
    state.events.append(cancel_event)
    async with state.lock:
        for q in state.queues:
            q.put_nowait(cancel_event)
    state.completed.set()
    return JSONResponse({"status": "cancelled", "run_id": run_id})
