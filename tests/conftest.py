"""Shared pytest fixtures."""

from __future__ import annotations

import pandas as pd
import pytest
import structlog

from .helpers import (  # noqa: F401 — re-exported for `from tests.conftest import ...`
    StubDataProvider,
    _synthetic_ohlcv,
    assert_no_lookahead_bias,
    bootstrap_test_container,
    strategy_conforms_to_protocol,
)


@pytest.fixture(autouse=True)
def _reset_structlog():
    """Reset structlog configuration before each test."""
    structlog.reset_defaults()
    yield
    structlog.reset_defaults()


@pytest.fixture
def synthetic_ohlcv() -> pd.DataFrame:
    return _synthetic_ohlcv()


@pytest.fixture
def short_ohlcv() -> pd.DataFrame:
    return _synthetic_ohlcv(n=120)


@pytest.fixture
def fake_fetcher():
    """A fetcher callable matching the get_ohlcv signature, returning synthetic data."""

    def _f(symbol, start=None, end=None, interval="1d"):
        df = _synthetic_ohlcv(n=500, symbol=symbol)
        if start is not None:
            df = df[df["timestamp"] >= pd.to_datetime(start, utc=True)]
        if end is not None:
            df = df[df["timestamp"] < pd.to_datetime(end, utc=True)]
        return df.reset_index(drop=True)

    return _f
