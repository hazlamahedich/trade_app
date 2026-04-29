from __future__ import annotations

import logging
import math
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

log = logging.getLogger(__name__)

router = APIRouter(prefix="/backtests")


def _is_htmx(request: Request) -> bool:
    return request.headers.get("hx-request") == "true"


def _safe_float(v: Any, fallback: float = 0.0) -> float:
    if v is None:
        return fallback
    f = float(v)
    return f if math.isfinite(f) else fallback


def _metrics_to_context(metrics: Any) -> dict[str, Any]:
    return {
        "total_return": _safe_float(metrics.total_return),
        "cagr": _safe_float(metrics.cagr),
        "sharpe": _safe_float(metrics.sharpe),
        "max_drawdown": _safe_float(metrics.max_drawdown),
        "alpha": _safe_float(metrics.alpha),
        "beta": _safe_float(metrics.beta),
    }


@router.get("")
async def backtests_index() -> Any:
    return RedirectResponse(url="/strategies", status_code=302)


@router.get("/{run_id}")
async def backtest_viewer(request: Request, run_id: str) -> Any:
    from trade_advisor.main import get_templates
    from trade_advisor.web.services.result_store import get_result_store

    templates = get_templates()
    store = get_result_store()
    stored = await store.get(run_id)

    if stored is None:
        ctx: dict[str, Any] = {"error_message": f"Backtest result not found: {run_id}"}
        if _is_htmx(request):
            resp = templates.TemplateResponse(request, "partials/error_state.html", ctx)
            resp.headers["HX-Retarget"] = "#results-container"
            resp.headers["HX-Reswap"] = "innerHTML"
            return resp
        return templates.TemplateResponse(
            request, "pages/backtest_viewer.html", ctx, status_code=404
        )

    comparison = stored.comparison
    integrity = comparison.integrity

    if integrity.should_halt_display:
        ctx = {
            "error_message": "Backtest results contain critical integrity errors and cannot be displayed.",
            "integrity_errors": integrity.errors,
            "run_id": run_id,
        }
        if _is_htmx(request):
            return templates.TemplateResponse(request, "partials/error_state.html", ctx)
        return templates.TemplateResponse(
            request, "pages/backtest_viewer.html", ctx, status_code=422
        )

    strategy_metrics = _metrics_to_context(comparison.strategy_metrics)
    baseline_metrics = _metrics_to_context(comparison.buy_and_hold_metrics)

    trades = comparison.strategy_result.trades
    trade_count = len(trades)
    win_rate = 0.0
    gross_wins = 0.0
    gross_losses = 0.0
    if trade_count > 0:
        trade_returns = trades["return"]
        winning = trade_returns[trade_returns > 0]
        losing = trade_returns[trade_returns < 0]
        win_rate = len(winning) / trade_count
        gross_wins = float(winning.sum()) if len(winning) > 0 else 0.0
        gross_losses = abs(float(losing.sum())) if len(losing) > 0 else 0.0

    trade_analysis = stored.trade_analysis

    equity = comparison.strategy_result.equity
    baseline_equity = comparison.buy_and_hold_result.equity

    strategy_equity_arr = [float(v) for v in equity.values]
    baseline_equity_arr = [float(v) for v in baseline_equity.values]
    timestamps_arr = [str(ts) for ts in equity.index]

    equity_props = {
        "strategy_equity": strategy_equity_arr,
        "baseline_equity": baseline_equity_arr,
        "timestamps": timestamps_arr,
    }

    regime_summary = None
    if comparison.regime is not None:
        regime_summary = str(comparison.regime)

    emotional_state = "neutral"
    diagnosis: dict[str, Any] = {}
    try:
        from trade_advisor.web.services.emotional_state import (
            STRESS_TEST_SUGGESTIONS,
            classify_emotional_state,
            compute_profit_factor,
        )

        profit_factor = compute_profit_factor(gross_wins, gross_losses)
        state_enum, diagnosis = classify_emotional_state(
            strategy_total_return=strategy_metrics["total_return"],
            baseline_total_return=baseline_metrics["total_return"],
            sharpe=strategy_metrics["sharpe"],
            profit_factor=profit_factor,
            max_drawdown=strategy_metrics["max_drawdown"],
            trade_count=trade_count,
            baseline_sharpe=baseline_metrics["sharpe"],
        )
        emotional_state = state_enum.value
    except Exception:
        log.warning("Emotional state classification failed, using neutral", exc_info=True)

    variants: list[dict] = []
    remix_url = ""
    parent_source_run_id: str | None = None
    source_expired = False
    try:
        from trade_advisor.web.services.remix import generate_variants

        config_dict_for_variants = {
            k: v for k, v in stored.config_dict.items() if k != "source_run_id"
        }
        strategy_type = stored.config_dict.get("strategy_type", "sma")
        variant_objs = generate_variants(config_dict_for_variants, strategy_type)
        variants = [v.model_dump() for v in variant_objs]

        remix_params = {
            k: str(v) for k, v in stored.config_dict.items()
            if k != "source_run_id" and isinstance(v, (str, int, float))
        }
        remix_url = f"/strategies?{urlencode(remix_params)}" if remix_params else ""

        parent_source_run_id = getattr(stored, "source_run_id", None) or stored.config_dict.get(
            "source_run_id"
        )
        if parent_source_run_id is not None:
            parent_source_run_id = str(parent_source_run_id)
        if parent_source_run_id:
            parent_result = await store.get(parent_source_run_id)
            if parent_result is None:
                source_expired = True
    except Exception:
        log.warning("Remix context generation failed", exc_info=True)

    ctx = {
        "run_id": run_id,
        "created_at": stored.created_at.strftime("%Y-%m-%d %H:%M UTC"),
        "config": stored.config_dict,
        "is_label": comparison.is_label,
        "strategy_metrics": strategy_metrics,
        "baseline_metrics": baseline_metrics,
        "trade_count": trade_count,
        "win_rate": win_rate,
        "avg_holding_period": trade_analysis.avg_holding_period,
        "avg_mfe": float(trade_analysis.avg_mfe),
        "avg_mae": float(trade_analysis.avg_mae),
        "equity_props": equity_props,
        "integrity_warnings": integrity.warnings if not integrity.is_valid else [],
        "engine_mode": stored.engine_mode,
        "regime_summary": regime_summary,
        "emotional_state": emotional_state,
        "diagnosis": diagnosis,
        "STRESS_TEST_SUGGESTIONS": STRESS_TEST_SUGGESTIONS,
        "variants": variants,
        "remix_url": remix_url,
        "source_run_id": parent_source_run_id,
        "source_expired": source_expired,
    }
    return templates.TemplateResponse(request, "pages/backtest_viewer.html", ctx)
