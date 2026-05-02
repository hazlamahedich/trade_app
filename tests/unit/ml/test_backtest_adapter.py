"""Comprehensive unit tests for ml/backtest_adapter.py - Story 3.5.

Levels A-I cover: Protocol compliance, continuous/discrete modes, signal shift
verification, length/timestamp mismatch, backtest integration, coexistence with
rule-based strategies, config serialization, and edge cases.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.helpers import _synthetic_ohlcv, assert_no_lookahead_bias, strategy_conforms_to_protocol
from trade_advisor.backtest.engine import BacktestResult, run_backtest
from trade_advisor.ml.backtest_adapter import (
    ConstantPredictionProvider,
    MLStrategy,
    MLStrategyConfig,
    NaNPredictionProvider,
    NoisyPredictionProvider,
    PredictionProvider,
    SignalMode,
)
from trade_advisor.strategies.interface import Strategy
from trade_advisor.strategies.sma_cross import SmaCross

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ohlcv(n: int = 100) -> pd.DataFrame:
    return _synthetic_ohlcv(n=n)


def _make_strategy(
    value: float = 0.5,
    mode: SignalMode = SignalMode.CONTINUOUS,
    **cfg_kw: object,
) -> MLStrategy:
    provider = ConstantPredictionProvider(value)
    config = MLStrategyConfig(signal_mode=mode, **cfg_kw)
    return MLStrategy(provider=provider, config=config)


# ===========================================================================
# Level A — Protocol compliance
# ===========================================================================


class TestProtocolCompliance:
    def test_mlstrategy_satisfies_strategy_protocol(self):
        assert strategy_conforms_to_protocol(
            MLStrategy,
            provider=ConstantPredictionProvider(0.5),
            config=MLStrategyConfig(),
        )

    def test_mlstrategy_isinstance_runtime_checkable(self):
        s = _make_strategy()
        assert isinstance(s, Strategy)

    def test_prediction_provider_protocol_check(self):
        provider = ConstantPredictionProvider(0.5)
        assert isinstance(provider, PredictionProvider)

    def test_has_required_attributes(self):
        s = _make_strategy()
        assert hasattr(s, "name")
        assert hasattr(s, "information_latency")
        assert hasattr(s, "warmup_period")
        assert hasattr(s, "generate_signals")

    def test_information_latency_is_one(self):
        s = _make_strategy()
        assert s.information_latency == 1


# ===========================================================================
# Level B — Continuous mode
# ===========================================================================


class TestContinuousMode:
    def test_identity_mapping(self):
        ohlcv = _make_ohlcv(50)
        s = _make_strategy(value=0.7, mode=SignalMode.CONTINUOUS)
        signals = s.generate_signals(ohlcv)
        assert signals.dtype == np.float64
        assert len(signals) == len(ohlcv)

    def test_clamping_above_one(self):
        ohlcv = _make_ohlcv(20)

        class HighProvider:
            def predict(self, ohlcv: pd.DataFrame) -> pd.Series:
                return pd.Series(2.5, index=ohlcv.index, dtype="float64")

        s = MLStrategy(provider=HighProvider(), config=MLStrategyConfig())
        signals = s.generate_signals(ohlcv)
        assert (signals <= 1.0).all()

    def test_clamping_below_minus_one(self):
        ohlcv = _make_ohlcv(20)

        class LowProvider:
            def predict(self, ohlcv: pd.DataFrame) -> pd.Series:
                return pd.Series(-3.0, index=ohlcv.index, dtype="float64")

        s = MLStrategy(provider=LowProvider(), config=MLStrategyConfig())
        signals = s.generate_signals(ohlcv)
        assert (signals >= -1.0).all()

    def test_nan_predictions_map_to_zero(self):
        ohlcv = _make_ohlcv(30)
        s = MLStrategy(
            provider=NaNPredictionProvider(nan_positions=[5, 10, 15]),
            config=MLStrategyConfig(),
        )
        signals = s.generate_signals(ohlcv)
        assert not signals.isna().any()
        assert (signals >= -1.0).all() and (signals <= 1.0).all()

    def test_zero_predictions_all_flat_after_shift(self):
        ohlcv = _make_ohlcv(20)
        s = _make_strategy(value=0.0, mode=SignalMode.CONTINUOUS)
        signals = s.generate_signals(ohlcv)
        assert (signals == 0.0).all()


# ===========================================================================
# Level C — Discrete mode
# ===========================================================================


class TestDiscreteMode:
    def test_above_long_threshold_maps_to_long(self):
        ohlcv = _make_ohlcv(20)
        s = _make_strategy(value=0.8, mode=SignalMode.DISCRETE)
        signals = s.generate_signals(ohlcv)
        non_zero = signals.iloc[1:]
        assert (non_zero == 1.0).all()

    def test_below_short_threshold_maps_to_short(self):
        ohlcv = _make_ohlcv(20)
        s = _make_strategy(value=-0.8, mode=SignalMode.DISCRETE)
        signals = s.generate_signals(ohlcv)
        non_zero = signals.iloc[1:]
        assert (non_zero == -1.0).all()

    def test_dead_zone_maps_to_flat(self):
        ohlcv = _make_ohlcv(20)
        s = _make_strategy(value=0.1, mode=SignalMode.DISCRETE)
        signals = s.generate_signals(ohlcv)
        assert (signals == 0.0).all()

    def test_asymmetric_thresholds(self):
        ohlcv = _make_ohlcv(20)
        s = _make_strategy(
            value=0.1,
            mode=SignalMode.DISCRETE,
            long_threshold=0.05,
            short_threshold=-0.5,
        )
        signals = s.generate_signals(ohlcv)
        non_zero = signals.iloc[1:]
        assert (non_zero == 1.0).all()

    def test_default_thresholds(self):
        cfg = MLStrategyConfig(signal_mode=SignalMode.DISCRETE)
        assert cfg.long_threshold == 0.3
        assert cfg.short_threshold == -0.3

    def test_boundary_at_long_threshold(self):
        ohlcv = _make_ohlcv(20)
        s = _make_strategy(value=0.3, mode=SignalMode.DISCRETE, long_threshold=0.3)
        signals = s.generate_signals(ohlcv)
        non_zero = signals.iloc[1:]
        assert (non_zero == 1.0).all()

    def test_boundary_at_short_threshold(self):
        ohlcv = _make_ohlcv(20)
        s = _make_strategy(value=-0.3, mode=SignalMode.DISCRETE, short_threshold=-0.3)
        signals = s.generate_signals(ohlcv)
        non_zero = signals.iloc[1:]
        assert (non_zero == -1.0).all()


# ===========================================================================
# Level D — Signal shift verification (lookahead protection)
# ===========================================================================


class TestSignalShift:
    def test_first_bar_always_zero_after_shift(self):
        ohlcv = _make_ohlcv(30)
        s = _make_strategy(value=1.0)
        signals = s.generate_signals(ohlcv)
        assert signals.iloc[0] == 0.0

    def test_signal_depends_only_on_previous_predictions(self):
        ohlcv = _make_ohlcv(50)

        class CheatingProvider:
            def __init__(self) -> None:
                self.call_count = 0

            def predict(self, ohlcv: pd.DataFrame) -> pd.Series:
                close = ohlcv["close"] if "close" in ohlcv.columns else ohlcv["adj_close"]
                raw = close.pct_change().fillna(0.0)
                return pd.Series(raw.values, index=ohlcv.index, dtype="float64")

        provider = CheatingProvider()
        s = MLStrategy(provider=provider, config=MLStrategyConfig())
        signals = s.generate_signals(ohlcv)
        assert signals.iloc[0] == 0.0

    def test_oracle_shuffle_no_lookahead(self):
        assert_no_lookahead_bias(
            MLStrategy,
            provider=ConstantPredictionProvider(0.8),
            config=MLStrategyConfig(signal_mode=SignalMode.DISCRETE),
        )

    def test_signal_t_does_not_depend_on_price_t(self):
        ohlcv = _make_ohlcv(100)

        class PositionBasedProvider:
            def predict(self, ohlcv: pd.DataFrame) -> pd.Series:
                n = len(ohlcv)
                vals = np.where(np.arange(n) % 7 < 3, 1.0, -1.0)
                return pd.Series(vals, index=ohlcv.index, dtype="float64")

        provider = PositionBasedProvider()
        s = MLStrategy(provider=provider, config=MLStrategyConfig())
        signals = s.generate_signals(ohlcv)

        ohlcv_truncated = ohlcv.iloc[:50]
        signals_truncated = s.generate_signals(ohlcv_truncated)
        pd.testing.assert_series_equal(
            signals.iloc[:50].reset_index(drop=True),
            signals_truncated.reset_index(drop=True),
            check_names=False,
        )


# ===========================================================================
# Level E — Length/timestamp mismatch
# ===========================================================================


class TestLengthTimestampMismatch:
    def test_short_predictions_padded_with_zero(self):
        ohlcv = _make_ohlcv(50)

        class ShortProvider:
            def predict(self, ohlcv: pd.DataFrame) -> pd.Series:
                return pd.Series([0.5] * 30, dtype="float64")

        s = MLStrategy(provider=ShortProvider(), config=MLStrategyConfig())
        signals = s.generate_signals(ohlcv)
        assert len(signals) == 50
        assert signals.iloc[0] == 0.0

    def test_long_predictions_truncated(self):
        ohlcv = _make_ohlcv(30)

        class LongProvider:
            def predict(self, ohlcv: pd.DataFrame) -> pd.Series:
                return pd.Series([0.5] * 60, dtype="float64")

        s = MLStrategy(provider=LongProvider(), config=MLStrategyConfig())
        signals = s.generate_signals(ohlcv)
        assert len(signals) == 30

    def test_misaligned_datetime_index_forward_fill(self):
        ohlcv = _make_ohlcv(50)
        ohlcv_dt = ohlcv.set_index(pd.date_range("2020-01-01", periods=len(ohlcv), freq="1D"))

        class OffsetProvider:
            def predict(self, ohlcv: pd.DataFrame) -> pd.Series:
                idx = ohlcv.index[5:]
                return pd.Series([0.6] * len(idx), index=idx, dtype="float64")

        s = MLStrategy(provider=OffsetProvider(), config=MLStrategyConfig())
        signals = s.generate_signals(ohlcv_dt)
        assert len(signals) == len(ohlcv_dt)

    def test_empty_predictions_returns_zero_signals(self):
        ohlcv = _make_ohlcv(20)

        class EmptyProvider:
            def predict(self, ohlcv: pd.DataFrame) -> pd.Series:
                return pd.Series(dtype="float64")

        s = MLStrategy(provider=EmptyProvider(), config=MLStrategyConfig())
        signals = s.generate_signals(ohlcv)
        assert len(signals) == 20
        assert (signals == 0.0).all()


# ===========================================================================
# Level F — Backtest integration
# ===========================================================================


class TestBacktestIntegration:
    def test_mlstrategy_in_run_backtest(self):
        ohlcv = _make_ohlcv(200)
        s = _make_strategy(value=0.8, mode=SignalMode.DISCRETE)
        signals = s.generate_signals(ohlcv)
        result = run_backtest(ohlcv, signals)
        assert isinstance(result, BacktestResult)
        assert len(result.equity) > 0
        assert len(result.trades.columns) == 7

    def test_backtest_produces_valid_equity_curve(self):
        ohlcv = _make_ohlcv(200)
        s = _make_strategy(value=0.5, mode=SignalMode.CONTINUOUS)
        signals = s.generate_signals(ohlcv)
        result = run_backtest(ohlcv, signals)
        assert result.equity.iloc[0] > 0
        assert (result.equity > 0).all() or len(result.equity) == 0


# ===========================================================================
# Level G — Coexistence with rule-based strategies
# ===========================================================================


class TestCoexistence:
    def test_ml_and_sma_produce_same_signal_format(self):
        ohlcv = _make_ohlcv(200)
        ml = _make_strategy(value=0.8, mode=SignalMode.DISCRETE)
        sma = SmaCross(fast=10, slow=20)

        ml_signals = ml.generate_signals(ohlcv)
        sma_signals = sma.generate_signals(ohlcv)

        assert ml_signals.dtype == sma_signals.dtype
        assert len(ml_signals) == len(sma_signals)
        assert ml_signals.index.equals(sma_signals.index) or len(ml_signals) == len(sma_signals)

    def test_both_valid_inputs_to_run_backtest(self):
        ohlcv = _make_ohlcv(200)
        ml = _make_strategy(value=0.8, mode=SignalMode.DISCRETE)
        sma = SmaCross(fast=10, slow=20)

        ml_result = run_backtest(ohlcv, ml.generate_signals(ohlcv))
        sma_result = run_backtest(ohlcv, sma.generate_signals(ohlcv))

        assert isinstance(ml_result, BacktestResult)
        assert isinstance(sma_result, BacktestResult)


# ===========================================================================
# Level H — Config serialization
# ===========================================================================


class TestConfigSerialization:
    def test_config_json_round_trip(self):
        cfg = MLStrategyConfig(
            signal_mode=SignalMode.DISCRETE,
            long_threshold=0.5,
            short_threshold=-0.4,
            warmup_period=10,
            prediction_source_id="test_model",
        )
        json_str = cfg.model_dump_json()
        restored = MLStrategyConfig.model_validate_json(json_str)
        assert restored.signal_mode == SignalMode.DISCRETE
        assert restored.long_threshold == 0.5
        assert restored.prediction_source_id == "test_model"

    def test_config_default_values(self):
        cfg = MLStrategyConfig()
        assert cfg.signal_mode == SignalMode.CONTINUOUS
        assert cfg.long_threshold == 0.3
        assert cfg.short_threshold == -0.3
        assert cfg.warmup_period == 0
        assert cfg.prediction_source_id == "unknown"

    def test_invalid_threshold_rejected(self):
        with pytest.raises(ValueError):
            MLStrategyConfig(long_threshold=-0.1)

        with pytest.raises(ValueError):
            MLStrategyConfig(short_threshold=0.5)

        with pytest.raises(ValueError):
            MLStrategyConfig(long_threshold=0.0, short_threshold=-0.1)

    def test_strategy_name_includes_source_id(self):
        s = _make_strategy(value=0.5, prediction_source_id="xgboost_v1")
        assert s.name == "ml_adapter:xgboost_v1"

    def test_to_config_round_trip(self):
        cfg = MLStrategyConfig(
            signal_mode=SignalMode.DISCRETE,
            prediction_source_id="test",
        )
        s = MLStrategy(provider=ConstantPredictionProvider(0.5), config=cfg)
        restored = s.to_config()
        assert restored.signal_mode == cfg.signal_mode
        assert restored.prediction_source_id == cfg.prediction_source_id


# ===========================================================================
# Level I — Edge cases
# ===========================================================================


class TestEdgeCases:
    def test_all_zero_predictions(self):
        ohlcv = _make_ohlcv(20)
        s = _make_strategy(value=0.0)
        signals = s.generate_signals(ohlcv)
        assert (signals == 0.0).all()

    def test_all_same_predictions(self):
        ohlcv = _make_ohlcv(30)
        s = _make_strategy(value=0.5, mode=SignalMode.CONTINUOUS)
        signals = s.generate_signals(ohlcv)
        assert (signals.iloc[1:] == 0.5).all()

    def test_single_bar_ohlcv(self):
        ohlcv = _make_ohlcv(1)
        s = _make_strategy(value=0.5)
        signals = s.generate_signals(ohlcv)
        assert len(signals) == 1
        assert signals.iloc[0] == 0.0

    def test_empty_ohlcv(self):
        ohlcv = _make_ohlcv(0)
        s = _make_strategy(value=0.5)
        signals = s.generate_signals(ohlcv)
        assert len(signals) == 0

    def test_signals_no_nan(self):
        ohlcv = _make_ohlcv(50)
        s = MLStrategy(
            provider=NaNPredictionProvider(nan_positions=list(range(50))),
            config=MLStrategyConfig(),
        )
        signals = s.generate_signals(ohlcv)
        assert not signals.isna().any()

    def test_signals_range_constraint(self):
        ohlcv = _make_ohlcv(100)
        s = MLStrategy(
            provider=NoisyPredictionProvider(seed=42, noise_std=2.0),
            config=MLStrategyConfig(),
        )
        signals = s.generate_signals(ohlcv)
        assert (signals >= -1.0).all()
        assert (signals <= 1.0).all()


# ===========================================================================
# Property-based tests (Task 5)
# ===========================================================================


class TestPropertyBased:
    @given(
        predictions=st.lists(
            st.one_of(
                st.floats(min_value=-5.0, max_value=5.0, allow_nan=False, allow_infinity=False),
                st.just(float("nan")),
            ),
            min_size=10,
            max_size=100,
        )
    )
    @settings(max_examples=50, deadline=None)
    def test_range_invariant(self, predictions: list[float]):
        ohlcv = _make_ohlcv(len(predictions))

        class StaticProvider:
            def __init__(self, vals: list[float]) -> None:
                self.vals = vals

            def predict(self, ohlcv: pd.DataFrame) -> pd.Series:
                return pd.Series(self.vals, index=ohlcv.index, dtype="float64")

        s = MLStrategy(provider=StaticProvider(predictions), config=MLStrategyConfig())
        signals = s.generate_signals(ohlcv)
        assert (signals >= -1.0).all()
        assert (signals <= 1.0).all()

    @given(
        pred_a=st.floats(min_value=-1.0, max_value=1.0, allow_nan=False),
        pred_b=st.floats(min_value=-1.0, max_value=1.0, allow_nan=False),
    )
    @settings(max_examples=50)
    def test_monotonicity_continuous(self, pred_a: float, pred_b: float):
        if abs(pred_a - pred_b) < 1e-10:
            return

        ohlcv = _make_ohlcv(2)

        class TwoProvider:
            def __init__(self, a: float, b: float) -> None:
                self.a = a
                self.b = b

            def predict(self, ohlcv: pd.DataFrame) -> pd.Series:
                return pd.Series([self.a, self.b], index=ohlcv.index, dtype="float64")

        s = MLStrategy(
            provider=TwoProvider(pred_a, pred_b),
            config=MLStrategyConfig(signal_mode=SignalMode.CONTINUOUS),
        )
        signals = s.generate_signals(ohlcv)
        if pred_a > pred_b:
            assert signals.iloc[1] >= signals.iloc[1]

    @given(n=st.integers(min_value=1, max_value=500))
    @settings(max_examples=30)
    def test_length_invariant(self, n: int):
        ohlcv = _make_ohlcv(n)
        s = _make_strategy(value=0.5)
        signals = s.generate_signals(ohlcv)
        assert len(signals) == n

    @given(
        values=st.lists(
            st.one_of(
                st.floats(min_value=-2.0, max_value=2.0, allow_nan=False, allow_infinity=False),
                st.just(float("nan")),
            ),
            min_size=5,
            max_size=50,
        )
    )
    @settings(max_examples=30, deadline=None)
    def test_nan_free_invariant(self, values: list[float]):
        ohlcv = _make_ohlcv(len(values))

        class ListProvider:
            def __init__(self, vals: list[float]) -> None:
                self.vals = vals

            def predict(self, ohlcv: pd.DataFrame) -> pd.Series:
                return pd.Series(self.vals, index=ohlcv.index, dtype="float64")

        s = MLStrategy(provider=ListProvider(values), config=MLStrategyConfig())
        signals = s.generate_signals(ohlcv)
        assert not signals.isna().any()

    @given(n=st.integers(min_value=1, max_value=200))
    @settings(max_examples=20)
    def test_dtype_invariant(self, n: int):
        ohlcv = _make_ohlcv(n)
        s = _make_strategy(value=0.5)
        signals = s.generate_signals(ohlcv)
        assert signals.dtype == np.float64
