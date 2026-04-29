"""Shared convergence test fixtures."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tests.helpers import _synthetic_ohlcv
from trade_advisor.config import BacktestConfig, CostModel


@pytest.fixture
def zero_cost_config() -> BacktestConfig:
    return BacktestConfig(
        initial_cash="100000",
        cost=CostModel(commission_pct=0.0, slippage_pct=0.0),
    )


@pytest.fixture
def ohlcv_500() -> pd.DataFrame:
    return _synthetic_ohlcv(n=500, seed=42)


@pytest.fixture
def flat_signal(ohlcv_500: pd.DataFrame) -> pd.Series:
    n = len(ohlcv_500)
    return pd.Series(np.zeros(n), dtype="float64", name="signal")


@pytest.fixture
def single_long_signal(ohlcv_500: pd.DataFrame) -> pd.Series:
    n = len(ohlcv_500)
    sig = np.zeros(n, dtype="float64")
    sig[10:50] = 1.0
    return pd.Series(sig, name="signal")


@pytest.fixture
def sma_crossover_signal(ohlcv_500: pd.DataFrame) -> pd.Series:
    from trade_advisor.strategies.sma_cross import SmaCross

    strategy = SmaCross(fast=20, slow=50)
    return strategy.generate_signals(ohlcv_500)


@pytest.fixture
def reversal_signal(ohlcv_500: pd.DataFrame) -> pd.Series:
    n = len(ohlcv_500)
    sig = np.zeros(n, dtype="float64")
    sig[20:100] = 1.0
    sig[100:180] = -1.0
    sig[180:260] = 1.0
    return pd.Series(sig, name="signal")


@pytest.fixture
def random_walk_signal(ohlcv_500: pd.DataFrame) -> pd.Series:
    rng = np.random.default_rng(42)
    n = len(ohlcv_500)
    raw = rng.standard_normal(n).cumsum()
    raw = raw / (np.abs(raw).max() + 1e-8)
    raw = np.clip(raw, -1.0, 1.0)
    return pd.Series(raw, dtype="float64", name="signal")
