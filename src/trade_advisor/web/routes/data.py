from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Form, Query, Request, Response

from trade_advisor.core.errors import DataError
from trade_advisor.infra.db import DatabaseManager
from trade_advisor.main import get_db, get_templates

log = logging.getLogger(__name__)

router = APIRouter(prefix="/data")

_db_dep = Depends(get_db)

_SYMBOL_SUMMARY_SQL = """
SELECT
    symbol,
    interval,
    COUNT(*) as bar_count,
    MIN(timestamp) as start_date,
    MAX(timestamp) as end_date,
    MAX(created_at) as last_updated,
    BOOL_OR(adj_close IS NULL) as has_null_adj,
    BOOL_OR(adj_close IS NOT NULL AND adj_close != close) as has_adj_diff
FROM ohlcv_cache
GROUP BY symbol, interval
ORDER BY symbol, interval
"""

_SYMBOL_DETAIL_SQL = """
SELECT timestamp, open, high, low, close, adj_close, volume, source,
       split_factor, div_factor
FROM ohlcv_cache
WHERE symbol = ? AND interval = '1d'
ORDER BY timestamp DESC
LIMIT ? OFFSET ?
"""

_SYMBOL_COUNT_SQL = """
SELECT COUNT(*) FROM ohlcv_cache WHERE symbol = ? AND interval = '1d'
"""

_CORP_ACTION_CHECK_SQL = """
SELECT timestamp, split_factor, div_factor
FROM ohlcv_cache
WHERE symbol = ? AND interval = '1d' AND (ABS(split_factor - 1.0) > 1e-9 OR ABS(div_factor - 1.0) > 1e-9)
"""

_EMPTY_CHECK_SQL = "SELECT COUNT(*) FROM ohlcv_cache"


def _format_ts_utc(ts: Any) -> str:
    if ts is None:
        return "N/A"
    if isinstance(ts, str):
        dt = datetime.fromisoformat(ts)
    elif isinstance(ts, datetime):
        dt = ts
    else:
        return str(ts)
    dt = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def _adj_label(has_null_adj: bool, has_adj_diff: bool) -> str:
    if has_null_adj:
        return "Raw (unadjusted)"
    if has_adj_diff:
        return "Adjusted"
    return "Adjusted (no diff)"


def _is_htmx(request: Request) -> bool:
    return request.headers.get("hx-request") == "true"


def _pagination_error_response(msg: str) -> Response:
    import json

    return Response(
        content=json.dumps({"detail": msg}),
        status_code=422,
        media_type="application/json",
    )


async def _build_symbol_list(db: DatabaseManager) -> list[dict]:
    rows = await db.read(_SYMBOL_SUMMARY_SQL)
    symbols = []
    for r in rows:
        symbols.append(
            {
                "symbol": r[0],
                "interval": r[1],
                "bar_count": r[2],
                "start_date": _format_ts_utc(r[3]),
                "end_date": _format_ts_utc(r[4]),
                "last_updated": _format_ts_utc(r[5]),
                "has_null_adj": bool(r[6]),
                "has_adj_diff": bool(r[7]),
                "adj_label": _adj_label(bool(r[6]), bool(r[7])),
            }
        )
    return symbols


@router.get("")
async def data_explorer(request: Request, db: DatabaseManager = _db_dep):
    templates = get_templates()

    try:
        count_rows = await db.read(_EMPTY_CHECK_SQL)
        is_empty = count_rows[0][0] == 0 if count_rows else True
    except DataError:
        err_ctx: dict[str, Any] = {"error_message": "Failed to read data from database."}
        if _is_htmx(request):
            resp = templates.TemplateResponse(request, "partials/error_state.html", err_ctx)
            resp.headers["HX-Retarget"] = "#error-container"
            resp.headers["HX-Reswap"] = "innerHTML"
            return resp
        return templates.TemplateResponse(request, "pages/data_explorer.html", err_ctx)
    except Exception:
        log.warning("Unexpected DB error checking empty state", exc_info=True)
        conn_err_ctx: dict[str, Any] = {"error_message": "Database connection error."}
        if _is_htmx(request):
            resp = templates.TemplateResponse(request, "partials/error_state.html", conn_err_ctx)
            resp.headers["HX-Retarget"] = "#error-container"
            resp.headers["HX-Reswap"] = "innerHTML"
            return resp
        return templates.TemplateResponse(request, "pages/data_explorer.html", conn_err_ctx)

    if is_empty:
        if _is_htmx(request):
            return templates.TemplateResponse(request, "partials/empty_state.html", {})
        return templates.TemplateResponse(request, "pages/data_explorer.html", {"is_empty": True})

    try:
        symbols = await _build_symbol_list(db)
    except DataError:
        read_err_ctx: dict[str, Any] = {"error_message": "Failed to read data from database."}
        if _is_htmx(request):
            resp = templates.TemplateResponse(request, "partials/error_state.html", read_err_ctx)
            resp.headers["HX-Retarget"] = "#error-container"
            resp.headers["HX-Reswap"] = "innerHTML"
            return resp
        return templates.TemplateResponse(request, "pages/data_explorer.html", read_err_ctx)

    ctx: dict[str, Any] = {"symbols": symbols, "is_empty": False}
    if _is_htmx(request):
        return templates.TemplateResponse(request, "partials/symbol_list.html", ctx)
    return templates.TemplateResponse(request, "pages/data_explorer.html", ctx)


@router.get("/symbol/{symbol}")
async def symbol_detail(
    request: Request,
    symbol: str,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: DatabaseManager = _db_dep,
):
    if page < 1:
        return _pagination_error_response("page must be >= 1")
    if size < 1:
        return _pagination_error_response("size must be >= 1")

    templates = get_templates()

    try:
        count_rows = await db.read(_SYMBOL_COUNT_SQL, (symbol,))
        total_bars = count_rows[0][0] if count_rows else 0
    except DataError:
        total_bars = 0

    if total_bars == 0:
        ctx = {"symbol": symbol, "bars": [], "page": 1, "size": size, "total": 0}
        return templates.TemplateResponse(request, "partials/symbol_detail.html", ctx)

    offset = (page - 1) * size
    try:
        rows = await db.read(_SYMBOL_DETAIL_SQL, (symbol, size, offset))
    except DataError as exc:
        ctx = {"error_message": str(exc)}
        resp = templates.TemplateResponse(request, "partials/error_state.html", ctx)
        resp.headers["HX-Retarget"] = "#error-container"
        resp.headers["HX-Reswap"] = "innerHTML"
        return resp

    bars = []
    for r in rows:
        bar = {
            "timestamp": _format_ts_utc(r[0]),
            "open": r[1],
            "high": r[2],
            "low": r[3],
            "close": r[4],
            "adj_close": r[5],
            "volume": r[6],
            "source": r[7],
            "split_factor": r[8],
            "div_factor": r[9],
            "is_corporate_action": abs((r[8] or 1.0) - 1.0) > 1e-9 or abs((r[9] or 1.0) - 1.0) > 1e-9,
        }
        bars.append(bar)

    anomalies = await _get_anomalies_for_symbol(db, symbol, bars)

    total_pages = max(1, (total_bars + size - 1) // size)
    ctx = {
        "symbol": symbol,
        "bars": bars,
        "anomalies": anomalies,
        "page": page,
        "size": size,
        "total": total_bars,
        "total_pages": total_pages,
    }
    return templates.TemplateResponse(request, "partials/symbol_detail.html", ctx)


async def _get_anomalies_for_symbol(
    db: DatabaseManager, symbol: str, bars: list[dict]
) -> list[dict]:
    anomalies: list[dict] = []
    try:
        corp_rows = await db.read(_CORP_ACTION_CHECK_SQL, (symbol,))
        for r in corp_rows:
            ts, sf, df = r
            if abs(sf - 1.0) > 1e-9:
                anomalies.append(
                    {
                        "type": "corporate_action",
                        "label": "Corporate Action: Stock Split",
                        "severity": "caution",
                        "timestamp": _format_ts_utc(ts),
                    }
                )
            if abs(df - 1.0) > 1e-9:
                anomalies.append(
                    {
                        "type": "corporate_action",
                        "label": "Corporate Action: Dividend",
                        "severity": "caution",
                        "timestamp": _format_ts_utc(ts),
                    }
                )
    except Exception:
        log.warning("Failed to query corporate actions for %s", symbol, exc_info=True)

    return anomalies


@router.post("/fetch")
async def fetch_symbol(
    request: Request,
    symbol: str = Form("SPY"),
    db: DatabaseManager = _db_dep,
):
    templates = get_templates()
    symbol = symbol.strip().upper() or "SPY"

    if not symbol.replace(".", "").replace("-", "").isalnum() or len(symbol) > 20:
        validation_ctx: dict[str, Any] = {"error_message": f"Invalid symbol: {symbol}"}
        resp = templates.TemplateResponse(request, "partials/error_state.html", validation_ctx)
        resp.headers["HX-Retarget"] = "#error-container"
        resp.headers["HX-Reswap"] = "innerHTML"
        return resp

    try:
        from trade_advisor.data.providers.yahoo import YahooProvider
        from trade_advisor.data.storage import DataRepository

        provider = YahooProvider()
        df = await provider.fetch(symbol, interval="1d")
        repo = DataRepository(db)
        await repo.store(df, provider_name=provider.name)
    except Exception as exc:
        log.warning("Fetch failed for %s: %s", symbol, exc)
        fetch_ctx: dict[str, Any] = {"error_message": f"Failed to fetch {symbol}: {exc}"}
        resp = templates.TemplateResponse(request, "partials/error_state.html", fetch_ctx)
        resp.headers["HX-Retarget"] = "#error-container"
        resp.headers["HX-Reswap"] = "innerHTML"
        return resp

    try:
        symbols = await _build_symbol_list(db)
    except DataError:
        err_ctx2: dict[str, Any] = {"error_message": "Data stored but failed to reload list."}
        resp = templates.TemplateResponse(request, "partials/error_state.html", err_ctx2)
        resp.headers["HX-Retarget"] = "#error-container"
        resp.headers["HX-Reswap"] = "innerHTML"
        return resp

    result_ctx: dict[str, Any] = {"symbols": symbols, "is_empty": False}
    return templates.TemplateResponse(request, "partials/symbol_list.html", result_ctx)
