"""ATDD: Story 3.3 — CompareBridge Split-Panel."""

from __future__ import annotations

import pytest


class TestStory33CompareBridge:
    """Story 3.3: Side-by-side comparison of two experiment runs."""

    @pytest.mark.test_id("3.3-ATDD-001")
    @pytest.mark.p0
    def test_compare_two_runs_returns_metrics_diff(self, db_with_experiments):
        # Given: a database with multiple runs
        db, ctx = db_with_experiments
        from trade_advisor.experiments.compare import compare_runs

        # When: comparing two runs
        run_a = ctx.known_run_ids[0]
        run_b = ctx.known_run_ids[1]
        diff = compare_runs(db, run_a, run_b)

        # Then: metrics diff is present and non-empty
        assert diff is not None
        assert hasattr(diff, "metrics_diff")
        assert len(diff.metrics_diff) > 0

    @pytest.mark.test_id("3.3-ATDD-002")
    @pytest.mark.p0
    def test_metrics_diff_highlights_improvement_and_degradation(self, db_with_experiments):
        # Given: a database with runs having different metrics
        db, ctx = db_with_experiments
        from trade_advisor.experiments.compare import compare_runs

        # When: comparing two runs
        run_a = ctx.known_run_ids[0]
        run_b = ctx.known_run_ids[1]
        diff = compare_runs(db, run_a, run_b)

        # Then: each metric has a direction and delta
        for _metric_name, change in diff.metrics_diff.items():
            assert change.direction in ("improvement", "degradation", "neutral")
            assert change.delta is not None

    @pytest.mark.test_id("3.3-ATDD-003")
    @pytest.mark.p0
    def test_parameter_text_diff_with_semantic_highlighting(self, db_with_experiments):
        # Given: a database with runs having different parameters
        db, ctx = db_with_experiments
        from trade_advisor.experiments.compare import compare_runs

        # When: comparing two runs with different params
        run_a = ctx.known_run_ids[0]
        run_b = ctx.known_run_ids[2]
        diff = compare_runs(db, run_a, run_b)

        # Then: parameter diff shows field, old, and new values
        assert diff.parameter_diff is not None
        assert len(diff.parameter_diff) > 0
        for param_change in diff.parameter_diff:
            assert param_change.field is not None
            assert param_change.old_value is not None
            assert param_change.new_value is not None

    @pytest.mark.test_id("3.3-ATDD-004")
    @pytest.mark.p0
    def test_apples_to_oranges_guard_for_incompatible_strategies(self, db_with_experiments):
        # Given: a database with runs from different strategy types
        db, ctx = db_with_experiments
        from trade_advisor.experiments.compare import compare_runs

        # When: comparing runs from different strategy families
        run_a = ctx.known_run_ids[0]
        run_b = ctx.cross_strategy_run_id
        diff = compare_runs(db, run_a, run_b)

        # Then: compatibility warning is present
        assert diff.compatibility_warning is not None
        assert "incompatible" in diff.compatibility_warning.lower()

    @pytest.mark.test_id("3.3-ATDD-005")
    @pytest.mark.p1
    def test_trade_list_synced_scrolling_alignment(self, db_with_experiments):
        # Given: a database with runs that have trade lists
        db, ctx = db_with_experiments
        from trade_advisor.experiments.compare import compare_trades

        # When: comparing trades between two runs
        run_a = ctx.known_run_ids[0]
        run_b = ctx.known_run_ids[1]
        result = compare_trades(db, run_a, run_b)

        # Then: alignment strategy and trade lists are present
        assert result.alignment_strategy is not None
        assert result.trades_a is not None
        assert result.trades_b is not None

    @pytest.mark.test_id("3.3-ATDD-006")
    @pytest.mark.p2
    def test_mvp_scope_is_text_diff_only(self, db_with_experiments):
        # Given: a database with comparable runs
        db, ctx = db_with_experiments
        from trade_advisor.experiments.compare import compare_runs

        # When: comparing two runs
        run_a = ctx.known_run_ids[0]
        run_b = ctx.known_run_ids[1]
        diff = compare_runs(db, run_a, run_b)

        # Then: chart overlay is deferred to Epic 7
        assert diff.chart_overlay is None or diff.chart_overlay == "deferred_epic_7"


class TestStory33CompareBridgeWebAPI:
    """Story 3.3: Web API routes for CompareBridge."""

    @pytest.mark.test_id("3.3-ATDD-007")
    @pytest.mark.p0
    async def test_compare_api_returns_diff(self, app_client, db_with_experiments):
        # Given: a running app with experiment data
        _db, ctx = db_with_experiments
        # When: calling compare API with two runs
        run_a = ctx.known_run_ids[0]
        run_b = ctx.known_run_ids[1]
        response = await app_client.get(f"/api/experiments/compare?run_a={run_a}&run_b={run_b}")
        # Then: response includes metrics_diff and parameter_diff
        assert response.status_code == 200
        data = response.json()
        assert "metrics_diff" in data
        assert "parameter_diff" in data

    @pytest.mark.test_id("3.3-ATDD-008")
    @pytest.mark.p1
    async def test_compare_api_404_for_missing_run(self, app_client, db_with_experiments):
        # Given: a running app with experiment data
        _db, ctx = db_with_experiments
        # When: comparing a valid run with a nonexistent run
        run_a = ctx.known_run_ids[0]
        response = await app_client.get(f"/api/experiments/compare?run_a={run_a}&run_b=nonexistent")
        # Then: 404 is returned
        assert response.status_code == 404

    @pytest.mark.test_id("3.3-ATDD-009")
    @pytest.mark.p0
    async def test_compare_page_renders_split_panel(self, app_client, db_with_experiments):
        # Given: a running app with experiment data
        _db, ctx = db_with_experiments
        # When: requesting the compare page
        run_a = ctx.known_run_ids[0]
        run_b = ctx.known_run_ids[1]
        response = await app_client.get(f"/experiments/compare?run_a={run_a}&run_b={run_b}")
        # Then: page renders with "compare" content
        assert response.status_code == 200
        html = response.text
        assert "compare" in html.lower()
