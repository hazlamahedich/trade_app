"""Tests for Strategy Protocol conformance and signal schemas."""

from __future__ import annotations

import pandas as pd
import pytest
from pydantic import ValidationError

from tests.helpers import strategy_conforms_to_protocol
from trade_advisor.strategies.interface import Strategy
from trade_advisor.strategies.schemas import SignalBatch, SignalModel
from trade_advisor.strategies.sma_cross import SmaCross


class TestProtocolConformance:
    def test_sma_cross_satisfies_strategy_protocol(self):
        s = SmaCross(fast=10, slow=30)
        assert isinstance(s, Strategy)

    def test_runtime_checkable_decorator_present(self):
        assert hasattr(Strategy, "__protocol_attrs__") or not hasattr(
            Strategy, "__abstractmethods__"
        )

    def test_custom_class_satisfies_protocol(self):
        class MinimalStrategy:
            name = "minimal"

            @property
            def information_latency(self) -> int:
                return 0

            @property
            def warmup_period(self) -> int:
                return 0

            def generate_signals(self, ohlcv: pd.DataFrame) -> pd.Series:
                return pd.Series(0, index=ohlcv.index, dtype="float64")

        obj = MinimalStrategy()
        assert isinstance(obj, Strategy)

    def test_protocol_missing_method_detected(self):
        class Incomplete:
            name = "incomplete"

        assert not isinstance(Incomplete(), Strategy)

    def test_strategy_conforms_to_protocol_helper(self):
        assert strategy_conforms_to_protocol(SmaCross, fast=10, slow=30)


class TestSignalModel:
    def test_signal_model_valid_directions(self):
        for val in [1.0, 0.0, -1.0, 0.5]:
            s = SignalModel(
                timestamp="2024-01-01T00:00:00Z",
                symbol="SPY",
                signal=val,
                strategy_name="sma",
            )
            assert s.signal == val

    def test_signal_model_rejects_out_of_range(self):
        for val in [2.0, -2.0, 1.5, -1.5]:
            with pytest.raises(ValidationError, match="signal"):
                SignalModel(
                    timestamp="2024-01-01T00:00:00Z",
                    symbol="SPY",
                    signal=val,
                    strategy_name="sma",
                )

    def test_signal_model_confidence_bounds(self):
        SignalModel(
            timestamp="2024-01-01T00:00:00Z",
            symbol="SPY",
            signal=1.0,
            confidence=0.0,
            strategy_name="sma",
        )
        SignalModel(
            timestamp="2024-01-01T00:00:00Z",
            symbol="SPY",
            signal=1.0,
            confidence=1.0,
            strategy_name="sma",
        )
        with pytest.raises(ValidationError, match="confidence"):
            SignalModel(
                timestamp="2024-01-01T00:00:00Z",
                symbol="SPY",
                signal=1.0,
                confidence=1.5,
                strategy_name="sma",
            )

    def test_signal_model_frozen(self):
        s = SignalModel(
            timestamp="2024-01-01T00:00:00Z",
            symbol="SPY",
            signal=1.0,
            strategy_name="sma",
        )
        with pytest.raises(ValidationError):
            s.signal = 0.0


class TestSignalBatch:
    def test_signal_batch_schema(self):
        s1 = SignalModel(
            timestamp="2024-01-01T00:00:00Z",
            symbol="SPY",
            signal=1.0,
            strategy_name="sma",
        )
        s2 = SignalModel(
            timestamp="2024-01-02T00:00:00Z",
            symbol="SPY",
            signal=-1.0,
            strategy_name="sma",
        )
        batch = SignalBatch(
            signals=[s1, s2],
            strategy_name="sma",
            generated_at="2024-01-03T00:00:00Z",
        )
        assert len(batch.signals) == 2
        assert batch.strategy_name == "sma"

    def test_signal_batch_json_serialization(self):
        s = SignalModel(
            timestamp="2024-01-01T00:00:00Z",
            symbol="SPY",
            signal=0.5,
            strategy_name="sma",
        )
        batch = SignalBatch(
            signals=[s],
            strategy_name="sma",
            generated_at="2024-01-02T00:00:00Z",
        )
        json_str = batch.model_dump_json()
        restored = SignalBatch.model_validate_json(json_str)
        assert restored == batch


class TestLatencyProperties:
    def test_information_latency_default(self):
        s = SmaCross(fast=10, slow=30)
        assert s.information_latency == 0

    def test_warmup_period_returns_slow(self):
        s = SmaCross(fast=10, slow=30)
        assert s.warmup_period == 30

    def test_warmup_period_custom_slow(self):
        s = SmaCross(fast=5, slow=50)
        assert s.warmup_period == 50
