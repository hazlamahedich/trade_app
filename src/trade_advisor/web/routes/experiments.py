from __future__ import annotations

import contextlib
import json
import logging
import math
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from trade_advisor.infra.protocols import DatabaseReader

log = logging.getLogger(__name__)

router = APIRouter(prefix="/experiments")
api_router = APIRouter(prefix="/api/experiments")


def _is_htmx(request: Request) -> bool:
    return request.headers.get("hx-request") == "true"


def _safe_float(v: Any, fallback: float = 0.0) -> float:
    if v is None:
        return fallback
    f = float(v)
    return f if math.isfinite(f) else fallback


def _safe_int_param(
    val: str | None, fallback: int, *, min_val: int = 0, max_val: int | None = None
) -> int:
    if val is None:
        return fallback
    try:
        result = int(val)
    except (ValueError, TypeError):
        return fallback
    result = max(result, min_val)
    if max_val is not None:
        result = min(result, max_val)
    return result


def _parse_metrics(metrics_json: str | None) -> dict[str, Any]:
    if not metrics_json:
        return {}
    with contextlib.suppress(json.JSONDecodeError, TypeError):
        return dict(json.loads(metrics_json))
    return {}


def _parse_filters(params: Any) -> dict[str, Any] | None:
    filters: dict[str, Any] = {}
    strategy = params.get("strategy")
    if strategy:
        filters["strategy"] = strategy
    status = params.get("status")
    if status:
        filters["status"] = status
    start_str = params.get("start_date")
    end_str = params.get("end_date")
    if start_str and end_str:
        from datetime import datetime

        try:
            start = datetime.fromisoformat(start_str)
            end = datetime.fromisoformat(end_str)
            filters["date_range"] = (start, end)
        except (ValueError, TypeError):
            pass
    return filters if filters else None


def _format_runs_for_display(runs: list[Any]) -> list[dict[str, Any]]:
    formatted = []
    for run in runs:
        metrics = _parse_metrics(run.metrics_json)

        diagnostics: dict[str, Any] = {}
        if getattr(run, "diagnostics_json", None):
            with contextlib.suppress(json.JSONDecodeError):
                diagnostics = json.loads(run.diagnostics_json)

        dsr = diagnostics.get("dsr")
        formatted.append(
            {
                "run_id": run.run_id,
                "strategy": run.strategy,
                "status": run.status,
                "created_at": run.created_at,
                "sharpe_display": f"{metrics.get('sharpe', 0.0):.2f}"
                if metrics.get('sharpe') is not None
                else "—",
                "return_display": f"{metrics.get('total_return', 0.0) * 100:+.1f}%"
                if metrics.get('total_return') is not None
                else "—",
                "dd_display": f"{metrics.get('max_drawdown', 0.0) * 100:.1f}%"
                if metrics.get('max_drawdown') is not None
                else "—",
                "n_trials": getattr(run, "n_trials", 0) or 0,
                "dsr_display": f"{dsr:.1%}" if dsr is not None else "—",
                "pre_mortem": run.pre_mortem,
            }
        )
    return formatted


@router.get("")
async def experiment_list(request: Request) -> Any:
    from trade_advisor.main import get_db, get_templates

    templates = get_templates()
    db = await get_db(request)

    qp = request.query_params
    sort = qp.get("sort", "created_at")
    direction = qp.get("dir", "desc")
    limit = _safe_int_param(qp.get("limit"), 50, min_val=1, max_val=500)
    offset = _safe_int_param(qp.get("offset"), 0, min_val=0)
    filters = _parse_filters(qp)

    try:
        from trade_advisor.experiments.tracker import ExperimentRepository

        runs = await ExperimentRepository.list_runs(
            db, order_by=sort, order_dir=direction, limit=limit, offset=offset, filters=filters
        )
    except Exception as exc:
        log.warning("ta:experiments:list_failed: %s", exc)
        ctx: dict[str, Any] = {
            "error_message": "Unable to load experiments. Your data is safe — please try again.",
            "runs": [],
        }
        if _is_htmx(request):
            return templates.TemplateResponse(
                request, "partials/experiment_row.html", ctx, status_code=503
            )
        return templates.TemplateResponse(
            request, "pages/experiment_list.html", ctx, status_code=503
        )

    ctx = {
        "runs": _format_runs_for_display(runs),
        "sort": sort,
        "direction": direction,
        "limit": limit,
        "offset": offset,
    }
    if _is_htmx(request):
        return templates.TemplateResponse(request, "partials/experiment_row.html", ctx)
    return templates.TemplateResponse(request, "pages/experiment_list.html", ctx)


@api_router.get("")
async def api_experiment_list(request: Request) -> Any:
    from trade_advisor.main import get_db

    db = await get_db(request)
    qp = request.query_params
    sort = qp.get("sort", "created_at")
    direction = qp.get("dir", "desc")
    limit = _safe_int_param(qp.get("limit"), 50, min_val=1, max_val=500)
    offset = _safe_int_param(qp.get("offset"), 0, min_val=0)
    filters = _parse_filters(qp)

    try:
        from trade_advisor.experiments.tracker import ExperimentRepository, generate_narrative

        runs = await ExperimentRepository.list_runs(
            db, order_by=sort, order_dir=direction, limit=limit, offset=offset, filters=filters
        )
    except Exception:
        return JSONResponse([], status_code=503)

    result = []
    for run in runs:
        metrics = _parse_metrics(run.metrics_json)
        narrative = generate_narrative(run)
        result.append(
            {
                "run_id": run.run_id,
                "strategy": run.strategy,
                "status": run.status,
                "metrics": metrics,
                "narrative": narrative,
                "created_at": run.created_at.isoformat() if run.created_at else None,
                "pre_mortem": run.pre_mortem,
                "seed": run.seed,
            }
        )
    return JSONResponse(result)


@api_router.get("/compare")
async def api_experiment_compare(request: Request) -> Any:
    from trade_advisor.main import get_db

    db = await get_db(request)
    qp = request.query_params
    run_a = qp.get("run_a", "").strip()
    run_b = qp.get("run_b", "").strip()

    if not run_a or not run_b:
        return JSONResponse({"error": "Missing run_a or run_b parameters"}, status_code=400)

    try:
        from trade_advisor.experiments.compare import compare_runs

        diff = compare_runs(db, run_a, run_b)
        return JSONResponse(diff.model_dump(mode="json"))
    except ValueError as exc:
        msg = str(exc)
        run_id = run_b if "run_a" not in msg else run_a
        return JSONResponse({"error": "Run not found", "run_id": run_id}, status_code=404)
    except Exception as exc:
        log.warning("ta:experiments:compare_failed: %s", exc)
        return JSONResponse({"error": "Unable to compare runs."}, status_code=500)


@router.get("/compare")
async def experiment_compare_page(request: Request) -> Any:
    from trade_advisor.main import get_db, get_templates

    templates = get_templates()
    db = await get_db(request)
    qp = request.query_params
    run_a = qp.get("run_a", "").strip()
    run_b = qp.get("run_b", "").strip()

    if not run_a or not run_b:
        ctx: dict[str, Any] = {"error_message": "Missing run_a or run_b parameters"}
        return templates.TemplateResponse(request, "pages/compare.html", ctx, status_code=400)

    try:
        from trade_advisor.experiments.compare import compare_runs

        diff = compare_runs(db, run_a, run_b)
        ctx = {
            "diff": diff,
            "run_a": run_a,
            "run_b": run_b,
        }
        return templates.TemplateResponse(request, "pages/compare.html", ctx)
    except ValueError:
        ctx = {"error_message": "Run not found. Try another run.", "run_a": run_a, "run_b": run_b}
        return templates.TemplateResponse(request, "pages/compare.html", ctx, status_code=404)
    except Exception as exc:
        log.warning("ta:experiments:compare_page_failed: %s", exc)
        ctx = {"error_message": "Unable to compare runs. Please try again."}
        return templates.TemplateResponse(request, "pages/compare.html", ctx, status_code=500)


@api_router.get("/{run_id}/lineage")
async def api_experiment_lineage(request: Request, run_id: str) -> Any:
    from trade_advisor.main import get_db

    db = await get_db(request)
    try:
        from trade_advisor.experiments.tracker import ExperimentRepository

        if not await ExperimentRepository.run_exists(db, run_id):
            return JSONResponse({"error": "not found"}, status_code=404)

        from trade_advisor.experiments.lineage import get_lineage

        lineage = await get_lineage(db, run_id)
        return JSONResponse(lineage.model_dump(mode="json"))
    except Exception as exc:
        log.warning("ta:experiments:lineage_failed run_id=%s: %s", run_id, exc)
        return JSONResponse({"error": "Unable to load lineage."}, status_code=500)


@api_router.get("/{run_id}")
async def api_experiment_detail(request: Request, run_id: str) -> Any:
    from trade_advisor.main import get_db

    db = await get_db(request)

    try:
        from trade_advisor.experiments.tracker import ExperimentRepository, generate_narrative

        record = await ExperimentRepository.get_run(db, run_id)
        if record is None:
            return JSONResponse({"error": "not found"}, status_code=404)

        metrics = _parse_metrics(record.metrics_json)

        narrative = generate_narrative(record)

        result = await ExperimentRepository.load_full_result(db, run_id)

        baseline_metrics = {}
        if result is not None:
            bm = result.comparison.buy_and_hold_metrics
            baseline_metrics = {
                "total_return": _safe_float(bm.total_return),
                "sharpe": _safe_float(bm.sharpe),
            }

        return JSONResponse(
            {
                "run_id": record.run_id,
                "strategy": record.strategy,
                "status": record.status,
                "metrics": metrics,
                "baseline_metrics": baseline_metrics,
                "narrative": narrative,
                "created_at": record.created_at.isoformat() if record.created_at else None,
                "pre_mortem": record.pre_mortem,
                "seed": record.seed,
                "config_hash": record.config_hash,
                "git_commit": record.git_commit,
                "data_fingerprint": record.data_fingerprint,
                "parent_run_id": record.parent_run_id,
                "n_trials": record.n_trials,
                "sr_variance": record.sr_variance,
                "diagnostics": json.loads(record.diagnostics_json) if record.diagnostics_json else None,
            }
        )
    except Exception as exc:
        log.warning("ta:experiments:detail_failed run_id=%s: %s", run_id, exc)
        return JSONResponse({"error": "Unable to load experiment detail."}, status_code=503)


@api_router.post("/{run_id}/reproduce")
async def api_experiment_reproduce(request: Request, run_id: str) -> Any:
    if not run_id or not run_id.strip():
        return JSONResponse({"error": "run_id is required"}, status_code=400)

    db: DatabaseReader = request.app.state.db
    if db is None:
        return JSONResponse({"error": "Database not initialized"}, status_code=503)

    try:
        from trade_advisor.experiments.reproduction import (
            ReproductionError,
            check_data_freshness,
            reproduce_run,
        )

        freshness = check_data_freshness(db, run_id)
        result = await reproduce_run(db, run_id)

        response_data: dict[str, Any] = {
            "run_id": result.run_id,
            "parent_run_id": result.parent_run_id,
            "is_clone": result.is_clone,
        }
        if freshness.has_changed:
            response_data["data_freshness_warning"] = freshness.warning
        return JSONResponse(response_data)
    except ReproductionError as exc:
        if exc.error_code == "not_found":
            return JSONResponse({"error": "Run not found", "run_id": run_id}, status_code=404)
        return JSONResponse({"error": str(exc), "run_id": run_id}, status_code=400)
    except Exception as exc:
        log.warning("ta:experiments:reproduce_failed run_id=%s: %s", run_id, exc)
        return JSONResponse({"error": "Unable to reproduce run."}, status_code=500)


@router.get("/{run_id}")
async def experiment_detail(request: Request, run_id: str) -> Any:
    from trade_advisor.main import get_db, get_templates

    templates = get_templates()
    db = await get_db(request)

    try:
        from trade_advisor.experiments.tracker import ExperimentRepository, generate_narrative

        record = await ExperimentRepository.get_run(db, run_id)
        if record is None:
            ctx: dict[str, Any] = {"error_message": f"Experiment not found: {run_id}"}
            return templates.TemplateResponse(
                request, "pages/experiment_detail.html", ctx, status_code=404
            )

        metrics = _parse_metrics(record.metrics_json)

        narrative = generate_narrative(record)

        result = await ExperimentRepository.load_full_result(db, run_id)

        equity_props: dict[str, Any] = {}
        trades_data: list[dict[str, Any]] = []
        baseline_metrics: dict[str, Any] = {}
        trade_count = 0

        if result is not None:
            equity = result.comparison.strategy_result.equity
            baseline_equity = result.comparison.buy_and_hold_result.equity
            equity_props = {
                "strategy_equity": [float(v) for v in equity.values],
                "baseline_equity": [float(v) for v in baseline_equity.values],
                "timestamps": [str(ts) for ts in equity.index],
            }

            trades_df = result.comparison.strategy_result.trades
            trade_count = len(trades_df)
            trades_data = trades_df.to_dict(orient="records") if trade_count > 0 else []

            bm = result.comparison.buy_and_hold_metrics
            baseline_metrics = {
                "total_return": _safe_float(bm.total_return),
                "cagr": _safe_float(bm.cagr),
                "sharpe": _safe_float(bm.sharpe),
                "max_drawdown": _safe_float(bm.max_drawdown),
            }

        ctx = {
            "record": record,
            "metrics": metrics,
            "baseline_metrics": baseline_metrics,
            "narrative": narrative,
            "equity_props": equity_props,
            "trades": trades_data,
            "trade_count": trade_count,
            "run_id": run_id,
            "has_result": result is not None,
            "diagnostics": json.loads(record.diagnostics_json) if record.diagnostics_json else None,
        }

        try:
            other_rows = db._execute_read(
                "SELECT run_id, strategy FROM experiments WHERE run_id != ? ORDER BY created_at DESC LIMIT 5",
                (run_id,),
            )
            ctx["other_runs"] = [{"run_id": r[0], "strategy": r[1]} for r in other_rows]
        except Exception:
            ctx["other_runs"] = []

        try:
            from trade_advisor.experiments.lineage import get_lineage as _get_lineage

            lineage_result = await _get_lineage(db, run_id)
            ctx["lineage_result"] = lineage_result
        except Exception:
            ctx["lineage_result"] = None

        return templates.TemplateResponse(request, "pages/experiment_detail.html", ctx)
    except Exception as exc:
        log.warning("ta:experiments:detail_failed run_id=%s: %s", run_id, exc)
        ctx = {"error_message": "Unable to load experiments. Your data is safe — please try again."}
        return templates.TemplateResponse(
            request, "pages/experiment_detail.html", ctx, status_code=503
        )
