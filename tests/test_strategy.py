"""Strategy unit tests."""

from __future__ import annotations

import pandas as pd
import pytest

from trade_advisor.strategies.sma_cross import SmaCross


def test_invalid_windows_rejected():
    with pytest.raises(ValueError):
        SmaCross(fast=50, slow=20)
    with pytest.raises(ValueError):
        SmaCross(fast=0, slow=10)


def test_signal_values_only_allowed(synthetic_ohlcv):
    sig = SmaCross(fast=10, slow=30).generate_signals(synthetic_ohlcv)
    assert set(sig.unique()).issubset({-1, 0, 1})


def test_long_only_has_no_shorts(synthetic_ohlcv):
    sig = SmaCross(fast=10, slow=30, allow_short=False).generate_signals(synthetic_ohlcv)
    assert (sig < 0).sum() == 0


def test_short_mode_can_produce_shorts(synthetic_ohlcv):
    sig = SmaCross(fast=10, slow=30, allow_short=True).generate_signals(synthetic_ohlcv)
    # With 500 random bars there should almost certainly be bearish stretches.
    assert (sig == -1).sum() > 0


def test_no_lookahead_signals_are_shifted(synthetic_ohlcv):
    """The signal at bar t must depend only on bars <= t-1.

    We test this by construction: replacing future bars must not change
    the early signals.
    """
    strat = SmaCross(fast=10, slow=30)
    sig_full = strat.generate_signals(synthetic_ohlcv)

    truncated = synthetic_ohlcv.iloc[:200].copy()
    sig_trunc = strat.generate_signals(truncated)

    pd.testing.assert_series_equal(
        sig_full.iloc[:200].reset_index(drop=True),
        sig_trunc.reset_index(drop=True),
        check_names=False,
    )


def test_warmup_bars_are_flat(synthetic_ohlcv):
    """Before the slow window has filled, there is no signal."""
    slow = 50
    sig = SmaCross(fast=10, slow=slow).generate_signals(synthetic_ohlcv)
    # The slow SMA requires ``slow`` bars; with the +1 lookahead shift,
    # signals must be zero for at least the first ``slow`` bars.
    assert (sig.iloc[:slow] == 0).all()
