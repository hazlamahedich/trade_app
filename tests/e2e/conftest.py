"""Playwright fixtures for Streamlit E2E tests.

Provides:
- ``streamlit_app``: starts a Streamlit subprocess on a free port
- ``app_page``: a Playwright Page already navigated to the running app
"""
from __future__ import annotations

import os
import signal
import subprocess
import time
from urllib.request import urlopen

import pytest

_PORT = int(os.getenv("STREAMLIT_PORT", "8501"))
_BASE_URL = os.getenv("STREAMLIT_BASE_URL", f"http://localhost:{_PORT}")
_STARTUP_TIMEOUT = 20


def _wait_for_streamlit(url: str, timeout: int = _STARTUP_TIMEOUT) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urlopen(url, timeout=2)
            return
        except Exception:
            time.sleep(0.5)
    raise RuntimeError(f"Streamlit not reachable at {url} after {timeout}s")


@pytest.fixture(scope="session")
def streamlit_url():
    """Return the base URL; start Streamlit if not already running."""
    try:
        urlopen(_BASE_URL, timeout=2)
        yield _BASE_URL
    except Exception:
        proc = subprocess.Popen(
            [
                "python", "-m", "streamlit", "run",
                "src/trade_advisor/ui/app.py",
                "--server.port", str(_PORT),
                "--server.headless", "true",
                "--browser.gatherUsageStats", "false",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _wait_for_streamlit(_BASE_URL)
        yield _BASE_URL
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=5)


@pytest.fixture
def app_page(browser, streamlit_url):
    page = browser.new_page()
    page.goto(streamlit_url, wait_until="networkidle")
    page.wait_for_selector("h1", timeout=15_000)
    yield page
    page.close()
