"""Shared pytest fixtures for integration tests (network-dependent)."""
from __future__ import annotations

import pytest


@pytest.fixture
def real_symbol() -> str:
    return "SPY"


@pytest.fixture
def real_start_date() -> str:
    return "2024-01-01"
