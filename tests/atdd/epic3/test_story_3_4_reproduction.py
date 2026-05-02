"""ATDD: Story 3.4 — Run Retrieval & Full Reproduction.

Tests assert the EXPECTED end-state for Story 3.4.
"""

from __future__ import annotations

import pandas as pd
import pytest


class TestStory34RunReproduction:
    """Story 3.4: One-click reproduction of any historical experiment run."""

    @pytest.mark.test_id("3.4-ATDD-001")
    @pytest.mark.p0
    def test_reproduce_loads_stored_config_seed_and_fingerprint(self, db_with_completed_run):
        # Given: a database with a completed run
        db, ctx = db_with_completed_run
        from trade_advisor.experiments.reproduction import load_run_for_reproduction

        # When: loading the run for reproduction
        spec = load_run_for_reproduction(db, ctx.run_id)

        # Then: spec has config, seed, and data_fingerprint
        assert spec is not None
        assert spec.config is not None
        assert spec.seed is not None
        assert spec.data_fingerprint is not None

    @pytest.mark.test_id("3.4-ATDD-002")
    @pytest.mark.p0
    async def test_reproduce_executes_with_identical_parameters(self, db_with_completed_run):
        # Given: a database with a completed run
        db, ctx = db_with_completed_run
        from trade_advisor.experiments.reproduction import reproduce_run

        # When: reproducing the run
        new_result = await reproduce_run(db, ctx.run_id)

        # Then: a new run is created with a different ID
        assert new_result is not None
        assert new_result.run_id != ctx.run_id

    @pytest.mark.test_id("3.4-ATDD-003")
    @pytest.mark.p0
    async def test_reproduced_result_matches_original_within_tolerance(self, db_with_completed_run):
        # Given: a database with a completed run and original equity
        db, ctx = db_with_completed_run
        from trade_advisor.experiments.reproduction import reproduce_run

        # When: reproducing the run
        new_result = await reproduce_run(db, ctx.run_id)

        # Then: equity matches original within 1e-10 tolerance
        original = ctx.original_equity
        pd.testing.assert_series_equal(
            new_result.equity.reset_index(drop=True),
            original.reset_index(drop=True),
            atol=1e-10,
        )

    @pytest.mark.test_id("3.4-ATDD-004")
    @pytest.mark.p0
    def test_data_snapshot_change_shows_warning(self, db_with_stale_fingerprint):
        # Given: a database with a run whose data fingerprint is stale
        db, ctx = db_with_stale_fingerprint
        from trade_advisor.experiments.reproduction import check_data_freshness

        # When: checking data freshness
        freshness = check_data_freshness(db, ctx.run_id)

        # Then: freshness indicates change with a warning
        assert freshness.has_changed is True
        assert freshness.warning is not None

    @pytest.mark.test_id("3.4-ATDD-005")
    @pytest.mark.p0
    async def test_reproduced_run_linked_via_lineage(self, db_with_completed_run):
        # Given: a database with a completed run
        db, ctx = db_with_completed_run
        from trade_advisor.experiments.reproduction import reproduce_run

        # When: reproducing the run
        new_result = await reproduce_run(db, ctx.run_id)

        # Then: new run is linked to original via parent_run_id
        assert new_result.parent_run_id == ctx.run_id

    @pytest.mark.test_id("3.4-ATDD-006")
    @pytest.mark.p1
    def test_reproduce_preserves_deterministic_run_id(self, db_with_completed_run):
        # Given: a database with a completed run
        _db, ctx = db_with_completed_run
        from trade_advisor.experiments.tracker import HashedRunInputs, generate_run_id

        # When: regenerating run ID from same inputs
        inputs = HashedRunInputs(
            config=ctx.config,
            data_fingerprint=ctx.data_fingerprint,
            code_version=ctx.code_version,
        )
        reproduced_id = generate_run_id(inputs)

        # Then: generated ID matches original
        assert reproduced_id == ctx.run_id

    @pytest.mark.test_id("3.4-ATDD-007")
    @pytest.mark.p1
    def test_reproduce_unknown_run_raises(self, db_with_completed_run):
        # Given: a database with a completed run
        db, _ctx = db_with_completed_run
        from trade_advisor.experiments.reproduction import (
            ReproductionError,
            load_run_for_reproduction,
        )

        # When/Then: loading a nonexistent run raises ReproductionError
        with pytest.raises(ReproductionError):
            load_run_for_reproduction(db, "nonexistent_run")

    @pytest.mark.test_id("3.4-ATDD-008")
    @pytest.mark.p2
    async def test_reproduce_chain_preserves_full_lineage(self, db_with_completed_run):
        # Given: a database with a completed run
        db, ctx = db_with_completed_run
        from trade_advisor.experiments.reproduction import reproduce_run

        # When: reproducing twice (chain of 3)
        gen1 = await reproduce_run(db, ctx.run_id)
        gen2 = await reproduce_run(db, gen1.run_id)

        # Then: each generation links to its parent
        assert gen2.parent_run_id == gen1.run_id
        assert gen1.parent_run_id == ctx.run_id


class TestStory34ReproductionWebAPI:
    """Story 3.4: Web API routes for run reproduction."""

    @pytest.mark.test_id("3.4-ATDD-009")
    @pytest.mark.p0
    async def test_reproduce_api_returns_new_run(self, repro_app_client, db_with_completed_run):
        # Given: a running app with a completed run
        _db, ctx = db_with_completed_run
        # When: posting reproduce request
        response = await repro_app_client.post(f"/api/experiments/{ctx.run_id}/reproduce")
        # Then: new run is returned linked to original
        assert response.status_code in (200, 202)
        data = response.json()
        assert data["run_id"] != ctx.run_id
        assert data["parent_run_id"] == ctx.run_id

    @pytest.mark.test_id("3.4-ATDD-010")
    @pytest.mark.p0
    async def test_reproduce_api_404_for_unknown_run(self, app_client):
        # Given: a running app
        # When: reproducing a nonexistent run
        response = await app_client.post("/api/experiments/nonexistent/reproduce")
        # Then: 404 is returned
        assert response.status_code == 404

    @pytest.mark.test_id("3.4-ATDD-011")
    @pytest.mark.p1
    async def test_reproduce_api_warns_on_stale_data(
        self, stale_app_client, db_with_stale_fingerprint
    ):
        # Given: a running app with a run whose data is stale
        _db, ctx = db_with_stale_fingerprint
        # When: reproducing the stale run
        response = await stale_app_client.post(f"/api/experiments/{ctx.run_id}/reproduce")
        # Then: response includes a data freshness warning
        data = response.json()
        assert data.get("data_freshness_warning") is not None
