"""ATDD red-phase tests for Story 3.5: ML-Based Strategy Signal Bridge.

These tests define acceptance criteria contracts.  They should pass once the
story is fully implemented.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tests.helpers import _synthetic_ohlcv
from trade_advisor.backtest.engine import BacktestResult, run_backtest
from trade_advisor.ml.backtest_adapter import (
    MLStrategy,
    MLStrategyConfig,
    SignalMode,
)
from trade_advisor.strategies.interface import Strategy


@pytest.fixture
def ohlcv() -> pd.DataFrame:
    return _synthetic_ohlcv(n=200)


class TestAC1ProtocolCompliance:
    """AC#1: MLStrategy wraps prediction source as Strategy Protocol."""

    @pytest.mark.test_id("3.5-ATDD-001")
    @pytest.mark.p0
    def test_mlstrategy_satisfies_strategy_protocol(self, ohlcv: pd.DataFrame):
        # Given: an MLStrategy with a constant prediction provider
        from trade_advisor.ml.backtest_adapter import ConstantPredictionProvider

        s = MLStrategy(
            provider=ConstantPredictionProvider(0.5),
            config=MLStrategyConfig(),
        )

        # Then: it satisfies the Strategy protocol
        assert isinstance(s, Strategy)

    @pytest.mark.test_id("3.5-ATDD-002")
    @pytest.mark.p0
    def test_generate_signals_returns_float_series(self, ohlcv: pd.DataFrame):
        # Given: an MLStrategy instance
        from trade_advisor.ml.backtest_adapter import ConstantPredictionProvider

        s = MLStrategy(
            provider=ConstantPredictionProvider(0.5),
            config=MLStrategyConfig(),
        )

        # When: generating signals
        signals = s.generate_signals(ohlcv)

        # Then: signals are a float64 Series
        assert isinstance(signals, pd.Series)
        assert signals.dtype == np.float64

    @pytest.mark.test_id("3.5-ATDD-003")
    @pytest.mark.p0
    def test_signals_shifted_by_one_bar(self, ohlcv: pd.DataFrame):
        # Given: an MLStrategy with nonzero prediction
        from trade_advisor.ml.backtest_adapter import ConstantPredictionProvider

        s = MLStrategy(
            provider=ConstantPredictionProvider(0.8),
            config=MLStrategyConfig(),
        )

        # When: generating signals
        signals = s.generate_signals(ohlcv)

        # Then: first bar is 0.0 (shifted)
        assert signals.iloc[0] == 0.0


class TestAC2ContinuousMode:
    """AC#2: Continuous mode — identity mapping with clamping."""

    @pytest.mark.test_id("3.5-ATDD-004")
    @pytest.mark.p0
    def test_identity_mapping(self, ohlcv: pd.DataFrame):
        # Given: an MLStrategy in continuous mode
        from trade_advisor.ml.backtest_adapter import ConstantPredictionProvider

        s = MLStrategy(
            provider=ConstantPredictionProvider(0.6),
            config=MLStrategyConfig(signal_mode=SignalMode.CONTINUOUS),
        )

        # When: generating signals
        signals = s.generate_signals(ohlcv)

        # Then: signal value equals prediction (after shift)
        assert signals.iloc[1] == pytest.approx(0.6)

    @pytest.mark.test_id("3.5-ATDD-005")
    @pytest.mark.p1
    def test_out_of_range_clamped(self, ohlcv: pd.DataFrame):
        # Given: a provider returning out-of-range values

        class ExtremeProvider:
            def predict(self, ohlcv: pd.DataFrame) -> pd.Series:
                return pd.Series(5.0, index=ohlcv.index, dtype="float64")

        s = MLStrategy(provider=ExtremeProvider(), config=MLStrategyConfig())

        # When: generating signals
        signals = s.generate_signals(ohlcv)

        # Then: signals are clamped to [-1.0, 1.0]
        assert signals.max() <= 1.0


class TestAC3DiscreteMode:
    """AC#3: Discrete mode — threshold mapping."""

    @pytest.mark.test_id("3.5-ATDD-006")
    @pytest.mark.p0
    def test_long_threshold_mapping(self, ohlcv: pd.DataFrame):
        # Given: an MLStrategy in discrete mode with high positive prediction
        from trade_advisor.ml.backtest_adapter import ConstantPredictionProvider

        s = MLStrategy(
            provider=ConstantPredictionProvider(0.8),
            config=MLStrategyConfig(signal_mode=SignalMode.DISCRETE),
        )

        # When: generating signals
        signals = s.generate_signals(ohlcv)

        # Then: all non-first bars are +1.0 (long)
        assert (signals.iloc[1:] == 1.0).all()

    @pytest.mark.test_id("3.5-ATDD-007")
    @pytest.mark.p0
    def test_short_threshold_mapping(self, ohlcv: pd.DataFrame):
        # Given: an MLStrategy in discrete mode with strong negative prediction
        from trade_advisor.ml.backtest_adapter import ConstantPredictionProvider

        s = MLStrategy(
            provider=ConstantPredictionProvider(-0.8),
            config=MLStrategyConfig(signal_mode=SignalMode.DISCRETE),
        )

        # When: generating signals
        signals = s.generate_signals(ohlcv)

        # Then: all non-first bars are -1.0 (short)
        assert (signals.iloc[1:] == -1.0).all()

    @pytest.mark.test_id("3.5-ATDD-008")
    @pytest.mark.p1
    def test_dead_zone_flat(self, ohlcv: pd.DataFrame):
        # Given: an MLStrategy in discrete mode with weak prediction
        from trade_advisor.ml.backtest_adapter import ConstantPredictionProvider

        s = MLStrategy(
            provider=ConstantPredictionProvider(0.1),
            config=MLStrategyConfig(signal_mode=SignalMode.DISCRETE),
        )

        # When: generating signals
        signals = s.generate_signals(ohlcv)

        # Then: all signals are 0.0 (flat, in dead zone)
        assert (signals == 0.0).all()


class TestAC4NaNHandling:
    """AC#4: NaN predictions → 0.0 (flat)."""

    @pytest.mark.test_id("3.5-ATDD-009")
    @pytest.mark.p0
    def test_nan_mapped_to_zero(self, ohlcv: pd.DataFrame):
        # Given: a provider that returns NaN at specific positions
        from trade_advisor.ml.backtest_adapter import NaNPredictionProvider

        s = MLStrategy(
            provider=NaNPredictionProvider(nan_positions=[10, 20, 30]),
            config=MLStrategyConfig(),
        )

        # When: generating signals
        signals = s.generate_signals(ohlcv)

        # Then: no NaN values remain
        assert not signals.isna().any()


class TestAC5PredictionLengthMismatch:
    """AC#5: Short predictions padded with 0.0."""

    @pytest.mark.test_id("3.5-ATDD-010")
    @pytest.mark.p1
    def test_short_predictions_padded(self, ohlcv: pd.DataFrame):
        # Given: a provider returning fewer predictions than bars

        class ShortProvider:
            def predict(self, ohlcv: pd.DataFrame) -> pd.Series:
                return pd.Series([0.5] * 100, dtype="float64")

        s = MLStrategy(provider=ShortProvider(), config=MLStrategyConfig())

        # When: generating signals
        signals = s.generate_signals(ohlcv)

        # Then: signals are padded to full length
        assert len(signals) == 200


class TestAC7BacktestIntegration:
    """AC#7: MLStrategy produces valid BacktestResult."""

    @pytest.mark.test_id("3.5-ATDD-011")
    @pytest.mark.p0
    def test_run_backtest_with_ml_strategy(self, ohlcv: pd.DataFrame):
        # Given: an MLStrategy in discrete mode
        from trade_advisor.ml.backtest_adapter import ConstantPredictionProvider

        s = MLStrategy(
            provider=ConstantPredictionProvider(0.8),
            config=MLStrategyConfig(signal_mode=SignalMode.DISCRETE),
        )

        # When: running a backtest
        signals = s.generate_signals(ohlcv)
        result = run_backtest(ohlcv, signals)

        # Then: a valid BacktestResult is produced
        assert isinstance(result, BacktestResult)
        assert len(result.equity) > 0


class TestAC8TestsWithoutMLInfrastructure:
    """AC#8: Works without sklearn or model files."""

    @pytest.mark.test_id("3.5-ATDD-012")
    @pytest.mark.p1
    def test_fake_provider_no_ml_deps(self, ohlcv: pd.DataFrame):
        # Given: a fake prediction provider (no ML deps)
        from trade_advisor.ml.backtest_adapter import ConstantPredictionProvider

        s = MLStrategy(
            provider=ConstantPredictionProvider(0.5),
            config=MLStrategyConfig(),
        )

        # When: generating signals
        signals = s.generate_signals(ohlcv)

        # Then: signals are produced without ML infrastructure
        assert len(signals) == len(ohlcv)


class TestAC9Coexistence:
    """AC#9: ML and rule-based strategies produce compatible signals."""

    @pytest.mark.test_id("3.5-ATDD-013")
    @pytest.mark.p1
    def test_same_signal_format(self, ohlcv: pd.DataFrame):
        # Given: an ML strategy and a rule-based strategy
        from trade_advisor.ml.backtest_adapter import ConstantPredictionProvider
        from trade_advisor.strategies.sma_cross import SmaCross

        ml = MLStrategy(
            provider=ConstantPredictionProvider(0.8),
            config=MLStrategyConfig(signal_mode=SignalMode.DISCRETE),
        )
        sma = SmaCross(fast=10, slow=20)

        # When: generating signals from both
        ml_signals = ml.generate_signals(ohlcv)
        sma_signals = sma.generate_signals(ohlcv)

        # Then: both produce same dtype and length
        assert ml_signals.dtype == sma_signals.dtype
        assert len(ml_signals) == len(sma_signals)
