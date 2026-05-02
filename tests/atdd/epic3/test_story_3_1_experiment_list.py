"""ATDD: Story 3.1 — Experiment Run List & Detail View.

Tests assert the EXPECTED end-state for Story 3.1.
"""

from __future__ import annotations

import json

import pytest


class TestStory31ExperimentRunList:
    """Story 3.1: Users can browse all past experiment runs in a list."""

    @pytest.mark.test_id("3.1-ATDD-001")
    @pytest.mark.p0
    async def test_list_returns_chronological_runs(self, db_with_experiments):
        # Given: a database with multiple experiment runs
        db, _ctx = db_with_experiments
        from trade_advisor.experiments.tracker import ExperimentRepository

        # When: listing runs ordered by created_at
        runs = await ExperimentRepository.list_runs(db, order_by="created_at", limit=50)

        # Then: runs are returned in reverse chronological order
        assert len(runs) > 0
        timestamps = [r.created_at for r in runs]
        assert timestamps == sorted(timestamps, reverse=True)

    @pytest.mark.test_id("3.1-ATDD-002")
    @pytest.mark.p0
    async def test_list_run_includes_required_fields(self, db_with_experiments):
        # Given: a database with stored experiment runs
        db, _ctx = db_with_experiments
        from trade_advisor.experiments.tracker import ExperimentRepository

        # When: listing runs
        runs = await ExperimentRepository.list_runs(db, order_by="created_at", limit=10)

        # Then: each run has required fields
        run = runs[0]
        assert run.run_id is not None
        assert run.strategy is not None
        assert run.status in ("completed", "running", "failed")
        assert run.created_at is not None

    @pytest.mark.test_id("3.1-ATDD-003")
    @pytest.mark.p0
    async def test_list_run_includes_key_metrics(self, db_with_experiments):
        # Given: a database with completed runs
        db, _ctx = db_with_experiments
        from trade_advisor.experiments.tracker import ExperimentRepository

        # When: listing runs
        runs = await ExperimentRepository.list_runs(db, order_by="created_at", limit=10)

        # Then: completed runs have key metrics
        completed = [r for r in runs if r.status == "completed"]
        if completed:
            run = completed[0]
            metrics = json.loads(run.metrics_json) if run.metrics_json else {}
            assert "sharpe" in metrics or "total_return" in metrics

    @pytest.mark.test_id("3.1-ATDD-004")
    @pytest.mark.p1
    async def test_sort_by_date(self, db_with_experiments):
        # Given: a database with runs at different dates
        db, _ctx = db_with_experiments
        from trade_advisor.experiments.tracker import ExperimentRepository

        # When: listing runs sorted by created_at
        runs = await ExperimentRepository.list_runs(db, order_by="created_at", limit=50)

        # Then: runs are in reverse chronological order
        timestamps = [r.created_at for r in runs]
        assert timestamps == sorted(timestamps, reverse=True)

    @pytest.mark.test_id("3.1-ATDD-005")
    @pytest.mark.p1
    async def test_sort_by_metric_sharpe(self, db_with_experiments):
        # Given: a database with runs having different Sharpe ratios
        db, _ctx = db_with_experiments
        from trade_advisor.experiments.tracker import ExperimentRepository

        # When: listing runs sorted by sharpe
        runs = await ExperimentRepository.list_runs(db, order_by="sharpe", limit=50)

        # Then: runs are sorted by Sharpe descending
        sharpes = [
            json.loads(r.metrics_json).get("sharpe", float("-inf")) for r in runs if r.metrics_json
        ]
        assert sharpes == sorted(sharpes, reverse=True)

    @pytest.mark.test_id("3.1-ATDD-006")
    @pytest.mark.p1
    async def test_sort_by_strategy_type(self, db_with_experiments):
        # Given: a database with runs from different strategy types
        db, _ctx = db_with_experiments
        from trade_advisor.experiments.tracker import ExperimentRepository

        # When: listing runs sorted by strategy ascending
        runs = await ExperimentRepository.list_runs(
            db, order_by="strategy", order_dir="asc", limit=50
        )

        # Then: runs are sorted alphabetically by strategy
        strategies = [r.strategy for r in runs]
        assert strategies == sorted(strategies)

    @pytest.mark.test_id("3.1-ATDD-007")
    @pytest.mark.p0
    async def test_detail_view_shows_full_config(self, db_with_experiments):
        # Given: a database with a known run
        db, ctx = db_with_experiments
        from trade_advisor.experiments.tracker import ExperimentRepository

        # When: fetching run detail by ID
        run_id = ctx.known_run_ids[0]
        detail = await ExperimentRepository.get_run(db, run_id)

        # Then: detail includes config_hash, seed, and run_id
        assert detail is not None
        assert detail.run_id == run_id
        assert detail.config_hash is not None
        assert detail.seed is not None

    @pytest.mark.test_id("3.1-ATDD-008")
    @pytest.mark.p0
    async def test_detail_view_shows_equity_curve(self, db_with_experiments):
        # Given: a database with a run that has equity data
        db, ctx = db_with_experiments
        from trade_advisor.experiments.tracker import ExperimentRepository

        # When: loading the full result for a run
        run_id = ctx.known_run_ids[0]
        result = await ExperimentRepository.load_full_result(db, run_id)

        # Then: equity curve is present and non-empty
        assert result is not None
        assert result.comparison.strategy_result.equity is not None
        assert len(result.comparison.strategy_result.equity) > 0

    @pytest.mark.test_id("3.1-ATDD-009")
    @pytest.mark.p0
    async def test_detail_view_shows_trade_list(self, db_with_experiments):
        # Given: a database with a run that has trade data
        db, ctx = db_with_experiments
        from trade_advisor.experiments.tracker import ExperimentRepository

        # When: loading the full result for a run
        run_id = ctx.known_run_ids[0]
        result = await ExperimentRepository.load_full_result(db, run_id)

        # Then: trade list is present
        assert result is not None
        trades = result.comparison.strategy_result.trades
        assert trades is not None

    @pytest.mark.test_id("3.1-ATDD-010")
    @pytest.mark.p1
    async def test_detail_view_shows_pre_mortem(self, db_with_experiments):
        # Given: a database with a run that has a pre-mortem
        db, ctx = db_with_experiments
        from trade_advisor.experiments.tracker import ExperimentRepository

        # When: fetching run detail
        run_id = ctx.known_run_ids[0]
        detail = await ExperimentRepository.get_run(db, run_id)

        # Then: pre-mortem is present
        assert detail is not None
        assert detail.pre_mortem is not None

    @pytest.mark.test_id("3.1-ATDD-011")
    @pytest.mark.p1
    async def test_faceted_filter_by_strategy_family(self, db_with_experiments):
        # Given: a database with runs from different strategy families
        db, _ctx = db_with_experiments
        from trade_advisor.experiments.tracker import ExperimentRepository

        # When: filtering by strategy family "SmaCross"
        runs = await ExperimentRepository.list_runs(db, filters={"strategy": "SmaCross"}, limit=50)

        # Then: all returned runs are SmaCross
        assert all(r.strategy == "SmaCross" for r in runs)

    @pytest.mark.test_id("3.1-ATDD-012")
    @pytest.mark.p1
    async def test_faceted_filter_by_date_range(self, db_with_experiments):
        # Given: a database with runs at various dates
        db, _ctx = db_with_experiments
        from datetime import datetime

        from trade_advisor.experiments.tracker import ExperimentRepository

        # When: filtering by date range
        start = datetime(2024, 1, 1)
        end = datetime(2025, 1, 1)
        runs = await ExperimentRepository.list_runs(
            db, filters={"date_range": (start, end)}, limit=50
        )

        # Then: all returned runs fall within the range
        for r in runs:
            assert start <= r.created_at <= end

    @pytest.mark.test_id("3.1-ATDD-013")
    @pytest.mark.p1
    async def test_faceted_filter_by_result_quality(self, db_with_experiments):
        # Given: a database with runs of varying status
        db, _ctx = db_with_experiments
        from trade_advisor.experiments.tracker import ExperimentRepository

        # When: filtering by status "completed"
        runs = await ExperimentRepository.list_runs(db, filters={"status": "completed"}, limit=50)

        # Then: all returned runs are completed
        assert all(r.status == "completed" for r in runs)

    @pytest.mark.test_id("3.1-ATDD-014")
    @pytest.mark.p2
    async def test_auto_generated_narrative_present(self, db_with_experiments):
        # Given: a database with a known run
        db, ctx = db_with_experiments
        from trade_advisor.experiments.tracker import ExperimentRepository

        # When: fetching run detail
        run_id = ctx.known_run_ids[0]
        detail = await ExperimentRepository.get_run(db, run_id)

        # Then: narrative attribute or metrics_json is present
        assert detail is not None
        assert hasattr(detail, "narrative") or detail.metrics_json is not None


class TestStory31ExperimentListWebAPI:
    """Story 3.1: Web API routes for experiment list and detail."""

    @pytest.mark.test_id("3.1-ATDD-015")
    @pytest.mark.p0
    async def test_experiments_page_returns_200(self, app_client):
        # Given: a running application with experiment data
        # When: requesting the experiments page
        response = await app_client.get("/experiments")
        # Then: the page returns 200
        assert response.status_code == 200

    @pytest.mark.test_id("3.1-ATDD-016")
    @pytest.mark.p0
    async def test_experiments_api_list(self, app_client):
        # Given: a running application with experiment data
        # When: requesting the experiments API
        response = await app_client.get("/api/experiments")
        # Then: a JSON list is returned
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.test_id("3.1-ATDD-017")
    @pytest.mark.p0
    async def test_experiment_detail_api(self, app_client, db_with_experiments):
        # Given: a running application with a known run
        _db, ctx = db_with_experiments
        # When: requesting run detail via API
        run_id = ctx.known_run_ids[0]
        response = await app_client.get(f"/api/experiments/{run_id}")
        # Then: detail JSON includes run_id, strategy, and metrics
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == run_id
        assert "strategy" in data
        assert "metrics" in data
