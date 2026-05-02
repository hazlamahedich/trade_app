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
        # Given: a database with a parent-child experiment chain
        db, ctx = db_with_remix_chain
        from trade_advisor.experiments.lineage import get_lineage

        # When: fetching lineage for the child run
        lineage = await get_lineage(db, ctx.child_run_id)

        # Then: lineage contains at least 2 nodes, parent first, child last
        assert len(lineage.nodes) >= 2
        assert lineage.nodes[0].run_id == ctx.parent_run_id
        assert lineage.nodes[-1].run_id == ctx.child_run_id

    @pytest.mark.test_id("3.2-ATDD-002")
    @pytest.mark.p0
    async def test_lineage_node_shows_run_id_and_key_metric(self, db_with_remix_chain):
        # Given: a database with a lineage chain
        db, ctx = db_with_remix_chain
        from trade_advisor.experiments.lineage import get_lineage

        # When: fetching lineage
        lineage = await get_lineage(db, ctx.child_run_id)

        # Then: each node has run_id and key_metric
        node = lineage.nodes[0]
        assert node.run_id is not None
        assert node.key_metric is not None

    @pytest.mark.test_id("3.2-ATDD-003")
    @pytest.mark.p0
    async def test_lineage_node_shows_parameter_change_from_parent(self, db_with_remix_chain):
        # Given: a database with a parent-child chain where params differ
        db, ctx = db_with_remix_chain
        from trade_advisor.experiments.lineage import get_lineage

        # When: fetching lineage for the child
        lineage = await get_lineage(db, ctx.child_run_id)

        # Then: child node shows parameter diff from parent
        child_node = lineage.nodes[-1]
        assert child_node.parameter_diff is not None
        assert len(child_node.parameter_diff) > 0

    @pytest.mark.test_id("3.2-ATDD-004")
    @pytest.mark.p1
    async def test_lineage_node_shows_pre_mortem_prediction(self, db_with_remix_chain):
        # Given: a database with experiments that have pre-mortem predictions
        db, ctx = db_with_remix_chain
        from trade_advisor.experiments.lineage import get_lineage

        # When: fetching lineage for the child
        lineage = await get_lineage(db, ctx.child_run_id)

        # Then: child node includes pre-mortem
        child_node = lineage.nodes[-1]
        assert child_node.pre_mortem is not None

    @pytest.mark.test_id("3.2-ATDD-005")
    @pytest.mark.p0
    async def test_lineage_is_immutable(self, db_with_remix_chain):
        # Given: a database with a lineage chain
        db, ctx = db_with_remix_chain
        from trade_advisor.experiments.lineage import get_lineage

        # When: fetching lineage for the parent
        lineage = await get_lineage(db, ctx.parent_run_id)

        # Then: all nodes are marked immutable
        for node in lineage.nodes:
            assert node.immutable is True

    @pytest.mark.test_id("3.2-ATDD-006")
    @pytest.mark.p0
    async def test_auto_narrative_appended_per_experiment(self, db_with_remix_chain):
        # Given: a database with a child forked from a parent
        db, ctx = db_with_remix_chain
        from trade_advisor.experiments.lineage import get_lineage

        # When: fetching lineage for the child
        lineage = await get_lineage(db, ctx.child_run_id)

        # Then: child node narrative mentions fork
        child_node = lineage.nodes[-1]
        assert child_node.narrative is not None
        assert "Forked from" in child_node.narrative

    @pytest.mark.test_id("3.2-ATDD-007")
    @pytest.mark.p1
    async def test_fork_point_recorded(self, db_with_remix_chain):
        # Given: a database with a parent-child fork
        db, ctx = db_with_remix_chain
        from trade_advisor.experiments.lineage import get_lineage

        # When: fetching lineage for the child
        lineage = await get_lineage(db, ctx.child_run_id)

        # Then: edges record the fork relationship
        assert lineage.edges is not None
        assert len(lineage.edges) >= 1
        edge = lineage.edges[0]
        assert edge.parent_id == ctx.parent_run_id
        assert edge.child_id == ctx.child_run_id

    @pytest.mark.test_id("3.2-ATDD-008")
    @pytest.mark.p2
    async def test_lineage_for_root_experiment_has_no_parent(self, db_with_remix_chain):
        # Given: a database with a lineage chain
        db, ctx = db_with_remix_chain
        from trade_advisor.experiments.lineage import get_lineage

        # When: fetching lineage for the root (parent)
        lineage = await get_lineage(db, ctx.parent_run_id)

        # Then: root node has no parent_run_id
        root = lineage.nodes[0]
        assert root.parent_run_id is None

    @pytest.mark.test_id("3.2-ATDD-009")
    @pytest.mark.p2
    async def test_lineage_with_multiple_fork_depth(self, db_with_deep_remix_chain):
        # Given: a database with a 3-level deep remix chain
        db, ctx = db_with_deep_remix_chain
        from trade_advisor.experiments.lineage import get_lineage

        # When: fetching lineage for the leaf node
        lineage = await get_lineage(db, ctx.leaf_run_id)

        # Then: lineage contains at least 3 nodes
        assert len(lineage.nodes) >= 3


class TestStory32LineageWebAPI:
    """Story 3.2: Web API routes for lineage."""

    @pytest.mark.test_id("3.2-ATDD-010")
    @pytest.mark.p0
    async def test_lineage_api_returns_dag(self, lineage_app_client, db_with_remix_chain):
        # Given: a running app with a remix chain
        _db, ctx = db_with_remix_chain
        # When: requesting lineage via API for the child
        response = await lineage_app_client.get(f"/api/experiments/{ctx.child_run_id}/lineage")
        # Then: response includes nodes and edges
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data

    @pytest.mark.test_id("3.2-ATDD-011")
    @pytest.mark.p1
    async def test_lineage_api_404_for_unknown_run(self, app_client):
        # Given: a running app
        # When: requesting lineage for a nonexistent run
        response = await app_client.get("/api/experiments/nonexistent/lineage")
        # Then: 404 is returned
        assert response.status_code == 404
