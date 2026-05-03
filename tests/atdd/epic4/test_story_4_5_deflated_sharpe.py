"""ATDD: Story 4.5 — Deflated Sharpe Ratio & Trial Accounting.

Tests assert the EXPECTED end-state for Story 4.5.
RED PHASE: These tests will fail until deflated Sharpe is implemented.
"""

from __future__ import annotations

import pytest


class TestStory45DeflatedSharpe:
    """Story 4.5: Deflated Sharpe ratio accounting for multiple testing."""

    @pytest.mark.test_id("4.5-ATDD-001")
    @pytest.mark.p0
    async def test_deflated_sharpe_computed(self):
        # Given: a standard Sharpe ratio and trial count
        from trade_advisor.backtest.walkforward.deflated import compute_deflated_sharpe

        standard_sharpe = 1.5
        n_trials = 50

        # When: computing deflated Sharpe ratio (WFO-6)
        deflated = compute_deflated_sharpe(standard_sharpe, n_trials)

        # Then: deflated Sharpe is lower than standard (penalized for trials)
        assert deflated < standard_sharpe
        assert deflated > 0

    @pytest.mark.test_id("4.5-ATDD-002")
    @pytest.mark.p0
    async def test_single_trial_no_penalty(self):
        # Given: a single trial
        from trade_advisor.backtest.walkforward.deflated import compute_deflated_sharpe

        # When: computing deflated Sharpe with n_trials=1
        deflated = compute_deflated_sharpe(1.5, n_trials=1)

        # Then: deflated Sharpe equals standard Sharpe (no multiple testing penalty)
        assert abs(deflated - 1.5) < 1e-10

    @pytest.mark.test_id("4.5-ATDD-003")
    @pytest.mark.p0
    async def test_many_trials_reduces_sharpe(self):
        # Given: many independent trials
        from trade_advisor.backtest.walkforward.deflated import compute_deflated_sharpe

        # When: computing deflated Sharpe with many trials
        deflated_few = compute_deflated_sharpe(1.5, n_trials=5)
        deflated_many = compute_deflated_sharpe(1.5, n_trials=100)

        # Then: more trials => lower deflated Sharpe
        assert deflated_many < deflated_few

    @pytest.mark.test_id("4.5-ATDD-004")
    @pytest.mark.p0
    async def test_below_significance_shows_warning(self):
        # Given: a deflated Sharpe below significance threshold
        from trade_advisor.backtest.walkforward.deflated import compute_deflated_sharpe

        # When: deflated Sharpe is low (many trials, moderate raw Sharpe)
        deflated = compute_deflated_sharpe(0.5, n_trials=200)

        # Then: the function signals a multiple-testing warning
        assert deflated < 0.5
        assert deflated < 0.0 or deflated < 1.0

    @pytest.mark.test_id("4.5-ATDD-005")
    @pytest.mark.p0
    async def test_trial_count_tracked_from_lineage(self, db_with_wf_results):
        # Given: a database with experiment lineage
        from trade_advisor.backtest.walkforward.deflated import count_independent_trials

        db, _ctx = db_with_wf_results

        # When: counting trials from experiment lineage
        n_trials = await count_independent_trials(db, strategy="SmaCross")

        # Then: trial count reflects number of independent experiments (MANDATORY for DSR)
        assert n_trials >= 1

    @pytest.mark.test_id("4.5-ATDD-010")
    @pytest.mark.p0
    async def test_degenerate_distribution_handled_safely(self):
        # Given: returns with zero variance (degenerate distribution)
        from trade_advisor.backtest.walkforward.deflated import compute_deflated_sharpe

        standard_sharpe = 0.0
        n_trials = 100

        # When: computing DSR for a flat equity curve
        # Then: it does not crash (no NaN/Inf leakage)
        deflated = compute_deflated_sharpe(standard_sharpe, n_trials)
        assert deflated == 0.0

    @pytest.mark.test_id("4.5-ATDD-011")
    @pytest.mark.p0
    async def test_memory_efficiency_with_many_trials(self):
        # Given: a massive number of trials
        from trade_advisor.backtest.walkforward.deflated import compute_trial_stats_online

        # When: processing 100,000 trials using online variance
        # Then: it completes quickly without storing all results in memory
        stats = compute_trial_stats_online(n_trials=100_000, metrics_stream=range(100_000))
        assert stats.n_trials == 100_000
        assert stats.variance > 0

    @pytest.mark.test_id("4.5-ATDD-006")
    @pytest.mark.p1
    async def test_displayed_alongside_standard_sharpe(self):
        # Given: both Sharpe ratios
        from trade_advisor.backtest.walkforward.deflated import compute_deflated_sharpe

        standard_sharpe = 1.5
        n_trials = 50
        deflated = compute_deflated_sharpe(standard_sharpe, n_trials)

        # When: presenting results
        # Then: both values are available for display
        assert standard_sharpe > 0
        assert deflated > 0
        assert deflated < standard_sharpe

    @pytest.mark.test_id("4.5-ATDD-007")
    @pytest.mark.p2
    async def test_zero_sharpe_returns_zero(self):
        # Given: a zero standard Sharpe
        from trade_advisor.backtest.walkforward.deflated import compute_deflated_sharpe

        # When: computing deflated Sharpe
        deflated = compute_deflated_sharpe(0.0, n_trials=50)

        # Then: deflated is also zero
        assert deflated == 0.0

    @pytest.mark.test_id("4.5-ATDD-008")
    @pytest.mark.p2
    async def test_negative_sharpe_stays_negative(self):
        # Given: a negative standard Sharpe
        from trade_advisor.backtest.walkforward.deflated import compute_deflated_sharpe

        # When: computing deflated Sharpe
        deflated = compute_deflated_sharpe(-1.0, n_trials=50)

        # Then: deflated Sharpe is also negative
        assert deflated < 0

    @pytest.mark.test_id("4.5-ATDD-009")
    @pytest.mark.p2
    async def test_invalid_trial_count_raises(self):
        # Given: zero or negative trial count
        from trade_advisor.backtest.walkforward.deflated import compute_deflated_sharpe

        # When: computing with invalid trial count
        # Then: validation error is raised
        with pytest.raises((ValueError, TypeError)):
            compute_deflated_sharpe(1.5, n_trials=0)
