"""Adversarial tests for information-latency / lookahead-bias (SE-5).

Two non-negotiable tests:
- **Oracle Shuffle**: shuffling data beyond a cutoff produces identical
  signals up to that cutoff.
- **Truncation**: adding future data doesn't change signal at index *i*.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from tests.helpers import _synthetic_ohlcv, assert_no_lookahead_bias
from trade_advisor.strategies.sma_cross import SmaCross


class TestLookaheadBias:
    def test_oracle_shuffle_sma_cross(self):
        strategy = SmaCross(fast=10, slow=30)
        ohlcv_full = _synthetic_ohlcv(n=300, seed=123)
        cutoff = 200

        ohlcv_truncated = ohlcv_full.iloc[:cutoff].copy()
        signals_truncated = strategy.generate_signals(ohlcv_truncated)

        rng = np.random.default_rng(99)
        shuffled_future = ohlcv_full.iloc[cutoff:].copy()
        shuffled_idx = rng.permutation(len(shuffled_future))
        ohlcv_shuffled = pd.concat(
            [ohlcv_truncated, shuffled_future.iloc[shuffled_idx].reset_index(drop=True)],
            ignore_index=True,
        )
        signals_shuffled = strategy.generate_signals(ohlcv_shuffled)

        pd.testing.assert_series_equal(
            signals_truncated.reset_index(drop=True),
            signals_shuffled.iloc[:cutoff].reset_index(drop=True),
            check_names=False,
            obj="signals up to cutoff must be identical after shuffling future data",
        )

    def test_truncation_test_sma_cross(self):
        strategy = SmaCross(fast=10, slow=30)
        ohlcv_full = _synthetic_ohlcv(n=300, seed=123)
        cutoff = 200

        ohlcv_truncated = ohlcv_full.iloc[:cutoff].copy()
        signals_truncated = strategy.generate_signals(ohlcv_truncated)
        signals_full = strategy.generate_signals(ohlcv_full)

        pd.testing.assert_series_equal(
            signals_truncated.reset_index(drop=True),
            signals_full.iloc[:cutoff].reset_index(drop=True),
            check_names=False,
            obj="signals at cutoff must not change when future data is added",
        )

    def test_signal_index_aligned_with_input(self):
        strategy = SmaCross(fast=10, slow=30)
        ohlcv = _synthetic_ohlcv(n=200, seed=42)
        signals = strategy.generate_signals(ohlcv)
        assert len(signals) == len(ohlcv)
        pd.testing.assert_index_equal(signals.index, ohlcv.index)

    def test_signal_values_in_valid_range(self):
        strategy = SmaCross(fast=10, slow=30)
        ohlcv = _synthetic_ohlcv(n=200, seed=42)
        signals = strategy.generate_signals(ohlcv)
        assert (signals >= -1.0).all() and (signals <= 1.0).all()

    def test_conftest_assert_no_lookahead_fixture(self):
        assert_no_lookahead_bias(SmaCross, fast=10, slow=30)

    def test_oracle_shuffle_sma_cross_allow_short(self):
        assert_no_lookahead_bias(SmaCross, fast=10, slow=30, allow_short=True)

    def test_truncation_sma_cross_allow_short(self):
        strategy = SmaCross(fast=10, slow=30, allow_short=True)
        ohlcv_full = _synthetic_ohlcv(n=300, seed=123)
        cutoff = 200
        ohlcv_truncated = ohlcv_full.iloc[:cutoff].copy()
        signals_truncated = strategy.generate_signals(ohlcv_truncated)
        signals_full = strategy.generate_signals(ohlcv_full)
        pd.testing.assert_series_equal(
            signals_truncated.reset_index(drop=True),
            signals_full.iloc[:cutoff].reset_index(drop=True),
            check_names=False,
            obj="short-signals must not lookahead",
        )
