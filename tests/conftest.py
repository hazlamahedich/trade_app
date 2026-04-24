"""Shared pytest fixtures."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def _synthetic_ohlcv(
    n: int = 500,
    symbol: str = "TEST",
    start: str = "2020-01-01",
    seed: int = 42,
    trend: float = 0.0003,
    vol: float = 0.01,
) -> pd.DataFrame:
    """Generate a deterministic synthetic OHLCV frame for offline tests."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start=start, periods=n, freq="B", tz="UTC")
    rets = rng.normal(loc=trend, scale=vol, size=n)
    close = 100.0 * np.cumprod(1.0 + rets)
    open_ = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.002, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.002, n)))
    volume = rng.integers(1_000_000, 5_000_000, size=n)

    df = pd.DataFrame(
        {
            "symbol": symbol,
            "interval": "1d",
            "timestamp": dates,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "adj_close": close,
            "volume": volume,
            "source": "synthetic",
        }
    )
    return df


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
