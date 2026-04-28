"""Tests for CLI data commands — data fetch, status, validate."""

from __future__ import annotations

import json
from unittest.mock import patch

import pandas as pd
import pytest
from tests.conftest import _synthetic_ohlcv
from typer.testing import CliRunner

from trade_advisor.cli import app

runner = CliRunner()


@pytest.fixture
def synthetic_df():
    return _synthetic_ohlcv(n=50)


@pytest.fixture
def mock_get_ohlcv(synthetic_df):
    with patch("trade_advisor.cli.get_ohlcv", return_value=synthetic_df) as m:
        yield m


@pytest.fixture
def mock_validate_ohlcv():
    with patch("trade_advisor.cli.validate_ohlcv", return_value=[]):
        yield


class TestDataFetch:
    def test_data_fetch_rich(self, mock_get_ohlcv):
        with (
            patch("trade_advisor.cli.load_cached", return_value=None),
            patch("trade_advisor.cli.detect_anomalies") as mock_detect,
        ):
            from trade_advisor.data.validation import ValidationLevel, ValidationResult

            mock_detect.return_value = ValidationResult(anomalies=[], level=ValidationLevel.PASS)
            result = runner.invoke(app, ["data", "fetch", "--symbol", "SPY"])
            assert result.exit_code == 0
            assert "SPY" in result.output

    def test_data_fetch_json(self, mock_get_ohlcv):
        with (
            patch("trade_advisor.cli.load_cached", return_value=None),
            patch("trade_advisor.cli.detect_anomalies") as mock_detect,
        ):
            from trade_advisor.data.validation import ValidationLevel, ValidationResult

            mock_detect.return_value = ValidationResult(anomalies=[], level=ValidationLevel.PASS)
            result = runner.invoke(app, ["data", "fetch", "--symbol", "SPY", "--format", "json"])
            assert result.exit_code == 0
            parsed = json.loads(result.output)
            assert parsed["symbol"] == "SPY"
            assert parsed["bar_count"] == 50

    def test_data_fetch_empty_data(self):
        empty_df = pd.DataFrame()
        with (
            patch("trade_advisor.cli.get_ohlcv", return_value=empty_df),
            patch("trade_advisor.cli.load_cached", return_value=None),
        ):
            result = runner.invoke(app, ["data", "fetch", "--symbol", "BAD"])
            assert result.exit_code == 1

    def test_data_fetch_with_start_end(self, mock_get_ohlcv):
        with (
            patch("trade_advisor.cli.load_cached", return_value=None),
            patch("trade_advisor.cli.detect_anomalies") as mock_detect,
        ):
            from trade_advisor.data.validation import ValidationLevel, ValidationResult

            mock_detect.return_value = ValidationResult(anomalies=[], level=ValidationLevel.PASS)
            result = runner.invoke(
                app,
                [
                    "data",
                    "fetch",
                    "--symbol",
                    "SPY",
                    "--start",
                    "2020-01-01",
                    "--end",
                    "2020-06-01",
                ],
            )
            assert result.exit_code == 0

    def test_data_fetch_invalid_start_end_order(self):
        result = runner.invoke(
            app,
            [
                "data",
                "fetch",
                "--symbol",
                "SPY",
                "--start",
                "2024-01-01",
                "--end",
                "2023-01-01",
            ],
        )
        assert result.exit_code == 1

    def test_data_fetch_network_error(self):
        from trade_advisor.core.errors import DataError

        with (
            patch("trade_advisor.cli.get_ohlcv", side_effect=DataError("network timeout")),
            patch("trade_advisor.cli.load_cached", return_value=None),
        ):
            result = runner.invoke(app, ["data", "fetch", "--symbol", "SPY"])
            assert result.exit_code == 1


class TestDataStatus:
    def test_data_status_no_cache(self):
        with patch("trade_advisor.cli._query_cached_symbols", return_value=[]):
            result = runner.invoke(app, ["data", "status"])
            assert result.exit_code == 0
            assert "No cached data" in result.output

    def test_data_status_with_cache(self):
        symbols = [
            {
                "symbol": "SPY",
                "interval": "1d",
                "bar_count": 100,
                "min_ts": "2020-01-01",
                "max_ts": "2020-06-01",
                "last_updated": "2024-01-01 00:00:00",
                "is_stale": False,
                "warnings": 0,
                "errors": 0,
            }
        ]
        with patch("trade_advisor.cli._query_cached_symbols", return_value=symbols):
            result = runner.invoke(app, ["data", "status"])
            assert result.exit_code == 0
            assert "SPY" in result.output

    def test_data_status_json(self):
        symbols = [
            {
                "symbol": "AAPL",
                "interval": "1d",
                "bar_count": 200,
                "min_ts": "2020-01-01",
                "max_ts": "2020-12-31",
                "last_updated": "2024-01-01 00:00:00",
                "is_stale": False,
                "warnings": 0,
                "errors": 0,
            }
        ]
        with patch("trade_advisor.cli._query_cached_symbols", return_value=symbols):
            result = runner.invoke(app, ["data", "status", "--format", "json"])
            assert result.exit_code == 0
            parsed = json.loads(result.output)
            assert len(parsed) == 1
            assert parsed[0]["symbol"] == "AAPL"

    def test_data_status_filter_symbol(self):
        symbols = [
            {
                "symbol": "SPY",
                "interval": "1d",
                "bar_count": 100,
                "min_ts": "2020-01-01",
                "max_ts": "2020-06-01",
                "last_updated": "2024-01-01 00:00:00",
                "is_stale": False,
                "warnings": 0,
                "errors": 0,
            },
            {
                "symbol": "AAPL",
                "interval": "1d",
                "bar_count": 200,
                "min_ts": "2020-01-01",
                "max_ts": "2020-12-31",
                "last_updated": "2024-01-01 00:00:00",
                "is_stale": False,
                "warnings": 0,
                "errors": 0,
            },
        ]
        with patch("trade_advisor.cli._query_cached_symbols", return_value=symbols):
            result = runner.invoke(app, ["data", "status", "--symbol", "SPY"])
            assert result.exit_code == 0
            assert "SPY" in result.output

    def test_data_status_filter_missing_symbol(self):
        symbols = [
            {
                "symbol": "SPY",
                "interval": "1d",
                "bar_count": 100,
                "min_ts": "2020-01-01",
                "max_ts": "2020-06-01",
                "last_updated": "2024-01-01 00:00:00",
                "is_stale": False,
                "warnings": 0,
                "errors": 0,
            }
        ]
        with patch("trade_advisor.cli._query_cached_symbols", return_value=symbols):
            result = runner.invoke(app, ["data", "status", "--symbol", "NOEXIST"])
            assert result.exit_code == 1


class TestRetryMechanism:
    def test_fetch_with_retry_succeeds_first_try(self, synthetic_df):
        with patch("trade_advisor.cli.get_ohlcv", return_value=synthetic_df):
            from trade_advisor.cli import _fetch_with_retry

            df, attempts = _fetch_with_retry("SPY", None, None, "1d")
            assert len(df) == 50
            assert attempts == 0

    def test_fetch_with_retry_retries_on_error(self, synthetic_df):
        from trade_advisor.core.errors import DataError

        call_count = 0

        def flaky_fetcher(*a, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise DataError("temporary")
            return synthetic_df

        with (
            patch("trade_advisor.cli.get_ohlcv", side_effect=flaky_fetcher),
            patch("trade_advisor.cli.time.sleep"),
        ):
            from trade_advisor.cli import _fetch_with_retry

            df, attempts = _fetch_with_retry("SPY", None, None, "1d", max_retries=2)
            assert len(df) == 50
            assert attempts == 1

    def test_fetch_with_retry_exhausted(self):
        from trade_advisor.cli import _fetch_with_retry, _RetryExhausted
        from trade_advisor.core.errors import DataError

        with (
            patch("trade_advisor.cli.get_ohlcv", side_effect=DataError("persistent error")),
            patch("trade_advisor.cli.time.sleep"),
            pytest.raises(_RetryExhausted),
        ):
            _fetch_with_retry("SPY", None, None, "1d", max_retries=1)

    def test_fetch_with_retry_non_retryable_raises(self):
        with patch("trade_advisor.cli.get_ohlcv", side_effect=ValueError("bad")):
            from trade_advisor.cli import _fetch_with_retry

            with pytest.raises(ValueError, match="bad"):
                _fetch_with_retry("SPY", None, None, "1d", max_retries=2)
