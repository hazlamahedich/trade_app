"""Shared ATDD fixtures for Epic 1 tests."""

from __future__ import annotations

from contextlib import asynccontextmanager

import numpy as np
import pandas as pd
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from tests.support.factories.ohlcv_factory import make_ohlcv as _make_ohlcv
from trade_advisor.core.config import DatabaseConfig
from trade_advisor.data.storage import DataRepository
from trade_advisor.infra.db import DatabaseManager


@pytest.fixture
def sample_ohlcv_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=100, freq="B", tz="UTC"),
            "symbol": "TEST",
            "interval": "1d",
            "open": np.linspace(100, 110, 100),
            "high": np.linspace(101, 111, 100),
            "low": np.linspace(99, 109, 100),
            "close": np.linspace(100.5, 110.5, 100),
            "adj_close": np.linspace(100.5, 110.5, 100),
            "volume": np.full(100, 1_000_000),
        }
    )


@pytest.fixture
def ohlcv_with_nan() -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=10, tz="UTC"),
            "open": [100.0] * 10,
            "high": [101.0] * 10,
            "low": [99.0] * 10,
            "close": [100.5, np.nan, np.nan, np.nan, 100.0, 100.5, 101.0, 101.5, 102.0, 102.5],
            "volume": [1e6] * 10,
        }
    )
    return df


@pytest.fixture
def ohlcv_with_duplicates() -> pd.DataFrame:
    ts = list(pd.date_range("2024-01-01", periods=5, tz="UTC"))
    ts.append(ts[-1])
    return pd.DataFrame(
        {
            "timestamp": ts,
            "open": [100.0] * 6,
            "high": [101.0] * 6,
            "low": [99.0] * 6,
            "close": [100.5] * 6,
            "volume": [1e6] * 6,
        }
    )


@pytest.fixture
def ohlcv_with_zero_volume() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=5, tz="UTC"),
            "open": [100.0] * 5,
            "high": [101.0] * 5,
            "low": [99.0] * 5,
            "close": [100.5] * 5,
            "volume": [1e6, 0, 1e6, 0, 1e6],
        }
    )


def _make_split_ohlcv(symbol: str = "SPLIT") -> pd.DataFrame:
    n = 20
    rng = np.random.default_rng(99)
    dates = pd.date_range("2024-01-01", periods=n, freq="B", tz="UTC")
    close = np.linspace(100, 110, n)
    split_factor = np.ones(n)
    split_factor[10] = 2.0
    div_factor = np.ones(n)
    div_factor[15] = 0.98
    df = pd.DataFrame(
        {
            "symbol": symbol,
            "interval": "1d",
            "timestamp": dates,
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "adj_close": close,
            "volume": rng.integers(1_000_000, 5_000_000, n),
            "source": "synthetic",
            "split_factor": split_factor,
            "div_factor": div_factor,
        }
    )
    return df


@asynccontextmanager
async def _create_client_with_data(*dfs: pd.DataFrame):
    from trade_advisor.main import app

    config = DatabaseConfig(path=":memory:")
    db = DatabaseManager(config)
    async with db:
        original_db = getattr(app.state, "db", None)
        app.state.db = db
        try:
            if dfs:
                repo = DataRepository(db)
                for df in dfs:
                    await repo.store(df, provider_name="synthetic")

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                yield client
        finally:
            app.state.db = original_db


@pytest_asyncio.fixture
async def async_client_with_data():
    async with _create_client_with_data(_make_ohlcv(n=100, start="2024-01-01")) as client:
        yield client


@pytest_asyncio.fixture
async def async_client_with_data_adj():
    async with _create_client_with_data(
        _make_ohlcv(n=100, start="2024-01-01", adj_diff=True)
    ) as client:
        yield client


@pytest_asyncio.fixture
async def async_client_with_anomaly():
    df = _make_ohlcv(symbol="ANOMALY", n=30, start="2024-01-01")
    df.loc[10, "volume"] = 0
    async with _create_client_with_data(df) as client:
        yield client


@pytest_asyncio.fixture
async def async_client_with_split():
    async with _create_client_with_data(_make_split_ohlcv()) as client:
        yield client


@pytest_asyncio.fixture
async def async_client_empty():
    async with _create_client_with_data() as client:
        yield client


@pytest_asyncio.fixture
async def async_client_50_symbols():
    dfs = []
    for i in range(50):
        symbol = f"SYM{i:03d}"
        dfs.append(_make_ohlcv(symbol=symbol, n=100, seed=i, start="2024-01-01"))
    async with _create_client_with_data(*dfs) as client:
        yield client
