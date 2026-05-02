"""Experiment comparison — side-by-side diff of two experiment runs."""

from __future__ import annotations

import json
import logging
import math
from typing import Any, Literal

from pydantic import BaseModel

from trade_advisor.infra.protocols import DatabaseReader

log = logging.getLogger(__name__)


class MetricChange(BaseModel):
    metric_name: str
    value_a: float | None
    value_b: float | None
    delta: float | None
    direction: Literal["improvement", "degradation", "neutral"]
    icon: str
    label: str


class ParameterChange(BaseModel):
    field: str
    old_value: Any
    new_value: Any


class TradeRecord(BaseModel):
    timestamp: str
    side: str
    quantity: float
    price: float | None


class TradeAlignment(BaseModel):
    alignment_strategy: str
    trades_a: list[TradeRecord]
    trades_b: list[TradeRecord]


class CompareResult(BaseModel):
    metrics_diff: dict[str, MetricChange]
    parameter_diff: list[ParameterChange]
    compatibility_warning: str | None
    baseline_id: str
    challenger_id: str
    missing_sections: list[str]


METRIC_DIRECTION: dict[str, Literal["higher_better", "lower_better"]] = {
    "sharpe": "higher_better",
    "total_return": "higher_better",
    "calmar": "higher_better",
    "sortino": "higher_better",
    "alpha": "higher_better",
    "information_ratio": "higher_better",
    "win_rate": "higher_better",
    "profit_factor": "higher_better",
    "max_drawdown": "higher_better",
    "var_95": "lower_better",
    "cvar_95": "lower_better",
    "tail_ratio": "lower_better",
}

_COMPARE_COLS = (
    "run_id, config_hash, strategy, metrics_json, seed, status, "
    "parent_run_id, created_at, config_json"
)
_COMPARE_COL_NAMES = [c.strip() for c in _COMPARE_COLS.split(",")]


def _parse_json(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return {}


def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
        if math.isfinite(f):
            return f
    except (TypeError, ValueError):
        pass
    return None


def _get_experiment_row(db: DatabaseReader, run_id: str) -> dict[str, Any] | None:
    rows = db._execute_read(
        "SELECT " + _COMPARE_COLS + " FROM experiments WHERE run_id = ?",
        (run_id,),
    )
    if not rows:
        return None
    return dict(zip(_COMPARE_COL_NAMES, rows[0], strict=True))


def _determine_order(
    row_a: dict[str, Any], row_b: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    created_a = row_a.get("created_at")
    created_b = row_b.get("created_at")
    if created_a and created_b:
        if created_a <= created_b:
            return row_a, row_b
        return row_b, row_a
    if row_a["run_id"] <= row_b["run_id"]:
        return row_a, row_b
    return row_b, row_a


def _compute_metrics_diff(
    metrics_a: dict[str, Any], metrics_b: dict[str, Any]
) -> dict[str, MetricChange]:
    result: dict[str, MetricChange] = {}
    all_keys = set(metrics_a.keys()) | set(metrics_b.keys())
    for key in all_keys:
        val_a = _safe_float(metrics_a.get(key))
        val_b = _safe_float(metrics_b.get(key))

        if val_a is None or val_b is None:
            delta = None
            direction: Literal["improvement", "degradation", "neutral"] = "neutral"
        else:
            delta = val_b - val_a
            if abs(delta) < 1e-10:
                direction = "neutral"
            else:
                metric_dir = METRIC_DIRECTION.get(key)
                if metric_dir is None:
                    log.warning("Unknown metric '%s', defaulting to higher_better", key)
                    metric_dir = "higher_better"
                if metric_dir == "higher_better":
                    direction = "improvement" if delta > 0 else "degradation"
                else:
                    direction = "improvement" if delta < 0 else "degradation"

        if direction == "improvement":
            icon, label = "▲", "Improved"
        elif direction == "degradation":
            icon, label = "▼", "Degraded"
        else:
            icon, label = "-", "No change"

        result[key] = MetricChange(
            metric_name=key,
            value_a=val_a,
            value_b=val_b,
            delta=delta,
            direction=direction,
            icon=icon,
            label=label,
        )
    return result


def _compute_parameter_diff_list(
    config_a: dict[str, Any] | None, config_b: dict[str, Any] | None
) -> list[ParameterChange]:
    if config_a is None:
        config_a = {}
    if config_b is None:
        config_b = {}
    changes: list[ParameterChange] = []
    shared_keys = set(config_a.keys()) & set(config_b.keys())
    for key in sorted(shared_keys):
        if config_a[key] != config_b[key]:
            changes.append(
                ParameterChange(field=key, old_value=config_a[key], new_value=config_b[key])
            )
    return changes


def _check_compatibility(
    row_a: dict[str, Any],
    row_b: dict[str, Any],
    config_a: dict[str, Any] | None = None,
    config_b: dict[str, Any] | None = None,
) -> str | None:
    warnings: list[str] = []
    strategy_a = row_a.get("strategy", "")
    strategy_b = row_b.get("strategy", "")
    if strategy_a != strategy_b:
        warnings.append(
            f"Incompatible strategy types: {strategy_a} vs {strategy_b}. "
            f"Results may not be directly comparable."
        )
    if config_a is None:
        config_a = _parse_json(row_a.get("config_json"))
    if config_b is None:
        config_b = _parse_json(row_b.get("config_json"))

    sym_a = config_a.get("symbol", "")
    sym_b = config_b.get("symbol", "")
    if sym_a and sym_b and sym_a != sym_b:
        warnings.append(f"Different underlying assets: {sym_a} vs {sym_b}.")

    int_a = config_a.get("interval", "")
    int_b = config_b.get("interval", "")
    if int_a and int_b and int_a != int_b:
        warnings.append(f"Different time intervals: {int_a} vs {int_b}.")

    return " | ".join(warnings) if warnings else None


def _detect_missing_sections(row: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if not row.get("metrics_json"):
        missing.append("metrics")
    if not row.get("config_json"):
        missing.append("config")
    return missing


def _has_positions(db: DatabaseReader, run_id: str) -> bool:
    rows = db._execute_read(
        "SELECT 1 FROM result_series WHERE run_id = ? AND series_type = 'positions' LIMIT 1",
        (run_id,),
    )
    return len(rows) > 0


def compare_runs(db: DatabaseReader, run_a: str, run_b: str) -> CompareResult:
    row_a = _get_experiment_row(db, run_a)
    row_b = _get_experiment_row(db, run_b)

    if row_a is None:
        raise ValueError(f"Run not found: {run_a}")
    if row_b is None:
        raise ValueError(f"Run not found: {run_b}")

    baseline, challenger = _determine_order(row_a, row_b)

    metrics_a = _parse_json(baseline.get("metrics_json"))
    metrics_b = _parse_json(challenger.get("metrics_json"))
    config_a = _parse_json(baseline.get("config_json"))
    config_b = _parse_json(challenger.get("config_json"))

    metrics_diff = _compute_metrics_diff(metrics_a, metrics_b)
    parameter_diff = _compute_parameter_diff_list(config_a, config_b)
    compatibility_warning = _check_compatibility(baseline, challenger, config_a, config_b)

    missing_sections: list[str] = []
    for row in (baseline, challenger):
        for section in _detect_missing_sections(row):
            if section not in missing_sections:
                missing_sections.append(section)

    for rid in (baseline["run_id"], challenger["run_id"]):
        if not _has_positions(db, rid) and "trades" not in missing_sections:
            missing_sections.append("trades")

    return CompareResult(
        metrics_diff=metrics_diff,
        parameter_diff=parameter_diff,
        compatibility_warning=compatibility_warning,
        baseline_id=baseline["run_id"],
        challenger_id=challenger["run_id"],
        missing_sections=missing_sections,
    )


def compare_trades(db: DatabaseReader, run_a: str, run_b: str) -> TradeAlignment:
    for rid in (run_a, run_b):
        row = _get_experiment_row(db, rid)
        if row is None:
            raise ValueError(f"Run not found: {rid}")

    def _load_positions(run_id: str) -> list[TradeRecord]:
        rows = db._execute_read(
            "SELECT ts, value FROM result_series "
            "WHERE run_id = ? AND series_type = 'positions' "
            "ORDER BY ts",
            (run_id,),
        )
        trades: list[TradeRecord] = []
        for row in rows:
            try:
                fv = float(row[1])
            except (IndexError, TypeError, ValueError):
                continue
            if not math.isfinite(fv):
                continue
            if fv > 0:
                side = "long"
            elif fv < 0:
                side = "short"
            else:
                side = "flat"
            trades.append(
                TradeRecord(timestamp=str(row[0]), side=side, quantity=abs(fv), price=None)
            )
        return trades

    return TradeAlignment(
        alignment_strategy="sequential",
        trades_a=_load_positions(run_a),
        trades_b=_load_positions(run_b),
    )
