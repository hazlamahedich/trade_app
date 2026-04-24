"""Sample enhanced unit test demonstrating factory usage and parametrize."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tests.support.factories.ohlcv_factory import make_ohlcv, make_signals
from tests.support.helpers.assertions import assert_no_lookahead_bias, assert_signals_in_range


class TestOHLCVFactory:
    def test_default_shape(self):
        df = make_ohlcv()
        assert len(df) == 500
        assert set(df.columns) >= {"open", "high", "low", "close", "volume"}

    def test_custom_symbol(self):
        df = make_ohlcv(symbol="AAPL")
        assert (df["symbol"] == "AAPL").all()

    @pytest.mark.parametrize("n", [10, 100, 1000])
    def test_various_lengths(self, n):
        df = make_ohlcv(n=n)
        assert len(df) == n

    def test_deterministic_with_same_seed(self):
        df1 = make_ohlcv(seed=7)
        df2 = make_ohlcv(seed=7)
        pd.testing.assert_frame_equal(df1, df2)

    def test_different_seeds_produce_different_data(self):
        df1 = make_ohlcv(seed=1)
        df2 = make_ohlcv(seed=2)
        assert not np.allclose(df1["close"].values, df2["close"].values)


class TestSignalAssertions:
    def test_valid_signals_pass(self):
        signals = make_signals(seed=42)
        assert_signals_in_range(signals)

    def test_no_lookahead_passes_for_shifted_signals(self):
        signals = make_signals()
        prices = make_ohlcv()["close"]
        assert_no_lookahead_bias(signals, prices)
