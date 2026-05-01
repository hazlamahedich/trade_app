"""ATDD: Story 3.2 — Experiment Lineage DAG.

Tests assert the EXPECTED end-state for Story 3.2.
"""

from __future__ import annotations

import pytest


class TestStory32LineageDAG:
    """Story 3.2: Parent-child relationships between experiments."""

    @pytest.mark.test_id("3.2-ATDD-001")
    @pytest.mark.p0
    async def test_lineage_thread_shows_parent_child_chain(self, db_with_remix_chain):
        from trade_advisor.experiments.lineage import get_lineage

        child_run_id = db_with_remix_chain._child_run_id
        lineage = await get_lineage(db_with_remix_chain, child_run_id)
        assert len(lineage.nodes) >= 2
        assert lineage.nodes[0].run_id == db_with_remix_chain._parent_run_id
        assert lineage.nodes[-1].run_id == child_run_id

    @pytest.mark.test_id("3.2-ATDD-002")
    @pytest.mark.p0
    async def test_lineage_node_shows_run_id_and_key_metric(self, db_with_remix_chain):
        from trade_advisor.experiments.lineage import get_lineage

        child_run_id = db_with_remix_chain._child_run_id
        lineage = await get_lineage(db_with_remix_chain, child_run_id)
        node = lineage.nodes[0]
        assert node.run_id is not None
        assert node.key_metric is not None

    @pytest.mark.test_id("3.2-ATDD-003")
    @pytest.mark.p0
    async def test_lineage_node_shows_parameter_change_from_parent(self, db_with_remix_chain):
        from trade_advisor.experiments.lineage import get_lineage

        child_run_id = db_with_remix_chain._child_run_id
        lineage = await get_lineage(db_with_remix_chain, child_run_id)
        child_node = lineage.nodes[-1]
        assert child_node.parameter_diff is not None
        assert len(child_node.parameter_diff) > 0

    @pytest.mark.test_id("3.2-ATDD-004")
    @pytest.mark.p1
    async def test_lineage_node_shows_pre_mortem_prediction(self, db_with_remix_chain):
        from trade_advisor.experiments.lineage import get_lineage

        child_run_id = db_with_remix_chain._child_run_id
        lineage = await get_lineage(db_with_remix_chain, child_run_id)
        child_node = lineage.nodes[-1]
        assert child_node.pre_mortem is not None

    @pytest.mark.test_id("3.2-ATDD-005")
    @pytest.mark.p0
    async def test_lineage_is_immutable(self, db_with_remix_chain):
        from trade_advisor.experiments.lineage import get_lineage

        parent_id = db_with_remix_chain._parent_run_id
        lineage = await get_lineage(db_with_remix_chain, parent_id)
        for node in lineage.nodes:
            assert node.immutable is True

    @pytest.mark.test_id("3.2-ATDD-006")
    @pytest.mark.p0
    async def test_auto_narrative_appended_per_experiment(self, db_with_remix_chain):
        from trade_advisor.experiments.lineage import get_lineage

        child_run_id = db_with_remix_chain._child_run_id
        lineage = await get_lineage(db_with_remix_chain, child_run_id)
        child_node = lineage.nodes[-1]
        assert child_node.narrative is not None
        assert "Forked from" in child_node.narrative

    @pytest.mark.test_id("3.2-ATDD-007")
    @pytest.mark.p1
    async def test_fork_point_recorded(self, db_with_remix_chain):
        from trade_advisor.experiments.lineage import get_lineage

        child_run_id = db_with_remix_chain._child_run_id
        lineage = await get_lineage(db_with_remix_chain, child_run_id)
        assert lineage.edges is not None
        assert len(lineage.edges) >= 1
        edge = lineage.edges[0]
        assert edge.parent_id == db_with_remix_chain._parent_run_id
        assert edge.child_id == child_run_id

    @pytest.mark.test_id("3.2-ATDD-008")
    @pytest.mark.p2
    async def test_lineage_for_root_experiment_has_no_parent(self, db_with_remix_chain):
        from trade_advisor.experiments.lineage import get_lineage

        parent_id = db_with_remix_chain._parent_run_id
        lineage = await get_lineage(db_with_remix_chain, parent_id)
        root = lineage.nodes[0]
        assert root.parent_run_id is None

    @pytest.mark.test_id("3.2-ATDD-009")
    @pytest.mark.p2
    async def test_lineage_with_multiple_fork_depth(self, db_with_deep_remix_chain):
        from trade_advisor.experiments.lineage import get_lineage

        leaf_id = db_with_deep_remix_chain._leaf_run_id
        lineage = await get_lineage(db_with_deep_remix_chain, leaf_id)
        assert len(lineage.nodes) >= 3


class TestStory32LineageWebAPI:
    """Story 3.2: Web API routes for lineage."""

    @pytest.mark.test_id("3.2-ATDD-010")
    @pytest.mark.p0
    async def test_lineage_api_returns_dag(self, lineage_app_client, db_with_remix_chain):
        child_id = db_with_remix_chain._child_run_id
        response = await lineage_app_client.get(f"/api/experiments/{child_id}/lineage")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data

    @pytest.mark.test_id("3.2-ATDD-011")
    @pytest.mark.p1
    async def test_lineage_api_404_for_unknown_run(self, app_client):
        response = await app_client.get("/api/experiments/nonexistent/lineage")
        assert response.status_code == 404
