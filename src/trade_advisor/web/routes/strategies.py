from __future__ import annotations

import asyncio
import json
import logging
import math
import re
from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd
from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import StreamingResponse

log = logging.getLogger(__name__)

router = APIRouter(prefix="/strategies")

_OHLCV_SQL = """
SELECT timestamp, open, high, low, close, adj_close, volume
FROM ohlcv_cache
WHERE symbol = ? AND interval = ?
ORDER BY timestamp ASC
"""

_PROGRESS_STAGES = [
    "Loading data...",
    "Generating signals...",
    "Running backtest...",
    "Computing baseline...",
    "Done.",
]


def _is_htmx(request: Request) -> bool:
    return request.headers.get("hx-request") == "true"


def _error_response(request: Request, message: str) -> Any:
    from trade_advisor.main import get_templates

    templates = get_templates()
    ctx = {"error_message": message}
    resp = templates.TemplateResponse(request, "partials/error_state.html", ctx)
    resp.headers["HX-Retarget"] = "#results-container"
    resp.headers["HX-Reswap"] = "innerHTML"
    return resp


_SYMBOL_RE = re.compile(r"^[A-Za-z0-9.\-]+$")


def _safe_int(val: str | None, fallback: int) -> int:
    if val is None:
        return fallback
    try:
        return int(val)
    except (ValueError, TypeError):
        return fallback


def _safe_float(val: str | None, fallback: float) -> float:
    if val is None:
        return fallback
    try:
        return float(val)
    except (ValueError, TypeError):
        return fallback


def _safe_symbol(val: str | None, fallback: str) -> str:
    if val is None or not _SYMBOL_RE.match(val):
        return fallback
    return val.upper()


@router.get("")
async def strategy_lab(request: Request) -> Any:
    from trade_advisor.main import get_templates

    templates = get_templates()
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    qp = request.query_params
    default_symbol = _safe_symbol(qp.get("symbol"), "SPY")
    default_fast = _safe_int(qp.get("fast"), 20)
    default_slow = _safe_int(qp.get("slow"), 50)
    default_interval = qp.get("interval", "1d")
    default_start = qp.get("start_date", "2020-01-01")
    default_end = qp.get("end_date", today)
    default_engine_mode = qp.get("engine_mode", "vectorized")
    default_commission = _safe_float(qp.get("commission_pct"), 0.001)
    default_slippage = _safe_float(qp.get("slippage_pct"), 0.0005)
    default_initial_cash = _safe_float(qp.get("initial_cash"), 100000)
    ctx: dict[str, Any] = {
        "default_symbol": default_symbol,
        "default_fast": default_fast,
        "default_slow": default_slow,
        "default_interval": default_interval,
        "default_start": default_start,
        "default_end": default_end,
        "default_engine_mode": default_engine_mode,
        "default_commission": default_commission,
        "default_slippage": default_slippage,
        "default_initial_cash": default_initial_cash,
    }
    if _is_htmx(request):
        return templates.TemplateResponse(request, "partials/strategy_form.html", ctx)
    return templates.TemplateResponse(request, "pages/strategy_lab.html", ctx)


def _validate_inputs(
    symbol: str,
    fast: int,
    slow: int,
    start_date: str,
    end_date: str,
    initial_cash: float,
    commission_pct: float,
    slippage_pct: float,
) -> str | None:
    if not symbol or not symbol.strip():
        return "Symbol is required."
    if fast <= 0:
        return "Fast period must be positive."
    if slow <= 0:
        return "Slow period must be positive."
    if fast >= slow:
        return f"Fast period ({fast}) must be less than slow period ({slow})."
    try:
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
    except (ValueError, TypeError):
        return "Invalid date format."
    if start_dt >= end_dt:
        return "Start date must be before end date."
    if initial_cash <= 0:
        return "Initial cash must be positive."
    if not math.isfinite(initial_cash):
        return "Initial cash must be a finite number."
    if commission_pct < 0:
        return "Commission must be non-negative."
    if not math.isfinite(commission_pct):
        return "Commission must be a finite number."
    if commission_pct > 1.0:
        return "Commission must be at most 100% (1.0)."
    if slippage_pct < 0:
        return "Slippage must be non-negative."
    if not math.isfinite(slippage_pct):
        return "Slippage must be a finite number."
    if slippage_pct > 1.0:
        return "Slippage must be at most 100% (1.0)."
    return None


@router.post("/run")
async def run_backtest(
    request: Request,
    strategy_type: str = Form("sma"),
    symbol: str = Form("SPY"),
    fast: int = Form(20),
    slow: int = Form(50),
    interval: str = Form("1d"),
    start_date: str = Form("2020-01-01"),
    end_date: str = Form("2025-01-01"),
    engine_mode: str = Form("vectorized"),
    commission_pct: float = Form(0.001),
    slippage_pct: float = Form(0.0005),
    initial_cash: float = Form(100000),
    source_run_id: str = Form(""),
) -> Any:
    symbol = symbol.strip().upper()
    validation_error = _validate_inputs(
        symbol, fast, slow, start_date, end_date, initial_cash, commission_pct, slippage_pct
    )
    if validation_error:
        return _error_response(request, validation_error)

    if not symbol.replace(".", "").replace("-", "").isalnum() or len(symbol) > 20:
        return _error_response(request, f"Invalid symbol: {symbol}")

    from trade_advisor.main import get_db

    db = await get_db(request)

    try:
        rows = await db.read(_OHLCV_SQL, (symbol, interval))
    except Exception as exc:
        log.warning("Database read failed for %s/%s: %s", symbol, interval, exc)
        return _error_response(request, f"Database error: {exc}")
    if not rows:
        return _error_response(
            request, f"No cached data for {symbol}/{interval}. Fetch it first via Data Explorer."
        )

    df = pd.DataFrame(
        rows, columns=["timestamp", "open", "high", "low", "close", "adj_close", "volume"]
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp")

    start_dt = pd.to_datetime(start_date, utc=True)
    end_dt = pd.to_datetime(end_date, utc=True)

    warmup_start = start_dt - timedelta(days=slow * 2)
    mask = (df["timestamp"] >= warmup_start) & (df["timestamp"] <= end_dt)
    ohlcv = df.loc[mask].copy()
    if ohlcv.empty or len(ohlcv) < slow + 10:
        return _error_response(
            request, f"Insufficient data: need at least {slow + 10} bars, got {len(ohlcv)}"
        )

    user_range = ohlcv[ohlcv["timestamp"] >= start_dt]
    if len(user_range) < slow + 10:
        return _error_response(
            request,
            f"Selected date range has {len(user_range)} bars after warmup; need at least {slow + 10}.",
        )

    try:
        from trade_advisor.strategies.sma_cross import SmaCross

        strategy = SmaCross(fast=fast, slow=slow)
        signals = await asyncio.to_thread(strategy.generate_signals, ohlcv)

        from trade_advisor.core.config import BacktestConfig, CostModel
        from trade_advisor.core.types import from_float

        config = BacktestConfig(
            initial_cash=str(from_float(initial_cash)),
            cost=CostModel(commission_pct=commission_pct, slippage_pct=slippage_pct),
        )

        if engine_mode == "event_driven":
            from trade_advisor.backtest.event_driven import EventDrivenEngine

            engine = EventDrivenEngine(config)
            ed_result = await asyncio.to_thread(engine.run, ohlcv, signals)

        from trade_advisor.backtest.baseline import compute_with_baseline
        from trade_advisor.backtest.metrics.trade_analysis import compute_trade_analysis

        comparison = await asyncio.to_thread(compute_with_baseline, ohlcv, signals, config)

        if engine_mode == "event_driven":
            from dataclasses import replace

            comparison = replace(comparison, strategy_result=ed_result)

        trade_analysis = await asyncio.to_thread(compute_trade_analysis, comparison.strategy_result)

    except Exception as exc:
        log.warning("Backtest failed for %s: %s", symbol, exc, exc_info=True)
        return _error_response(request, f"Backtest failed: {exc}")

    from trade_advisor.web.services.result_store import StoredResult, get_result_store

    store = get_result_store()
    run_id = store.generate_run_id()

    config_dict = {
        "strategy_type": strategy_type,
        "symbol": symbol,
        "fast": fast,
        "slow": slow,
        "interval": interval,
        "start_date": start_date,
        "end_date": end_date,
        "engine_mode": engine_mode,
        "commission_pct": commission_pct,
        "slippage_pct": slippage_pct,
        "initial_cash": initial_cash,
    }

    stored = StoredResult(
        comparison=comparison,
        trade_analysis=trade_analysis,
        config_dict=config_dict,
        run_id=run_id,
        created_at=datetime.now(UTC),
        engine_mode=engine_mode,
        source_run_id=source_run_id if source_run_id else None,
    )
    await store.store(stored)

    if source_run_id:
        try:
            from trade_advisor.web.sse import StrategyForkedEvent

            StrategyForkedEvent(
                run_id=run_id,
                timestamp=datetime.now(UTC).isoformat(),
                source_run_id=source_run_id,
                variant_params=config_dict,
            )
            log.info(
                "ta:strategy:forked source=%s new=%s",
                source_run_id,
                run_id,
            )
        except Exception:
            log.warning("SSE fork event construction failed", exc_info=True)

    if _is_htmx(request):
        resp = Response(content="", status_code=200)
        resp.headers["HX-Redirect"] = f"/backtests/{run_id}"
        return resp

    return Response(
        content=json.dumps({"run_id": run_id}),
        media_type="application/json",
        status_code=200,
    )


@router.get("/run/{run_id}/stream")
async def stream_progress(run_id: str) -> StreamingResponse:
    async def _event_generator():
        for i, stage in enumerate(_PROGRESS_STAGES):
            payload = {
                "event_type": "progress",
                "run_id": run_id,
                "timestamp": datetime.now(UTC).isoformat(),
                "current": i + 1,
                "total": len(_PROGRESS_STAGES),
                "message": stage,
            }
            yield f"event: ta:backtest:progress\ndata: {json.dumps(payload)}\n\n"
            await asyncio.sleep(0.1)

        from trade_advisor.web.services.result_store import get_result_store

        store = get_result_store()
        stored = await store.get(run_id)
        if stored:
            completion_payload = {
                "event_type": "progress",
                "run_id": run_id,
                "timestamp": datetime.now(UTC).isoformat(),
                "current": len(_PROGRESS_STAGES),
                "total": len(_PROGRESS_STAGES),
                "message": "Done.",
            }
            yield f"event: ta:backtest:completed\ndata: {json.dumps(completion_payload)}\n\n"

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
