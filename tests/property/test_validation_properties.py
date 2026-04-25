from __future__ import annotations

import numpy as np
import pandas as pd
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.extra.pandas import columns, data_frames, series

from trade_advisor.data.validation import (
    AnomalySeverity,
    detect_anomalies,
)


def _valid_ohlcv_df(n_rows: int) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    close = 100.0 + rng.standard_normal(n_rows).cumsum() * 0.5
    close = np.maximum(close, 1.0)
    op = close * (1 + rng.standard_normal(n_rows) * 0.01)
    high = np.maximum(op, close) * (1 + np.abs(rng.standard_normal(n_rows) * 0.005))
    low = np.minimum(op, close) * (1 - np.abs(rng.standard_normal(n_rows) * 0.005))
    low = np.maximum(low, 0.01)
    vol = rng.integers(500_000, 5_000_000, size=n_rows).astype(float)
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n_rows, tz="UTC"),
        "open": op, "high": high, "low": low, "close": close, "volume": vol,
    })


@settings(max_examples=50)
@given(n_rows=st.integers(min_value=0, max_value=200))
def test_input_never_mutated(n_rows: int):
    if n_rows == 0:
        df = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
    else:
        df = _valid_ohlcv_df(n_rows)
    original = df.copy()
    detect_anomalies(df, symbol="TEST")
    pd.testing.assert_frame_equal(df, original)


@settings(max_examples=50)
@given(n_rows=st.integers(min_value=2, max_value=200))
def test_no_duplicate_anomaly_entries(n_rows: int):
    df = _valid_ohlcv_df(n_rows)
    result = detect_anomalies(df, symbol="TEST")
    messages = [(a.severity, a.row_index, a.column, a.message) for a in result.anomalies]
    assert len(messages) == len(set(messages))


@settings(max_examples=30)
@given(n_rows=st.integers(min_value=5, max_value=50))
def test_constant_close_no_outlier(n_rows: int):
    df = _valid_ohlcv_df(n_rows)
    df["close"] = 100.0
    df["open"] = 100.0
    df["high"] = 100.0
    df["low"] = 100.0
    result = detect_anomalies(df, symbol="TEST")
    outlier_anomalies = [a for a in result.anomalies if "outlier" in a.message.lower()]
    assert len(outlier_anomalies) == 0


@settings(max_examples=50)
@given(n_rows=st.integers(min_value=0, max_value=200))
def test_result_always_has_correct_level(n_rows: int):
    if n_rows == 0:
        df = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
    else:
        df = _valid_ohlcv_df(n_rows)
    result = detect_anomalies(df, symbol="TEST")
    has_errors = any(a.severity == AnomalySeverity.ERROR for a in result.anomalies)
    has_warnings = any(a.severity == AnomalySeverity.WARNING for a in result.anomalies)
    if has_errors:
        assert result.level.value == "FAIL"
    elif has_warnings:
        assert result.level.value == "WARN"
    else:
        assert result.level.value == "PASS"
