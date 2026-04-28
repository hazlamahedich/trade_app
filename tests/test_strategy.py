"""Strategy unit tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tests.helpers import assert_no_lookahead_bias
from trade_advisor.strategies.sma_cross import SmaCross, SmaCrossConfig


def test_invalid_windows_rejected():
    with pytest.raises(ValueError):
        SmaCross(fast=50, slow=20)
    with pytest.raises(ValueError):
        SmaCross(fast=0, slow=10)
    with pytest.raises(ValueError):
        SmaCross(fast=10, slow=0)
    with pytest.raises(ValueError):
        SmaCross(fast=10, slow=-1)


def test_signal_values_only_allowed(synthetic_ohlcv):
    sig = SmaCross(fast=10, slow=30).generate_signals(synthetic_ohlcv)
    assert set(sig.unique()).issubset({-1, 0, 1})


def test_long_only_has_no_shorts(synthetic_ohlcv):
    sig = SmaCross(fast=10, slow=30, allow_short=False).generate_signals(synthetic_ohlcv)
    assert (sig < 0).sum() == 0


def test_short_mode_can_produce_shorts(synthetic_ohlcv):
    sig = SmaCross(fast=10, slow=30, allow_short=True).generate_signals(synthetic_ohlcv)
    assert (sig == -1).sum() > 0


def test_no_lookahead_signals_are_shifted(synthetic_ohlcv):
    """The signal at bar t must depend only on bars <= t-1."""
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
    assert (sig.iloc[:slow] == 0).all()


def test_information_latency_is_one():
    assert SmaCross(fast=10, slow=30).information_latency == 1


def test_warmup_period_returns_slow():
    assert SmaCross(fast=10, slow=30).warmup_period == 30


def test_config_json_roundtrip(synthetic_ohlcv):
    original = SmaCross(fast=14, slow=30, allow_short=True)
    cfg = original.to_config()
    json_str = cfg.model_dump_json()
    restored_cfg = SmaCrossConfig.model_validate_json(json_str)
    restored = SmaCross.from_config(restored_cfg)
    pd.testing.assert_series_equal(
        original.generate_signals(synthetic_ohlcv),
        restored.generate_signals(synthetic_ohlcv),
    )


def test_config_deterministic_signals(synthetic_ohlcv):
    strat = SmaCross(fast=10, slow=30)
    s1 = strat.generate_signals(synthetic_ohlcv)
    s2 = strat.generate_signals(synthetic_ohlcv)
    pd.testing.assert_series_equal(s1, s2)


def test_config_captures_all_parameters():
    cfg = SmaCross(fast=14, slow=30, allow_short=True).to_config()
    dumped = cfg.model_dump()
    assert dumped["fast"] == 14
    assert dumped["slow"] == 30
    assert dumped["allow_short"] is True


def test_config_round_trip_preserves_all_fields():
    original = SmaCrossConfig(fast=10, slow=30, allow_short=True)
    strategy = SmaCross.from_config(original)
    restored = strategy.to_config()
    assert restored == original


def test_empty_dataframe_returns_empty_series():
    empty = pd.DataFrame(columns=["close"])
    sig = SmaCross(fast=5, slow=10).generate_signals(empty)
    assert len(sig) == 0
    assert sig.dtype == np.float64


def test_single_bar_dataframe_returns_flat():
    single = pd.DataFrame({"close": [100.0], "adj_close": [100.0]})
    sig = SmaCross(fast=5, slow=10).generate_signals(single)
    assert len(sig) == 1
    assert sig.iloc[0] == 0.0


def test_window_exceeds_data_length_returns_all_flat():
    short = pd.DataFrame({"close": range(5), "adj_close": range(5)})
    sig = SmaCross(fast=5, slow=10).generate_signals(short)
    assert len(sig) == 5
    assert (sig == 0.0).all()


def test_fast_equals_slow_rejected():
    with pytest.raises(ValueError):
        SmaCross(fast=10, slow=10)
    with pytest.raises(ValueError):
        SmaCrossConfig(fast=10, slow=10)


def test_to_signal_batch_correct_count_timestamps_values():
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2020-01-01", periods=200, tz="UTC")
    df = pd.DataFrame(
        {"close": rng.normal(100, 5, 200), "adj_close": rng.normal(100, 5, 200)},
        index=dates,
    )
    strat = SmaCross(fast=10, slow=30)
    batch = strat.to_signal_batch(df, "TEST")
    assert batch.strategy_name == "sma_cross"
    for s in batch.signals:
        assert s.symbol == "TEST"
        assert s.signal != 0.0
        assert s.strategy_name == "sma_cross"
        assert s.timestamp.tzinfo is not None


def test_to_signal_batch_rejects_range_index(synthetic_ohlcv):
    strat = SmaCross(fast=10, slow=30)
    with pytest.raises(TypeError, match="DatetimeIndex"):
        strat.to_signal_batch(synthetic_ohlcv, "TEST")


def test_no_lookahead_adversarial():
    assert_no_lookahead_bias(SmaCross, fast=10, slow=20)


def test_fast_equals_one_produces_valid_signals():
    rng = np.random.default_rng(42)
    df = pd.DataFrame({"close": rng.normal(100, 5, 100), "adj_close": rng.normal(100, 5, 100)})
    sig = SmaCross(fast=1, slow=5).generate_signals(df)
    assert len(sig) == 100
    assert sig.isna().sum() == 0
    assert (sig.iloc[:5] == 0.0).all()


def test_nan_close_produces_flat_signals():
    n = 100
    rng = np.random.default_rng(42)
    vals = rng.normal(100, 5, n).astype(float)
    vals[50:60] = np.nan
    df = pd.DataFrame({"close": vals, "adj_close": vals})
    sig = SmaCross(fast=10, slow=30).generate_signals(df)
    assert len(sig) == n
    assert sig.isna().sum() == 0
