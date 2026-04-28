"""Shared ATDD fixtures for Epic 2 tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from tests.helpers import _synthetic_ohlcv


@pytest.fixture
def ohlcv_500() -> pd.DataFrame:
    return _synthetic_ohlcv(n=500, seed=42)


@pytest.fixture
def ohlcv_2520() -> pd.DataFrame:
    return _synthetic_ohlcv(n=2520, seed=42, symbol="SPY")


@pytest.fixture
def ohlcv_trending_up() -> pd.DataFrame:
    return _synthetic_ohlcv(n=500, seed=42, trend=0.002, vol=0.005)


@pytest.fixture
def ohlcv_trending_down() -> pd.DataFrame:
    n = 500
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2020-01-01", periods=n)
    close = 100.0
    closes = []
    for _ in range(n):
        close *= 1.0 + rng.normal(-0.002, 0.01)
        closes.append(close)
    close_s = pd.Series(closes)
    return pd.DataFrame(
        {
            "symbol": "DOWN",
            "interval": "1d",
            "timestamp": dates,
            "open": close_s * 0.999,
            "high": close_s * 1.002,
            "low": close_s * 0.997,
            "close": close_s,
            "adj_close": close_s,
            "volume": rng.integers(1_000_000, 5_000_000, n),
            "source": "synthetic",
        }
    )


@pytest.fixture
def ohlcv_flat() -> pd.DataFrame:
    n = 200
    dates = pd.bdate_range("2020-01-01", periods=n)
    close = pd.Series(np.full(n, 100.0) + np.random.default_rng(42).normal(0, 0.1, n))
    return pd.DataFrame(
        {
            "symbol": "FLAT",
            "interval": "1d",
            "timestamp": dates,
            "open": close,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "adj_close": close,
            "volume": np.full(n, 1_000_000),
            "source": "synthetic",
        }
    )


@pytest.fixture
def ohlcv_50_symbols() -> list[pd.DataFrame]:
    return [
        _synthetic_ohlcv(n=2520, seed=i, symbol=f"SYM{i:03d}")
        for i in range(50)
    ]


@pytest.fixture
def backtest_config():
    from trade_advisor.core.config import BacktestConfig, CostModel

    return BacktestConfig(
        initial_cash="100000",
        cost=CostModel(commission_pct=0.001, slippage_pct=0.0005),
    )


@pytest.fixture
def zero_cost_config():
    from trade_advisor.core.config import BacktestConfig, CostModel

    return BacktestConfig(
        initial_cash="100000",
        cost=CostModel(commission_pct=0.0, slippage_pct=0.0),
    )
