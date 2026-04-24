"""Streamlit page object for the Quant Trade Advisor dashboard."""
from __future__ import annotations

from playwright.sync_api import Locator, Page


class DashboardPage:
    """Page object representing the Streamlit dashboard."""

    def __init__(self, page: Page) -> None:
        self.page = page
        self.title = page.locator("h1")

    # --- Sidebar controls ---

    @property
    def symbol_input(self) -> Locator:
        return self.page.locator('input[aria-label="Symbol"]')

    @property
    def start_date_input(self) -> Locator:
        return self.page.locator('input[aria-label="Start date"]')

    @property
    def fast_sma_input(self) -> Locator:
        return self.page.locator('input[aria-label="Fast SMA"]')

    @property
    def slow_sma_input(self) -> Locator:
        return self.page.locator('input[aria-label="Slow SMA"]')

    @property
    def run_button(self) -> Locator:
        return self.page.get_by_role("button", name="Run backtest")

    # --- Actions ---

    def set_symbol(self, symbol: str) -> None:
        self.symbol_input.fill(symbol)

    def set_fast_sma(self, value: int) -> None:
        self.fast_sma_input.fill(str(value))

    def set_slow_sma(self, value: int) -> None:
        self.slow_sma_input.fill(str(value))

    def run_backtest(self) -> None:
        self.run_button.click()
        self.page.wait_for_selector('[data-testid="stMetricValue"]', timeout=30_000)

    # --- Result locators ---

    @property
    def metric_values(self) -> Locator:
        return self.page.locator('[data-testid="stMetricValue"]')

    def get_metric(self, label: str) -> str:
        container = self.page.locator(f'[data-testid="stMetricLabel"]:has-text("{label}")')
        return container.locator("..").locator('[data-testid="stMetricValue"]').inner_text()

    @property
    def error_message(self) -> Locator:
        return self.page.locator('[data-testid="stAlert"]')

    @property
    def chart(self) -> Locator:
        return self.page.locator(".js-plotly-plot")
