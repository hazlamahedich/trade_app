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
from trade_advisor.web.models import WFResultResponse, WFWindowResponse, WFDiagnosticsResponse
from trade_advisor.web.sse import (
    ErrorEvent,
    WalkForwardCancelledEvent,
    WalkForwardCompletedEvent,
    WalkForwardProgressEvent,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/walkforward")
api_router = APIRouter(prefix="/api/walkforward")

_runner = InProcessTaskRunner()


@dataclass
class _RunState:
    events: list[Any] = field(default_factory=list)
    queues: list[asyncio.Queue[Any]] = field(default_factory=list)
    completed: asyncio.Event = field(default_factory=asyncio.Event)
    cancelled: bool = False
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    result: Any | None = None
    raw_result: Any | None = None


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
            # AC-6: Micro-lessons during progress
            lessons = [
                "Walk-forward validation helps detect overfitting by testing on unseen data.",
                "WFE > 0.7 suggests the strategy edge is robust across time windows.",
                "Parameter drift indicates how the optimal strategy changes with market regimes.",
                "Deflated Sharpe Ratio (DSR) accounts for the number of trials performed.",
            ]
            event.message = lessons[event.window_idx % len(lessons)]
            
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
            
            state.result = result
            state.raw_result = result

            completed = WalkForwardCompletedEvent(
                run_id=run_id,
                timestamp=datetime.now(UTC).isoformat(),
                n_windows=result.n_windows,
                discarded_bars=result.discarded_bars,
            )
            _emit(completed)
        except Exception:
            _emit(
                ErrorEvent(
                    run_id=run_id,
                    timestamp=datetime.now(UTC).isoformat(),
                    detail="Walk-forward run failed",
                )
            )
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


@router.get("")
@router.get("/")
async def walkforward_index(request: Request) -> Any:
    from trade_advisor.main import get_templates

    templates = get_templates()
    return templates.TemplateResponse(request, "pages/walkforward.html", {"run_id": None})


@router.get("/{run_id}")
async def walkforward_detail(request: Request, run_id: str) -> Any:
    from trade_advisor.main import get_templates

    templates = get_templates()
    return templates.TemplateResponse(request, "pages/walkforward.html", {"run_id": run_id})


def _downsample(data: list[dict[str, Any]], target: int = 1000) -> list[dict[str, Any]]:
    """Simple nth-point downsampling for large equity curves."""
    n = len(data)
    if n <= target:
        return data
    step = n // target
    return data[::step]


@api_router.get("/{run_id}", response_model=WFResultResponse)
async def get_wf_results(request: Request, run_id: str) -> Any:
    state = _get_run(run_id)
    if state is None or state.result is None:
        # Fallback to DB for completed runs
        import json

        from trade_advisor.main import get_db

        db = await get_db(request)
        rows = await db.read(
            "SELECT metrics_json, config_json, trade_analysis_json FROM experiments WHERE run_id = ?",
            (run_id,),
        )
        if not rows:
            return JSONResponse({"error": "Results not found or run not completed"}, status_code=404)

        metrics = json.loads(rows[0][0] or "{}")
        cfg = json.loads(rows[0][1] or "{}")
        results = json.loads(rows[0][2] or "{}")

        # Reconstruct curves from results_json if available
        equity = results.get("stitched_equity", [])
        baseline = results.get("baseline_equity", [])

        return WFResultResponse(
            run_id=run_id,
            wfe=metrics.get("wfe", 0.0),
            wfe_status=metrics.get("wfe_status", "caution"),
            equity=_downsample(equity),
            baseline=_downsample(baseline),
            windows=[
                WFWindowResponse(
                    window_idx=i,
                    is_start=w.get("is_start", ""),
                    is_end=w.get("is_end", ""),
                    oos_start=w.get("oos_start", ""),
                    oos_end=w.get("oos_end", ""),
                    is_sharpe=w.get("is_sharpe", 0.0),
                    oos_sharpe=w.get("oos_sharpe", 0.0),
                    is_return=w.get("is_return", 0.0),
                    oos_return=w.get("oos_return", 0.0),
                    params=w.get("params"),
                )
                for i, w in enumerate(results.get("windows", []))
            ]
            or [
                WFWindowResponse(
                    window_idx=0,
                    is_start="",
                    is_end="",
                    oos_start="",
                    oos_end="",
                    is_sharpe=0.0,
                    oos_sharpe=0.0,
                    is_return=0.0,
                    oos_return=0.0,
                )
            ],
            diagnostics=WFDiagnosticsResponse(
                risk_adj_wfe=metrics.get("risk_adj_wfe", 0.0),
                expected_value=metrics.get("expected_value", 0.0),
                dsr=metrics.get("dsr"),
                dsr_significant=metrics.get("dsr_significant", False),
                hints=metrics.get("hints", {}),
            ),
            regime_variance=metrics.get("regime_variance", 0.0),
        )

    res = state.result
    raw = state.raw_result

    # Convert series to lists of dicts for frontend charts
    equity_curve = []
    if res.stitched_equity is not None and not res.stitched_equity.empty:
        for t, v in res.stitched_equity.items():
            equity_curve.append({"time": t.isoformat(), "value": v})

    baseline_curve = []
    if res.baseline_equity is not None and not res.baseline_equity.empty:
        for t, v in res.baseline_equity.items():
            baseline_curve.append({"time": t.isoformat(), "value": v})

    windows_data = []
    if raw is not None and raw.windows:
        for i, w in enumerate(raw.windows):
            windows_data.append(
                WFWindowResponse(
                    window_idx=i,
                    is_start=w.boundary.is_start_dt.isoformat()
                    if hasattr(w.boundary, "is_start_dt")
                    else str(w.boundary.is_start),
                    is_end=w.boundary.is_end_dt.isoformat()
                    if hasattr(w.boundary, "is_end_dt")
                    else str(w.boundary.is_end),
                    oos_start=w.boundary.oos_start_dt.isoformat()
                    if hasattr(w.boundary, "oos_start_dt")
                    else str(w.boundary.oos_start),
                    oos_end=w.boundary.oos_end_dt.isoformat()
                    if hasattr(w.boundary, "oos_end_dt")
                    else str(w.boundary.oos_end),
                    is_sharpe=w.is_sharpe,
                    oos_sharpe=w.oos_sharpe,
                    is_return=w.is_return,
                    oos_return=w.oos_return,
                    params=w.optimization_result.best_params if w.optimization_result else None,
                )
            )

    return WFResultResponse(
        run_id=run_id,
        wfe=res.wfe,
        wfe_status=res.wfe_status,
        equity=_downsample(equity_curve),
        baseline=_downsample(baseline_curve),
        windows=windows_data,
        diagnostics=WFDiagnosticsResponse(**res.diagnostics.__dict__) if res.diagnostics else None,
        regime_variance=res.regime_variance,
    )
