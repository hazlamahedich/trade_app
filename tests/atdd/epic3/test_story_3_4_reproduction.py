"""ATDD: Story 3.4 — Run Retrieval & Full Reproduction.

Red-phase scaffolds. Tests assert the EXPECTED end-state for Story 3.4.
All tests are marked pytest.mark.skip until the feature is implemented.
"""

from __future__ import annotations

import pytest


class TestStory34RunReproduction:
    """Story 3.4: One-click reproduction of any historical experiment run."""

    @pytest.mark.test_id("3.4-ATDD-001")
    @pytest.mark.p0
    @pytest.mark.skip(reason="RED: Story 3.4 not implemented")
    def test_reproduce_loads_stored_config_seed_and_fingerprint(
        self, db_with_completed_run
    ):
        from trade_advisor.experiments.reproduction import load_run_for_reproduction

        run_id = db_with_completed_run._run_id
        spec = load_run_for_reproduction(db_with_completed_run, run_id)
        assert spec is not None
        assert spec.config is not None
        assert spec.seed is not None
        assert spec.data_fingerprint is not None

    @pytest.mark.test_id("3.4-ATDD-002")
    @pytest.mark.p0
    @pytest.mark.skip(reason="RED: Story 3.4 not implemented")
    def test_reproduce_executes_with_identical_parameters(
        self, db_with_completed_run
    ):
        from trade_advisor.experiments.reproduction import reproduce_run

        run_id = db_with_completed_run._run_id
        new_result = reproduce_run(db_with_completed_run, run_id)
        assert new_result is not None
        assert new_result.run_id != run_id

    @pytest.mark.test_id("3.4-ATDD-003")
    @pytest.mark.p0
    @pytest.mark.skip(reason="RED: Story 3.4 not implemented")
    def test_reproduced_result_matches_original_within_tolerance(
        self, db_with_completed_run
    ):
        from trade_advisor.experiments.reproduction import reproduce_run

        run_id = db_with_completed_run._run_id
        original = db_with_completed_run._original_equity
        new_result = reproduce_run(db_with_completed_run, run_id)
        pd.testing.assert_series_equal(
            new_result.equity.reset_index(drop=True),
            original.reset_index(drop=True),
            atol=1e-10,
        )

    @pytest.mark.test_id("3.4-ATDD-004")
    @pytest.mark.p0
    @pytest.mark.skip(reason="RED: Story 3.4 not implemented")
    def test_data_snapshot_change_shows_warning(self, db_with_stale_fingerprint):
        from trade_advisor.experiments.reproduction import check_data_freshness

        run_id = db_with_stale_fingerprint._run_id
        freshness = check_data_freshness(db_with_stale_fingerprint, run_id)
        assert freshness.has_changed is True
        assert freshness.warning is not None

    @pytest.mark.test_id("3.4-ATDD-005")
    @pytest.mark.p0
    @pytest.mark.skip(reason="RED: Story 3.4 not implemented")
    def test_reproduced_run_linked_via_lineage(self, db_with_completed_run):
        from trade_advisor.experiments.reproduction import reproduce_run

        run_id = db_with_completed_run._run_id
        new_result = reproduce_run(db_with_completed_run, run_id)
        assert new_result.parent_run_id == run_id

    @pytest.mark.test_id("3.4-ATDD-006")
    @pytest.mark.p1
    @pytest.mark.skip(reason="RED: Story 3.4 not implemented")
    def test_reproduce_preserves_deterministic_run_id(self, db_with_completed_run):
        from trade_advisor.experiments.tracker import generate_run_id, HashedRunInputs

        original_run_id = db_with_completed_run._run_id
        config = db_with_completed_run._config
        inputs = HashedRunInputs(
            config=config,
            data_fingerprint=db_with_completed_run._data_fingerprint,
            code_version=db_with_completed_run._code_version,
        )
        reproduced_id = generate_run_id(inputs)
        assert reproduced_id == original_run_id

    @pytest.mark.test_id("3.4-ATDD-007")
    @pytest.mark.p1
    @pytest.mark.skip(reason="RED: Story 3.4 not implemented")
    def test_reproduce_unknown_run_raises(self, db_with_completed_run):
        from trade_advisor.experiments.reproduction import load_run_for_reproduction

        with pytest.raises(Exception):
            load_run_for_reproduction(db_with_completed_run, "nonexistent_run")

    @pytest.mark.test_id("3.4-ATDD-008")
    @pytest.mark.p2
    @pytest.mark.skip(reason="RED: Story 3.4 not implemented")
    def test_reproduce_chain_preserves_full_lineage(self, db_with_completed_run):
        from trade_advisor.experiments.reproduction import reproduce_run

        run_id = db_with_completed_run._run_id
        gen1 = reproduce_run(db_with_completed_run, run_id)
        gen2 = reproduce_run(db_with_completed_run, gen1.run_id)
        assert gen2.parent_run_id == gen1.run_id
        assert gen1.parent_run_id == run_id


class TestStory34ReproductionWebAPI:
    """Story 3.4: Web API routes for run reproduction."""

    @pytest.mark.test_id("3.4-ATDD-009")
    @pytest.mark.p0
    @pytest.mark.skip(reason="RED: Story 3.4 not implemented")
    async def test_reproduce_api_returns_new_run(self, app_client, db_with_completed_run):
        run_id = db_with_completed_run._run_id
        response = await app_client.post(f"/api/experiments/{run_id}/reproduce")
        assert response.status_code in (200, 202)
        data = response.json()
        assert data["run_id"] != run_id
        assert data["parent_run_id"] == run_id

    @pytest.mark.test_id("3.4-ATDD-010")
    @pytest.mark.p0
    @pytest.mark.skip(reason="RED: Story 3.4 not implemented")
    async def test_reproduce_api_404_for_unknown_run(self, app_client):
        response = await app_client.post("/api/experiments/nonexistent/reproduce")
        assert response.status_code == 404

    @pytest.mark.test_id("3.4-ATDD-011")
    @pytest.mark.p1
    @pytest.mark.skip(reason="RED: Story 3.4 not implemented")
    async def test_reproduce_api_warns_on_stale_data(self, app_client, db_with_stale_fingerprint):
        run_id = db_with_stale_fingerprint._run_id
        response = await app_client.post(f"/api/experiments/{run_id}/reproduce")
        data = response.json()
        assert data.get("data_freshness_warning") is not None
