"""Playwright configuration for Streamlit E2E tests.

Run with: pytest tests/e2e/ --browser chromium
Headless: PLAYWRIGHT_HEADLESS=1 pytest tests/e2e/
"""
from __future__ import annotations

import os

headless = os.getenv("PLAYWRIGHT_HEADLESS", "1") == "1"
slow_mo = float(os.getenv("PLAYWRIGHT_SLOW_MO", "0"))


def pytest_playwright_configure(config):
    return {
        "headless": headless,
        "slowmo": slow_mo,
        "browser_channel": "chromium",
        "base_url": os.getenv("STREAMLIT_BASE_URL", "http://localhost:8501"),
        "timeout": 30_000,
        "action_timeout": 15_000,
        "navigation_timeout": 30_000,
        "screenshot": "only-on-failure",
        "video": "retain-on-failure",
        "trace": "retain-on-failure",
    }
