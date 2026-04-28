"""Tests for data/sources.py — yfinance normalization."""

from __future__ import annotations

import pandas as pd
import pytest

from trade_advisor.data.sources import CANONICAL_COLUMNS, _normalize


class TestNormalize:
    def test_normalize_standard_columns(self):
        raw = pd.DataFrame(
            {
                "Open": [100.0],
                "High": [101.0],
                "Low": [99.0],
                "Close": [100.5],
                "Adj Close": [100.3],
                "Volume": [1000000],
            },
            index=pd.date_range("2024-01-01", periods=1, tz="UTC"),
        )
        result = _normalize(raw, symbol="SPY", interval="1d")
        assert set(result.columns) == set(CANONICAL_COLUMNS)
        assert result["symbol"].iloc[0] == "SPY"
        assert result["interval"].iloc[0] == "1d"
        assert result["source"].iloc[0] == "yfinance"
        assert result["volume"].dtype == "int64"

    def test_normalize_missing_adj_close_imputes_close(self):
        raw = pd.DataFrame(
            {
                "Open": [100.0],
                "High": [101.0],
                "Low": [99.0],
                "Close": [100.5],
                "Volume": [500000],
            },
            index=pd.date_range("2024-01-01", periods=1, tz="UTC"),
        )
        result = _normalize(raw, symbol="AAPL", interval="1d")
        assert (result["adj_close"] == result["close"]).all()

    def test_normalize_multiindex_columns(self):
        cols = pd.MultiIndex.from_tuples(
            [("Open", "SPY"), ("High", "SPY"), ("Low", "SPY"), ("Close", "SPY"), ("Volume", "SPY")]
        )
        raw = pd.DataFrame(
            [[100.0, 101.0, 99.0, 100.5, 1000000]],
            columns=cols,
            index=pd.date_range("2024-01-01", periods=1, tz="UTC"),
        )
        result = _normalize(raw, symbol="SPY", interval="1d")
        assert "open" in result.columns
        assert len(result) == 1

    def test_normalize_missing_required_column_raises(self):
        raw = pd.DataFrame(
            {"Open": [100.0], "Close": [100.5]},
            index=pd.date_range("2024-01-01", periods=1, tz="UTC"),
        )
        with pytest.raises(ValueError, match="missing columns"):
            _normalize(raw, symbol="BAD", interval="1d")

    def test_normalize_deduplicates_timestamps(self):
        raw = pd.DataFrame(
            {
                "Open": [100.0, 100.0],
                "High": [101.0, 101.0],
                "Low": [99.0, 99.0],
                "Close": [100.5, 100.5],
                "Volume": [1000000, 1000000],
            },
            index=pd.to_datetime(["2024-01-01", "2024-01-01"], utc=True),
        )
        result = _normalize(raw, symbol="SPY", interval="1d")
        assert len(result) == 1

    def test_normalize_sorted_by_timestamp(self):
        raw = pd.DataFrame(
            {
                "Open": [102.0, 100.0, 101.0],
                "High": [103.0, 101.0, 102.0],
                "Low": [101.0, 99.0, 100.0],
                "Close": [102.5, 100.5, 101.5],
                "Volume": [1000, 2000, 1500],
            },
            index=pd.to_datetime(["2024-01-03", "2024-01-01", "2024-01-02"], utc=True),
        )
        result = _normalize(raw, symbol="SPY", interval="1d")
        timestamps = result["timestamp"].tolist()
        assert timestamps == sorted(timestamps)

    def test_normalize_volume_filled_na(self):
        raw = pd.DataFrame(
            {
                "Open": [100.0],
                "High": [101.0],
                "Low": [99.0],
                "Close": [100.5],
                "Volume": [None],
            },
            index=pd.date_range("2024-01-01", periods=1, tz="UTC"),
        )
        result = _normalize(raw, symbol="SPY", interval="1d")
        assert result["volume"].iloc[0] == 0


class TestFetchYfinance:
    def test_fetch_yfinance_empty_raises(self):

        from trade_advisor.data.sources import fetch_yfinance

        with pytest.raises(RuntimeError, match="no data"):
            fetch_yfinance("NONEXISTENT_TICKER_XYZ_12345")
