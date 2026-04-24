"""E2E tests for the Streamlit dashboard.

Run: pytest tests/e2e/test_dashboard.py --browser chromium
Requires: streamlit server started automatically by conftest fixture.
"""

from __future__ import annotations

import pytest

from tests.e2e.pages.dashboard import DashboardPage

pytestmark = pytest.mark.e2e


class TestDashboardLanding:
    """Given the dashboard is loaded, When no backtest has run, Then show landing state."""

    def test_title_visible(self, app_page):
        dashboard = DashboardPage(app_page)
        assert dashboard.title.inner_text() == "Quant Trade Advisor"

    def test_landing_info_message(self, app_page):
        app_page.locator("text=Configure a run in the sidebar").wait_for(timeout=10_000)

    def test_run_button_exists(self, app_page):
        dashboard = DashboardPage(app_page)
        assert dashboard.run_button.is_visible()


class TestDashboardBacktest:
    """Given valid params, When Run backtest is clicked, Then metrics appear."""

    def test_run_shows_metrics(self, app_page):
        dashboard = DashboardPage(app_page)
        dashboard.set_symbol("SPY")
        dashboard.run_backtest()
        assert dashboard.metric_values.count() >= 5

    def test_shows_error_when_fast_ge_slow(self, app_page):
        dashboard = DashboardPage(app_page)
        dashboard.set_fast_sma(50)
        dashboard.set_slow_sma(20)
        dashboard.run_button.click()
        dashboard.error_message.wait_for(timeout=10_000)
        assert (
            "Fast SMA must be strictly less than Slow SMA" in dashboard.error_message.inner_text()
        )
