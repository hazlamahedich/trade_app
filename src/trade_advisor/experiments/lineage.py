"""Experiment lineage DAG — parent-child chain traversal and parameter diff.

Walks the ``parent_run_id`` chain from a target experiment back to the root,
then reverses to chronological (oldest-first) order. Each node carries a
parameter diff computed against its immediate parent.

Source of truth: ``experiments.parent_run_id`` column in DuckDB.
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from trade_advisor.infra.protocols import DatabaseReader

log = logging.getLogger(__name__)

_MAX_DEPTH = 20


class LineageNode(BaseModel):
    run_id: str
    parent_run_id: str | None = None
    strategy: str = ""
    key_metric: float | None = None
    parameter_diff: dict[str, dict[str, Any]] = {}
    pre_mortem: str | None = None
    narrative: str | None = None
    immutable: bool = True
    created_at: datetime | None = None


class LineageEdge(BaseModel):
    parent_id: str
    child_id: str


class LineageResult(BaseModel):
    nodes: list[LineageNode]
    edges: list[LineageEdge]
    truncated: bool = False


def _extract_key_metric(metrics_json: str | None) -> float | None:
    if not metrics_json:
        return None
    try:
        data = json.loads(metrics_json)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    for key in ("sharpe", "total_return"):
        val = data.get(key)
        if val is not None:
            try:
                f = float(val)
            except (TypeError, ValueError):
                continue
            if math.isfinite(f):
                return f
    return None


def _compute_parameter_diff(
    parent_config: dict[str, Any], child_config: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    diff: dict[str, dict[str, Any]] = {}
    all_keys = set(parent_config.keys()) & set(child_config.keys())
    for key in all_keys:
        pval = parent_config[key]
        cval = child_config[key]
        if pval != cval:
            diff[key] = {"old": pval, "new": cval}
    return diff


def _parse_json_config(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return {}


def _build_narrative(
    node_id: str,
    parent_id: str | None,
    param_diff: dict[str, dict[str, Any]],
    parent_metric: float | None,
    child_metric: float | None,
) -> str:
    if not parent_id:
        return f"Root experiment {node_id[:12]}."
    parts = [f"Forked from run {parent_id[:12]}"]
    if param_diff:
        changes = ", ".join(f"{k} {v['old']}\u2192{v['new']}" for k, v in param_diff.items())
        parts.append(f"changed {changes}")
    if parent_metric is not None and child_metric is not None:
        parts.append(
            f"Result: Sharpe {'improved' if child_metric > parent_metric else 'changed'} "
            f"{parent_metric:.2f}\u2192{child_metric:.2f}"
        )
    return ". ".join(parts) + "."


async def get_lineage(db: DatabaseReader, run_id: str) -> LineageResult:
    rows: list[tuple[Any, ...]] = []
    current_id: str | None = run_id
    visited: set[str] = set()
    metric_map: dict[str, float | None] = {}
    config_map: dict[str, dict[str, Any]] = {}

    while current_id and current_id not in visited and len(rows) < _MAX_DEPTH:
        visited.add(current_id)
        result = await db.read(
            "SELECT run_id, parent_run_id, strategy, metrics_json, config_json, "
            "pre_mortem, narrative, created_at, status "
            "FROM experiments WHERE run_id = ?",
            (current_id,),
        )
        if not result:
            break
        rows.append(result[0])
        row = result[0]
        rid = row[0]
        metric_map[rid] = _extract_key_metric(row[3])
        config_map[rid] = _parse_json_config(row[4])
        current_id = row[1]
        if current_id and current_id in visited:
            log.warning("lineage cycle detected at %s", current_id)
            break

    truncated = len(rows) >= _MAX_DEPTH and current_id is not None
    if truncated:
        log.warning(
            "lineage truncated at %d nodes; ancestor %s not visited",
            _MAX_DEPTH,
            current_id,
        )

    rows.reverse()

    nodes: list[LineageNode] = []
    edges: list[LineageEdge] = []

    for row in rows:
        (
            rid,
            parent_rid,
            strategy,
            _metrics_raw,
            _config_raw,
            pre_mortem,
            narrative_raw,
            created_at,
            status,
        ) = row
        param_diff: dict[str, dict[str, Any]] = {}
        if parent_rid and parent_rid in config_map:
            param_diff = _compute_parameter_diff(config_map[parent_rid], config_map[rid])

        child_metric = metric_map.get(rid)
        parent_metric = metric_map.get(parent_rid) if parent_rid else None
        narrative = _build_narrative(rid, parent_rid, param_diff, parent_metric, child_metric)

        if narrative_raw:
            narrative = narrative_raw

        nodes.append(
            LineageNode(
                run_id=rid,
                parent_run_id=parent_rid,
                strategy=strategy,
                key_metric=child_metric,
                parameter_diff=param_diff,
                pre_mortem=pre_mortem,
                narrative=narrative,
                immutable=(status or "running") == "completed",
                created_at=created_at,
            )
        )

        if parent_rid:
            edges.append(LineageEdge(parent_id=parent_rid, child_id=rid))

    return LineageResult(nodes=nodes, edges=edges, truncated=truncated)


async def check_mutability(db: DatabaseReader, run_id: str) -> bool:
    rows = await db.read(
        "SELECT status FROM experiments WHERE run_id = ?",
        (run_id,),
    )
    if not rows:
        return False
    status: str | None = rows[0][0]
    return (status or "running") != "completed"
