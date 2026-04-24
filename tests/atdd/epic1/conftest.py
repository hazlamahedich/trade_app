"""Shared ATDD fixtures for Epic 1 tests."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def sample_ohlcv_df() -> pd.DataFrame:
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=100, freq="B", tz="UTC"),
        "symbol": "TEST",
        "interval": "1d",
        "open": np.linspace(100, 110, 100),
        "high": np.linspace(101, 111, 100),
        "low": np.linspace(99, 109, 100),
        "close": np.linspace(100.5, 110.5, 100),
        "adj_close": np.linspace(100.5, 110.5, 100),
        "volume": np.full(100, 1_000_000),
    })


@pytest.fixture
def ohlcv_with_nan() -> pd.DataFrame:
    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=10, tz="UTC"),
        "open": [100.0] * 10,
        "high": [101.0] * 10,
        "low": [99.0] * 10,
        "close": [100.5, np.nan, np.nan, np.nan, 100.0, 100.5, 101.0, 101.5, 102.0, 102.5],
        "volume": [1e6] * 10,
    })
    return df


@pytest.fixture
def ohlcv_with_duplicates() -> pd.DataFrame:
    ts = list(pd.date_range("2024-01-01", periods=5, tz="UTC"))
    ts.append(ts[-1])
    return pd.DataFrame({
        "timestamp": ts,
        "open": [100.0] * 6,
        "high": [101.0] * 6,
        "low": [99.0] * 6,
        "close": [100.5] * 6,
        "volume": [1e6] * 6,
    })


@pytest.fixture
def ohlcv_with_zero_volume() -> pd.DataFrame:
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=5, tz="UTC"),
        "open": [100.0] * 5,
        "high": [101.0] * 5,
        "low": [99.0] * 5,
        "close": [100.5] * 5,
        "volume": [1e6, 0, 1e6, 0, 1e6],
    })
