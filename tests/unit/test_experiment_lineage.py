"""Unit tests for experiments/lineage.py — Story 3.2.

Six levels:
  A — get_lineage unit tests
  B — parameter_diff computation
  C — key_metric extraction
  D — immutability enforcement
  E — Web API integration
  F — Edge cases
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from trade_advisor.experiments.lineage import (
    LineageEdge,
    LineageNode,
    LineageResult,
    _compute_parameter_diff,
    _extract_key_metric,
    _parse_json_config,
    check_mutability,
    get_lineage,
)

# ── Helpers ──────────────────────────────────────────────────────────────


async def _make_db(
    records: list[dict],
    configs: dict[str, dict] | None = None,
) -> object:
    from trade_advisor.core.config import DatabaseConfig
    from trade_advisor.experiments.tracker import ExperimentRecord, ExperimentRepository
    from trade_advisor.infra.db import DatabaseManager

    config = DatabaseConfig(path=":memory:")
    db = DatabaseManager(config)
    now = datetime.now(UTC)
    db = await db.__aenter__()
    for r in records:
        rec = ExperimentRecord(
            run_id=r["run_id"],
            config_hash=r.get("config_hash", "hash"),
            strategy=r.get("strategy", "SmaCross"),
            metrics_json=r.get("metrics_json"),
            seed=r.get("seed", 42),
            status=r.get("status", "completed"),
            parent_run_id=r.get("parent_run_id"),
            pre_mortem=r.get("pre_mortem"),
            narrative=r.get("narrative"),
            created_at=r.get("created_at", now),
            completed_at=r.get("created_at", now),
        )
        await ExperimentRepository.store_run(db, rec)

    if configs:
        for run_id, cfg in configs.items():
            await db.write(
                "UPDATE experiments SET config_json = ? WHERE run_id = ?",
                (json.dumps(cfg), run_id),
            )
    return db


# ── Level A: get_lineage unit tests ──────────────────────────────────────


class TestGetLineage:
    @pytest.mark.asyncio
    async def test_parent_child_chain(self):
        db = await _make_db(
            [
                {"run_id": "run_a", "metrics_json": json.dumps({"sharpe": 0.8})},
                {
                    "run_id": "run_b",
                    "parent_run_id": "run_a",
                    "metrics_json": json.dumps({"sharpe": 1.1}),
                },
            ],
            configs={"run_a": {"fast": 14}, "run_b": {"fast": 20}},
        )
        result = await get_lineage(db, "run_b")
        assert len(result.nodes) == 2
        assert result.nodes[0].run_id == "run_a"
        assert result.nodes[1].run_id == "run_b"
        assert result.nodes[0].parent_run_id is None
        assert result.nodes[1].parent_run_id == "run_a"

    @pytest.mark.asyncio
    async def test_root_node_no_parent(self):
        db = await _make_db(
            [{"run_id": "run_root", "metrics_json": json.dumps({"sharpe": 0.5})}],
        )
        result = await get_lineage(db, "run_root")
        assert len(result.nodes) == 1
        assert result.nodes[0].parent_run_id is None
        assert result.edges == []

    @pytest.mark.asyncio
    async def test_deep_chain_three_levels(self):
        db = await _make_db(
            [
                {"run_id": "r1", "metrics_json": json.dumps({"sharpe": 0.3})},
                {
                    "run_id": "r2",
                    "parent_run_id": "r1",
                    "metrics_json": json.dumps({"sharpe": 0.6}),
                },
                {
                    "run_id": "r3",
                    "parent_run_id": "r2",
                    "metrics_json": json.dumps({"sharpe": 0.9}),
                },
            ],
            configs={"r1": {"fast": 10}, "r2": {"fast": 14}, "r3": {"fast": 20}},
        )
        result = await get_lineage(db, "r3")
        assert len(result.nodes) == 3
        assert [n.run_id for n in result.nodes] == ["r1", "r2", "r3"]
        assert len(result.edges) == 2

    @pytest.mark.asyncio
    async def test_nonexistent_run_id(self):
        db = await _make_db([])
        result = await get_lineage(db, "ghost_run")
        assert result.nodes == []
        assert result.edges == []

    @pytest.mark.asyncio
    async def test_nodes_chronological_order(self):
        now = datetime.now(UTC)
        from datetime import timedelta

        db = await _make_db(
            [
                {"run_id": "old", "created_at": now - timedelta(days=2)},
                {"run_id": "mid", "parent_run_id": "old", "created_at": now - timedelta(days=1)},
                {"run_id": "new", "parent_run_id": "mid", "created_at": now},
            ],
        )
        result = await get_lineage(db, "new")
        ids = [n.run_id for n in result.nodes]
        assert ids == ["old", "mid", "new"]


# ── Level B: parameter_diff computation ──────────────────────────────────


class TestParameterDiff:
    def test_changed_params_only(self):
        diff = _compute_parameter_diff({"fast": 14, "slow": 50}, {"fast": 20, "slow": 50})
        assert diff == {"fast": {"old": 14, "new": 20}}

    def test_no_changes(self):
        diff = _compute_parameter_diff({"fast": 14}, {"fast": 14})
        assert diff == {}

    def test_multiple_changes(self):
        diff = _compute_parameter_diff({"fast": 14, "slow": 50}, {"fast": 20, "slow": 100})
        assert len(diff) == 2
        assert diff["fast"] == {"old": 14, "new": 20}
        assert diff["slow"] == {"old": 50, "new": 100}

    def test_type_mismatch(self):
        diff = _compute_parameter_diff({"fast": 14}, {"fast": "50"})
        assert "fast" in diff

    def test_missing_config_on_parent(self):
        diff = _compute_parameter_diff({}, {"fast": 20})
        assert diff == {}

    def test_asymmetric_keys_child_only(self):
        diff = _compute_parameter_diff({"fast": 14}, {"fast": 14, "slow": 50})
        assert diff == {}

    def test_asymmetric_keys_parent_only(self):
        diff = _compute_parameter_diff({"fast": 14, "slow": 50}, {"fast": 14})
        assert diff == {}


# ── Level C: key_metric extraction ───────────────────────────────────────


class TestKeyMetricExtraction:
    def test_sharpe_present(self):
        assert _extract_key_metric(json.dumps({"sharpe": 1.5, "total_return": 0.2})) == 1.5

    def test_sharpe_missing_falls_back_to_total_return(self):
        assert _extract_key_metric(json.dumps({"total_return": 0.2})) == 0.2

    def test_both_missing(self):
        assert _extract_key_metric(json.dumps({"max_drawdown": -0.1})) is None

    def test_none_input(self):
        assert _extract_key_metric(None) is None

    def test_empty_string(self):
        assert _extract_key_metric("") is None

    def test_malformed_json(self):
        assert _extract_key_metric("not json") is None

    def test_nan_value(self):
        assert _extract_key_metric(json.dumps({"sharpe": float("nan")})) is None

    def test_inf_value(self):
        assert _extract_key_metric(json.dumps({"sharpe": float("inf")})) is None

    def test_negative_inf_value(self):
        assert _extract_key_metric(json.dumps({"sharpe": float("-inf")})) is None

    def test_empty_json_string(self):
        assert _extract_key_metric("{}") is None

    def test_sharpe_zero(self):
        assert _extract_key_metric(json.dumps({"sharpe": 0.0})) == 0.0


# ── Level D: immutability enforcement ────────────────────────────────────


class TestImmutability:
    @pytest.mark.asyncio
    async def test_completed_returns_false(self):
        db = await _make_db([{"run_id": "r1", "status": "completed"}])
        assert await check_mutability(db, "r1") is False

    @pytest.mark.asyncio
    async def test_running_returns_true(self):
        db = await _make_db([{"run_id": "r2", "status": "running"}])
        assert await check_mutability(db, "r2") is True

    @pytest.mark.asyncio
    async def test_nonexistent_run_id(self):
        db = await _make_db([])
        assert await check_mutability(db, "ghost") is False


# ── Level E: Web API integration ─────────────────────────────────────────


class TestLineageWebAPI:
    @pytest.mark.asyncio
    async def test_api_200_with_valid_data(self):
        from httpx import ASGITransport, AsyncClient

        from trade_advisor.core.config import DatabaseConfig
        from trade_advisor.experiments.tracker import ExperimentRecord, ExperimentRepository
        from trade_advisor.infra.db import DatabaseManager

        config = DatabaseConfig(path=":memory:")
        db = DatabaseManager(config)
        now = datetime.now(UTC)
        db = await db.__aenter__()
        await ExperimentRepository.store_run(
            db,
            ExperimentRecord(
                run_id="api_r1",
                config_hash="h",
                strategy="SmaCross",
                metrics_json=json.dumps({"sharpe": 0.8}),
                seed=42,
                created_at=now,
                completed_at=now,
            ),
        )
        await db.write(
            "UPDATE experiments SET config_json = ? WHERE run_id = ?",
            (json.dumps({"fast": 14}), "api_r1"),
        )

        from trade_advisor.main import app

        orig = getattr(app.state, "db", None)
        app.state.db = db
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/experiments/api_r1/lineage")
                assert resp.status_code == 200
                data = resp.json()
                assert "nodes" in data
                assert len(data["nodes"]) == 1
        finally:
            app.state.db = orig

    @pytest.mark.asyncio
    async def test_api_404_unknown_run(self):
        from httpx import ASGITransport, AsyncClient

        from trade_advisor.core.config import DatabaseConfig
        from trade_advisor.infra.db import DatabaseManager

        config = DatabaseConfig(path=":memory:")
        db = DatabaseManager(config)
        db = await db.__aenter__()

        from trade_advisor.main import app

        orig = getattr(app.state, "db", None)
        app.state.db = db
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/experiments/no_such_run/lineage")
                assert resp.status_code == 404
        finally:
            app.state.db = orig

    @pytest.mark.asyncio
    async def test_api_with_remix_chain(self):
        from httpx import ASGITransport, AsyncClient

        from trade_advisor.core.config import DatabaseConfig
        from trade_advisor.experiments.tracker import ExperimentRecord, ExperimentRepository
        from trade_advisor.infra.db import DatabaseManager

        config = DatabaseConfig(path=":memory:")
        db = DatabaseManager(config)
        now = datetime.now(UTC)
        db = await db.__aenter__()
        for rid, pid in [("p1", None), ("c1", "p1")]:
            await ExperimentRepository.store_run(
                db,
                ExperimentRecord(
                    run_id=rid,
                    config_hash="h",
                    strategy="SmaCross",
                    metrics_json=json.dumps({"sharpe": 0.8}),
                    seed=42,
                    parent_run_id=pid,
                    created_at=now,
                    completed_at=now,
                ),
            )
            await db.write(
                "UPDATE experiments SET config_json = ? WHERE run_id = ?",
                (json.dumps({"fast": 14 if rid == "p1" else 20}), rid),
            )

        from trade_advisor.main import app

        orig = getattr(app.state, "db", None)
        app.state.db = db
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/experiments/c1/lineage")
                assert resp.status_code == 200
                data = resp.json()
                assert len(data["nodes"]) == 2
                assert len(data["edges"]) == 1
        finally:
            app.state.db = orig


# ── Level F: Edge cases ──────────────────────────────────────────────────


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_orphan_run_partial_lineage(self):
        db = await _make_db(
            [
                {"run_id": "orphan_child", "parent_run_id": "deleted_parent"},
            ],
            configs={"orphan_child": {"fast": 20}},
        )
        result = await get_lineage(db, "orphan_child")
        assert len(result.nodes) == 1
        assert result.nodes[0].run_id == "orphan_child"
        assert result.nodes[0].parameter_diff == {}

    @pytest.mark.asyncio
    async def test_empty_metrics_json(self):
        db = await _make_db(
            [{"run_id": "r1", "metrics_json": ""}],
        )
        result = await get_lineage(db, "r1")
        assert len(result.nodes) == 1
        assert result.nodes[0].key_metric is None

    @pytest.mark.asyncio
    async def test_config_json_none(self):
        db = await _make_db(
            [
                {"run_id": "r1"},
                {"run_id": "r2", "parent_run_id": "r1"},
            ],
        )
        result = await get_lineage(db, "r2")
        assert len(result.nodes) == 2
        child = result.nodes[1]
        assert child.parameter_diff == {}

    @pytest.mark.asyncio
    async def test_single_node_lineage(self):
        db = await _make_db(
            [{"run_id": "solo", "metrics_json": json.dumps({"sharpe": 1.0})}],
        )
        result = await get_lineage(db, "solo")
        assert len(result.nodes) == 1
        assert result.edges == []

    @pytest.mark.asyncio
    async def test_circular_reference_detected(self, caplog):
        import logging

        with caplog.at_level(logging.WARNING, logger="trade_advisor.experiments.lineage"):
            db = await _make_db(
                [
                    {"run_id": "circ_a", "parent_run_id": "circ_b"},
                    {"run_id": "circ_b", "parent_run_id": "circ_a"},
                ],
            )
            result = await get_lineage(db, "circ_a")
            assert len(result.nodes) >= 1
            assert any("cycle" in r.message.lower() for r in caplog.records)

    def test_parse_json_config_none(self):
        assert _parse_json_config(None) == {}

    def test_parse_json_config_empty(self):
        assert _parse_json_config("") == {}

    def test_parse_json_config_invalid(self):
        assert _parse_json_config("not json") == {}

    def test_parse_json_config_valid(self):
        assert _parse_json_config('{"fast": 14}') == {"fast": 14}

    def test_lineage_node_model(self):
        node = LineageNode(
            run_id="test_run",
            parent_run_id=None,
            strategy="SmaCross",
            key_metric=1.5,
            parameter_diff={},
            pre_mortem="test",
            narrative="test",
            immutable=True,
        )
        assert node.run_id == "test_run"
        assert node.immutable is True

    def test_lineage_edge_model(self):
        edge = LineageEdge(parent_id="p1", child_id="c1")
        assert edge.parent_id == "p1"
        assert edge.child_id == "c1"

    def test_lineage_result_model(self):
        result = LineageResult(
            nodes=[LineageNode(run_id="r1")],
            edges=[LineageEdge(parent_id="r0", child_id="r1")],
        )
        assert len(result.nodes) == 1
        assert len(result.edges) == 1

    @pytest.mark.asyncio
    async def test_narrative_starts_with_forked(self):
        db = await _make_db(
            [
                {"run_id": "np1", "metrics_json": json.dumps({"sharpe": 0.8})},
                {
                    "run_id": "np2",
                    "parent_run_id": "np1",
                    "metrics_json": json.dumps({"sharpe": 1.1}),
                },
            ],
            configs={"np1": {"fast": 14}, "np2": {"fast": 20}},
        )
        result = await get_lineage(db, "np2")
        child_narrative = result.nodes[1].narrative
        assert child_narrative is not None
        assert child_narrative.startswith("Forked from run")

    @pytest.mark.asyncio
    async def test_narrative_includes_sharpe_comparison(self):
        db = await _make_db(
            [
                {"run_id": "sp1", "metrics_json": json.dumps({"sharpe": 0.8})},
                {
                    "run_id": "sp2",
                    "parent_run_id": "sp1",
                    "metrics_json": json.dumps({"sharpe": 1.1}),
                },
            ],
            configs={"sp1": {"fast": 14}, "sp2": {"fast": 20}},
        )
        result = await get_lineage(db, "sp2")
        child_narrative = result.nodes[1].narrative
        assert "Sharpe" in child_narrative
        assert "0.80" in child_narrative
        assert "1.10" in child_narrative

    @pytest.mark.asyncio
    async def test_root_narrative(self):
        db = await _make_db(
            [{"run_id": "root1", "metrics_json": json.dumps({"sharpe": 0.5})}],
        )
        result = await get_lineage(db, "root1")
        assert result.nodes[0].narrative is not None
        assert "Root experiment" in result.nodes[0].narrative

    @pytest.mark.asyncio
    async def test_stored_narrative_preserved(self):
        db = await _make_db(
            [
                {"run_id": "sn1", "narrative": "Custom narrative text"},
            ],
        )
        result = await get_lineage(db, "sn1")
        assert result.nodes[0].narrative == "Custom narrative text"
