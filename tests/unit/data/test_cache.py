"""Tests for data/cache.py — Parquet caching layer."""

from __future__ import annotations

import pandas as pd
import pytest

from tests.conftest import _synthetic_ohlcv


class TestParquetCache:
    def test_get_ohlcv_returns_dataframe(self):
        from unittest.mock import patch

        from trade_advisor.data.cache import get_ohlcv

        df = _synthetic_ohlcv(n=50)
        with patch("trade_advisor.data.cache.fetch_yfinance", return_value=df):
            result = get_ohlcv("TEST", start="2020-01-01", interval="1d")
            assert isinstance(result, pd.DataFrame)
            assert len(result) > 0

    def test_load_cached_missing_returns_none(self, tmp_path):
        from trade_advisor.data.cache import load_cached

        with pytest.MonkeyPatch.context() as m:
            m.setenv("DATA_CACHE_DIR", str(tmp_path / "nonexistent"))
            result = load_cached("NOEXIST", "1d")
            assert result is None

    def test_validate_ohlcv_clean_data(self):
        from trade_advisor.data.cache import validate_ohlcv

        df = _synthetic_ohlcv(n=100)
        warnings = validate_ohlcv(df, "TEST")
        assert isinstance(warnings, list)

    def test_validate_ohlcv_nan_detection(self):
        from trade_advisor.data.cache import validate_ohlcv

        df = _synthetic_ohlcv(n=20)
        df.loc[5, "close"] = float("nan")
        warnings = validate_ohlcv(df, "TEST")
        assert any("NaN" in w for w in warnings)

    def test_validate_ohlcv_duplicate_timestamps_raises(self):
        from trade_advisor.data.cache import DataValidationError, validate_ohlcv

        df = _synthetic_ohlcv(n=20)
        df = pd.concat([df, df.iloc[[0]]], ignore_index=True)
        with pytest.raises(DataValidationError, match="duplicate"):
            validate_ohlcv(df, "TEST")

    def test_validate_ohlcv_unsorted_timestamps_raises(self):
        from trade_advisor.data.cache import DataValidationError, validate_ohlcv

        df = _synthetic_ohlcv(n=20)
        df = df.iloc[::-1].reset_index(drop=True)
        with pytest.raises(DataValidationError, match="sorted"):
            validate_ohlcv(df, "TEST")

    def test_validate_ohlcv_non_positive_prices(self):
        from trade_advisor.data.cache import validate_ohlcv

        df = _synthetic_ohlcv(n=20)
        df.loc[5, "close"] = -1.0
        warnings = validate_ohlcv(df, "TEST")
        assert any("non-positive" in w for w in warnings)

    def test_validate_ohlcv_high_less_than_low(self):
        from trade_advisor.data.cache import validate_ohlcv

        df = _synthetic_ohlcv(n=20)
        df.loc[5, "high"] = df.loc[5, "low"] - 5.0
        warnings = validate_ohlcv(df, "TEST")
        assert any("high < low" in w for w in warnings)

    def test_validate_ohlcv_empty_raises(self):
        from trade_advisor.data.cache import DataValidationError, validate_ohlcv

        df = pd.DataFrame(
            columns=[
                "symbol",
                "interval",
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "adj_close",
                "volume",
                "source",
            ]
        )
        with pytest.raises(DataValidationError, match="empty"):
            validate_ohlcv(df, "TEST")

    def test_validate_ohlcv_missing_columns_raises(self):
        from trade_advisor.data.cache import DataValidationError, validate_ohlcv

        df = pd.DataFrame({"close": [100.0]})
        with pytest.raises(DataValidationError, match="missing columns"):
            validate_ohlcv(df, "TEST")
