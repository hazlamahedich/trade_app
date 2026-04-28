"""Property-based tests for signal schemas."""

from __future__ import annotations

from datetime import UTC, datetime

from hypothesis import given, settings
from hypothesis import strategies as st

from trade_advisor.strategies.schemas import SignalBatch, SignalModel

_signal_st = st.sampled_from([-1.0, 0.0, 1.0]) | st.floats(
    min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False
)
_confidence_st = st.none() | st.floats(
    min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
)
_name_st = st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N")))


@settings(max_examples=200)
@given(signal=_signal_st, confidence=_confidence_st, name=_name_st)
def test_signal_model_round_trip(signal: float, confidence: float | None, name: str):
    ts = datetime(2026, 1, 1, tzinfo=UTC)
    m = SignalModel(
        timestamp=ts, symbol="TEST", signal=signal, confidence=confidence, strategy_name=name
    )
    assert m.signal == signal
    assert m.confidence == confidence


@settings(max_examples=100)
@given(signals=st.lists(_signal_st, min_size=1, max_size=50), name=_name_st)
def test_signal_batch_consistency(signals: list[float], name: str):
    ts = datetime(2026, 1, 1, tzinfo=UTC)
    models = [
        SignalModel(timestamp=ts, symbol="TEST", signal=s, strategy_name=name) for s in signals
    ]
    batch = SignalBatch(signals=models, strategy_name=name, generated_at=ts)
    assert len(batch.signals) == len(signals)
    assert all(s.strategy_name == name for s in batch.signals)


@settings(max_examples=100)
@given(
    out_of_range=st.one_of(
        st.floats(max_value=-1.01, allow_nan=False, allow_infinity=False),
        st.floats(min_value=1.01, allow_nan=False, allow_infinity=False),
    )
)
def test_signal_rejects_out_of_range(out_of_range: float):
    ts = datetime(2026, 1, 1, tzinfo=UTC)
    try:
        SignalModel(timestamp=ts, symbol="TEST", signal=out_of_range, strategy_name="test")
        raise AssertionError(f"Expected ValueError for signal={out_of_range}")
    except ValueError:
        pass
