"""Shared pytest fixtures for unit/integration tests.

Extends the root conftest with additional reusable fixtures.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tests.conftest import _synthetic_ohlcv


@pytest.fixture
def ohlcv_with_signals() -> pd.DataFrame:
    df = _synthetic_ohlcv(n=500)
    rng = np.random.default_rng(99)
    df["signal"] = rng.choice([-1, 0, 1], size=len(df), p=[0.15, 0.70, 0.15])
    return df


@pytest.fixture(params=[100, 250, 500])
def ohlcv_various_sizes(request) -> pd.DataFrame:
    return _synthetic_ohlcv(n=request.param)


@pytest.fixture
def empty_ohlcv() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "symbol",
            "interval",
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "adj_close",
            "volume",
            "source",
        ]
    )


@pytest.fixture
def single_row_ohlcv() -> pd.DataFrame:
    return _synthetic_ohlcv(n=1)
