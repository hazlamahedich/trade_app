"""ATDD acceptance tests: Story 2.1 — Built-in SMA Crossover Strategy.

Tests assert the expected end-state after full Story 2.1 implementation.
All tests are active (unskipped).
"""

from __future__ import annotations

import json

import pandas as pd
import pytest
from tests.helpers import _synthetic_ohlcv, assert_no_lookahead_bias

from trade_advisor.strategies.interface import Strategy
from trade_advisor.strategies.sma_cross import SmaCross


class TestStory21SmaCrossover:
    """Story 2.1: Working SMA crossover strategy included with the platform."""

    def test_sma_crossover_implements_strategy_protocol(self):
        strategy = SmaCross(fast=20, slow=50)
        assert isinstance(strategy, Strategy)

    def test_sma_crossover_generates_buy_sell_signals(self, ohlcv_500):
        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv_500)
        assert set(signals.unique()).issubset({-1.0, 0.0, 1.0})
        assert (signals != 0).any(), "Strategy produces no non-flat signals"

    def test_sma_crossover_generates_timestamps(self, ohlcv_500):
        strategy = SmaCross(fast=20, slow=50)
        signals = strategy.generate_signals(ohlcv_500)
        assert len(signals) == len(ohlcv_500)

    def test_sma_crossover_config_serializable_to_json(self):
        strategy = SmaCross(fast=14, slow=30)
        config = strategy.to_config()
        config_json = config.model_dump_json()
        parsed = json.loads(config_json)
        assert parsed["fast"] == 14
        assert parsed["slow"] == 30

    def test_sma_crossover_information_latency_declared(self):
        strategy = SmaCross(fast=20, slow=50)
        assert strategy.information_latency == 1
        assert strategy.warmup_period == 50

    def test_sma_crossover_no_lookahead_bias(self):
        assert_no_lookahead_bias(SmaCross, fast=10, slow=20)

    def test_sma_crossover_invalid_params_raise(self):
        with pytest.raises(ValueError):
            SmaCross(fast=50, slow=20)
        with pytest.raises(ValueError):
            SmaCross(fast=0, slow=50)
        with pytest.raises(ValueError):
            SmaCross(fast=-1, slow=50)

    def test_sma_crossover_allow_short_mode(self, ohlcv_500):
        strategy = SmaCross(fast=20, slow=50, allow_short=True)
        signals = strategy.generate_signals(ohlcv_500)
        assert -1.0 in set(signals.unique()), "allow_short=True should produce -1 signals"

    def test_sma_crossover_identical_seed_identical_signals(self):
        df1 = _synthetic_ohlcv(n=500, seed=42)
        df2 = _synthetic_ohlcv(n=500, seed=42)
        strategy = SmaCross(fast=20, slow=50)
        s1 = strategy.generate_signals(df1)
        s2 = strategy.generate_signals(df2)
        pd.testing.assert_series_equal(s1, s2)
