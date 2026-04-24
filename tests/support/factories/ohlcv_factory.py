"""Test data factories for deterministic test fixtures.

Usage:
    from tests.support.factories.ohlcv_factory import make_ohlcv
    df = make_ohlcv(n=200, symbol="AAPL")
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def make_ohlcv(
    n: int = 500,
    symbol: str = "TEST",
    start: str = "2020-01-01",
    seed: int = 42,
    trend: float = 0.0003,
    vol: float = 0.01,
    interval: str = "1d",
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start=start, periods=n, freq="B", tz="UTC")
    rets = rng.normal(loc=trend, scale=vol, size=n)
    close = 100.0 * np.cumprod(1.0 + rets)
    open_ = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.002, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.002, n)))
    volume = rng.integers(1_000_000, 5_000_000, size=n)

    return pd.DataFrame(
        {
            "symbol": symbol,
            "interval": interval,
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


def make_signals(
    n: int = 500,
    seed: int = 99,
    long_pct: float = 0.15,
    short_pct: float = 0.15,
) -> pd.Series:
    rng = np.random.default_rng(seed)
    flat_pct = 1.0 - long_pct - short_pct
    return pd.Series(rng.choice([-1, 0, 1], size=n, p=[short_pct, flat_pct, long_pct]))


def make_equity(
    n: int = 500,
    initial_cash: float = 100_000.0,
    seed: int = 42,
) -> pd.Series:
    rng = np.random.default_rng(seed)
    returns = pd.Series(rng.normal(0.0002, 0.01, size=n))
    equity = initial_cash * (1 + returns).cumprod()
    equity.index = pd.bdate_range("2020-01-01", periods=n)
    return equity
