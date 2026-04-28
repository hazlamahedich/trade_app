"""ATDD tests: Story 1.8 — CLI for Data Operations.

Tests the `ta data fetch`, `ta data status`, and `ta data validate` commands
via typer.testing.CliRunner with mocked data sources.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pandas as pd
import pytest
from typer.testing import CliRunner

from tests.conftest import _synthetic_ohlcv
from trade_advisor.cli import app

runner = CliRunner()


@pytest.fixture
def mock_fetcher():
    def _f(*args, **kwargs):
        symbol = kwargs.get("symbol") or (args[0] if args else "SPY")
        start = kwargs.get("start")
        end = kwargs.get("end")
        gen_start = start if start else "2020-01-01"
        df = _synthetic_ohlcv(n=500, symbol=symbol, start=str(gen_start)[:10])
        if start is not None:
            df = df[df["timestamp"] >= pd.to_datetime(start, utc=True)]
        if end is not None:
            df = df[df["timestamp"] < pd.to_datetime(end, utc=True)]
        return df.reset_index(drop=True)

    return _f


@pytest.fixture
def mock_fetcher_empty():
    def _f(symbol, start=None, end=None, interval="1d"):
        raise RuntimeError(f"yfinance returned no data for {symbol}")

    return _f


@pytest.fixture
def cached_spy(tmp_path):
    df = _synthetic_ohlcv(n=200, symbol="SPY")
    p = tmp_path / "ohlcv" / "SPY" / "1d" / "part.parquet"
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p, index=False)
    return tmp_path


@pytest.fixture
def cli_runner():
    return runner


class TestDataFetchCommand:
    def test_fetch_validates_caches_data(self, cli_runner, mock_fetcher, tmp_path):
        with (
            patch("trade_advisor.cli.get_ohlcv", side_effect=mock_fetcher),
            patch("trade_advisor.cli.load_cached", return_value=None),
            patch("trade_advisor.cli.detect_anomalies") as mock_validate,
        ):
            from trade_advisor.data.validation import (
                ValidationLevel,
                ValidationResult,
            )

            mock_validate.return_value = ValidationResult(level=ValidationLevel.PASS, anomalies=[])
            result = cli_runner.invoke(
                app,
                [
                    "data",
                    "fetch",
                    "--symbol",
                    "SPY",
                    "--start",
                    "2020-01-01",
                    "--end",
                    "2024-12-31",
                ],
            )
            assert result.exit_code == 0
            mock_validate.assert_called_once()

    def test_fetch_refresh_ignores_cache(self, cli_runner, mock_fetcher):
        with (
            patch("trade_advisor.cli.get_ohlcv", side_effect=mock_fetcher) as mock_get,
            patch("trade_advisor.cli.detect_anomalies") as mock_validate,
        ):
            from trade_advisor.data.validation import ValidationLevel, ValidationResult

            mock_validate.return_value = ValidationResult(level=ValidationLevel.PASS, anomalies=[])
            result = cli_runner.invoke(app, ["data", "fetch", "--symbol", "SPY", "--refresh"])
            assert result.exit_code == 0
            mock_get.assert_called_once()
            assert mock_get.call_args[1]["refresh"] is True

    def test_fetch_interval_flag(self, cli_runner, mock_fetcher):
        with (
            patch("trade_advisor.cli.get_ohlcv", side_effect=mock_fetcher) as mock_get,
            patch("trade_advisor.cli.load_cached", return_value=None),
            patch("trade_advisor.cli.detect_anomalies") as mock_validate,
        ):
            from trade_advisor.data.validation import ValidationLevel, ValidationResult

            mock_validate.return_value = ValidationResult(level=ValidationLevel.PASS, anomalies=[])
            result = cli_runner.invoke(
                app,
                ["data", "fetch", "--symbol", "SPY", "--interval", "1h", "--start", "2024-01-01"],
            )
            assert result.exit_code == 0
            assert mock_get.call_args[1]["interval"] == "1h"

    def test_fetch_format_json(self, cli_runner, mock_fetcher):
        with (
            patch("trade_advisor.cli.get_ohlcv", side_effect=mock_fetcher),
            patch("trade_advisor.cli.load_cached", return_value=None),
            patch("trade_advisor.cli.detect_anomalies") as mock_validate,
        ):
            from trade_advisor.data.validation import ValidationLevel, ValidationResult

            mock_validate.return_value = ValidationResult(level=ValidationLevel.PASS, anomalies=[])
            result = cli_runner.invoke(
                app,
                [
                    "data",
                    "fetch",
                    "--symbol",
                    "SPY",
                    "--start",
                    "2020-01-01",
                    "--format",
                    "json",
                ],
            )
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert "symbol" in data
            assert data["symbol"] == "SPY"
            assert "warnings" in data

    def test_fetch_json_includes_future_date_warning(self, cli_runner, mock_fetcher):
        with (
            patch("trade_advisor.cli.get_ohlcv", side_effect=mock_fetcher),
            patch("trade_advisor.cli.load_cached", return_value=None),
            patch("trade_advisor.cli.detect_anomalies") as mock_validate,
        ):
            from trade_advisor.data.validation import ValidationLevel, ValidationResult

            mock_validate.return_value = ValidationResult(level=ValidationLevel.PASS, anomalies=[])
            result = cli_runner.invoke(
                app,
                ["data", "fetch", "--symbol", "SPY", "--start", "2030-01-01", "--format", "json"],
            )
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert any("future" in w.lower() for w in data["warnings"])

    def test_fetch_invalid_symbol_exits_1(self, cli_runner, mock_fetcher_empty):
        with (
            patch("trade_advisor.cli.get_ohlcv", side_effect=mock_fetcher_empty),
            patch("trade_advisor.cli.load_cached", return_value=None),
            patch("time.sleep"),
        ):
            result = cli_runner.invoke(app, ["data", "fetch", "--symbol", "INVALIDXYZ123"])
            assert result.exit_code == 1

    def test_fetch_swapped_dates_exits_1(self, cli_runner):
        result = cli_runner.invoke(
            app,
            [
                "data",
                "fetch",
                "--symbol",
                "SPY",
                "--start",
                "2024-12-31",
                "--end",
                "2020-01-01",
            ],
        )
        assert result.exit_code == 1
        combined = result.output.lower()
        assert "start" in combined

    def test_fetch_invalid_date_format_exits_1(self, cli_runner):
        result = cli_runner.invoke(
            app,
            [
                "data",
                "fetch",
                "--symbol",
                "SPY",
                "--start",
                "not-a-date",
                "--end",
                "2024-01-01",
            ],
        )
        assert result.exit_code == 1

    def test_fetch_future_start_warns(self, cli_runner, mock_fetcher):
        with (
            patch("trade_advisor.cli.get_ohlcv", side_effect=mock_fetcher),
            patch("trade_advisor.cli.load_cached", return_value=None),
            patch("trade_advisor.cli.detect_anomalies") as mock_validate,
        ):
            from trade_advisor.data.validation import ValidationLevel, ValidationResult

            mock_validate.return_value = ValidationResult(level=ValidationLevel.PASS, anomalies=[])
            result = cli_runner.invoke(
                app, ["data", "fetch", "--symbol", "SPY", "--start", "2030-01-01"]
            )
            assert result.exit_code == 0

    def test_fetch_incremental_update(self, cli_runner, mock_fetcher):
        cached_df = _synthetic_ohlcv(n=100, symbol="SPY")
        with (
            patch("trade_advisor.cli.get_ohlcv", side_effect=mock_fetcher),
            patch("trade_advisor.cli.load_cached", return_value=cached_df),
            patch("trade_advisor.cli.detect_anomalies") as mock_validate,
        ):
            from trade_advisor.data.validation import ValidationLevel, ValidationResult

            mock_validate.return_value = ValidationResult(level=ValidationLevel.PASS, anomalies=[])
            result = cli_runner.invoke(
                app,
                [
                    "data",
                    "fetch",
                    "--symbol",
                    "SPY",
                    "--start",
                    "2020-01-01",
                    "--end",
                    "2024-12-31",
                    "--format",
                    "json",
                ],
            )
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert any("new bars appended" in w for w in data["warnings"])

    def test_fetch_retry_on_failure(self, cli_runner):
        call_count = 0

        def failing_fetcher(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise RuntimeError("Network error")

        with (
            patch("trade_advisor.cli.get_ohlcv", side_effect=failing_fetcher),
            patch("trade_advisor.cli.load_cached", return_value=None),
            patch("time.sleep"),
        ):
            result = cli_runner.invoke(
                app, ["data", "fetch", "--symbol", "SPY", "--start", "2020-01-01"]
            )
            assert result.exit_code == 1
            assert call_count == 3

    def test_fetch_retry_error_includes_attempt_count(self, cli_runner):
        def failing_fetcher(*args, **kwargs):
            raise RuntimeError("Network error")

        with (
            patch("trade_advisor.cli.get_ohlcv", side_effect=failing_fetcher),
            patch("trade_advisor.cli.load_cached", return_value=None),
            patch("time.sleep"),
        ):
            result = cli_runner.invoke(
                app,
                [
                    "data",
                    "fetch",
                    "--symbol",
                    "SPY",
                    "--start",
                    "2020-01-01",
                    "--format",
                    "json",
                ],
            )
            assert result.exit_code == 1


class TestDataStatusCommand:
    def test_status_empty_state(self, cli_runner):
        with patch(
            "trade_advisor.cli._query_cached_symbols",
            return_value=[],
        ):
            result = cli_runner.invoke(app, ["data", "status"])
            assert result.exit_code == 0
            assert "no cached data" in result.output.lower() or "No cached" in result.output

    def test_status_shows_rich_table(self, cli_runner):
        symbols = [
            {
                "symbol": "SPY",
                "interval": "1d",
                "bar_count": 500,
                "min_ts": "2020-01-02",
                "max_ts": "2021-12-31",
                "warnings": 2,
                "errors": 0,
                "last_updated": datetime.now(UTC).isoformat(),
                "is_stale": False,
            }
        ]
        with patch("trade_advisor.cli._query_cached_symbols", return_value=symbols):
            result = cli_runner.invoke(app, ["data", "status"])
            assert result.exit_code == 0
            assert "SPY" in result.output

    def test_status_highlights_stale(self, cli_runner):
        symbols = [
            {
                "symbol": "SPY",
                "interval": "1d",
                "bar_count": 500,
                "min_ts": "2020-01-02",
                "max_ts": "2021-12-31",
                "warnings": 0,
                "errors": 0,
                "last_updated": (datetime.now(UTC) - timedelta(days=7)).isoformat(),
                "is_stale": True,
            }
        ]
        with patch("trade_advisor.cli._query_cached_symbols", return_value=symbols):
            result = cli_runner.invoke(app, ["data", "status"])
            assert result.exit_code == 0

    def test_status_anomaly_counts(self, cli_runner):
        symbols = [
            {
                "symbol": "SPY",
                "interval": "1d",
                "bar_count": 500,
                "min_ts": "2020-01-02",
                "max_ts": "2021-12-31",
                "warnings": 3,
                "errors": 1,
                "last_updated": datetime.now(UTC).isoformat(),
                "is_stale": False,
            }
        ]
        with patch("trade_advisor.cli._query_cached_symbols", return_value=symbols):
            result = cli_runner.invoke(app, ["data", "status"])
            assert result.exit_code == 0
            assert "3" in result.output
            assert "1" in result.output

    def test_status_format_json(self, cli_runner):
        symbols = [
            {
                "symbol": "SPY",
                "interval": "1d",
                "bar_count": 500,
                "min_ts": "2020-01-02",
                "max_ts": "2021-12-31",
                "warnings": 0,
                "errors": 0,
                "last_updated": datetime.now(UTC).isoformat(),
                "is_stale": False,
            }
        ]
        with patch("trade_advisor.cli._query_cached_symbols", return_value=symbols):
            result = cli_runner.invoke(app, ["data", "status", "--format", "json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert isinstance(data, list)
            assert data[0]["symbol"] == "SPY"

    def test_status_symbol_filter(self, cli_runner):
        symbols = [
            {
                "symbol": "SPY",
                "interval": "1d",
                "bar_count": 500,
                "min_ts": "2020-01-02",
                "max_ts": "2021-12-31",
                "warnings": 0,
                "errors": 0,
                "last_updated": datetime.now(UTC).isoformat(),
                "is_stale": False,
            }
        ]
        with patch("trade_advisor.cli._query_cached_symbols", return_value=symbols):
            result = cli_runner.invoke(app, ["data", "status", "--symbol", "SPY"])
            assert result.exit_code == 0
            assert "SPY" in result.output

    def test_status_symbol_not_found(self, cli_runner):
        with patch("trade_advisor.cli._query_cached_symbols", return_value=[]):
            result = cli_runner.invoke(app, ["data", "status", "--symbol", "UNKNOWN"])
            assert result.exit_code == 1


class TestDataValidateCommand:
    def test_validate_runs_detect_anomalies(self, cli_runner):
        df = _synthetic_ohlcv(n=100, symbol="SPY")
        with (
            patch("trade_advisor.cli.load_cached", return_value=df),
            patch("trade_advisor.cli.detect_anomalies") as mock_validate,
        ):
            from trade_advisor.data.validation import ValidationLevel, ValidationResult

            mock_validate.return_value = ValidationResult(level=ValidationLevel.PASS, anomalies=[])
            result = cli_runner.invoke(app, ["data", "validate", "--symbol", "SPY"])
            assert result.exit_code == 0
            mock_validate.assert_called_once()

    def test_validate_error_anomalies_exits_1(self, cli_runner):
        from trade_advisor.data.validation import (
            Anomaly,
            AnomalyAction,
            AnomalySeverity,
            ValidationLevel,
            ValidationResult,
        )

        df = _synthetic_ohlcv(n=100, symbol="SPY")
        with (
            patch("trade_advisor.cli.load_cached", return_value=df),
            patch("trade_advisor.cli.detect_anomalies") as mock_validate,
        ):
            mock_validate.return_value = ValidationResult(
                level=ValidationLevel.FAIL,
                anomalies=[
                    Anomaly(
                        severity=AnomalySeverity.ERROR,
                        action=AnomalyAction.EXCLUDE,
                        message="Test error",
                        symbol="SPY",
                        row_index=0,
                    )
                ],
            )
            result = cli_runner.invoke(app, ["data", "validate", "--symbol", "SPY"])
            assert result.exit_code == 1

    def test_validate_category_breakdown(self, cli_runner):
        from trade_advisor.data.validation import (
            Anomaly,
            AnomalyAction,
            AnomalySeverity,
            ValidationLevel,
            ValidationResult,
        )

        df = _synthetic_ohlcv(n=100, symbol="SPY")
        with (
            patch("trade_advisor.cli.load_cached", return_value=df),
            patch("trade_advisor.cli.detect_anomalies") as mock_validate,
        ):
            mock_validate.return_value = ValidationResult(
                level=ValidationLevel.WARN,
                anomalies=[
                    Anomaly(
                        severity=AnomalySeverity.WARNING,
                        action=AnomalyAction.FLAG,
                        message="NaN run of length 3 in 'close'",
                        symbol="SPY",
                        row_index=5,
                        column="close",
                    ),
                    Anomaly(
                        severity=AnomalySeverity.WARNING,
                        action=AnomalyAction.FLAG,
                        message="Price gap at index 20: 5.00% change",
                        symbol="SPY",
                        row_index=20,
                        column="close",
                    ),
                ],
            )
            result = cli_runner.invoke(app, ["data", "validate", "--symbol", "SPY"])
            assert result.exit_code == 0

    def test_validate_unknown_symbol_exits_1(self, cli_runner):
        with patch("trade_advisor.cli.load_cached", return_value=None):
            result = cli_runner.invoke(app, ["data", "validate", "--symbol", "UNKNOWN"])
            assert result.exit_code == 1

    def test_validate_format_json(self, cli_runner):
        from trade_advisor.data.validation import ValidationLevel, ValidationResult

        df = _synthetic_ohlcv(n=100, symbol="SPY")
        with (
            patch("trade_advisor.cli.load_cached", return_value=df),
            patch("trade_advisor.cli.detect_anomalies") as mock_validate,
        ):
            mock_validate.return_value = ValidationResult(level=ValidationLevel.PASS, anomalies=[])
            result = cli_runner.invoke(
                app, ["data", "validate", "--symbol", "SPY", "--format", "json"]
            )
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert "level" in data


class TestCLIStructure:
    def test_data_subcommand_visible(self, cli_runner):
        result = cli_runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "data" in result.output

    def test_data_help_lists_subcommands(self, cli_runner):
        result = cli_runner.invoke(app, ["data", "--help"])
        assert result.exit_code == 0
        assert "fetch" in result.output
        assert "status" in result.output
        assert "validate" in result.output

    def test_unexpected_exception_exits_1(self, cli_runner):
        with (
            patch("trade_advisor.cli.get_ohlcv", side_effect=ValueError("boom")),
            patch("trade_advisor.cli.load_cached", return_value=None),
        ):
            result = cli_runner.invoke(
                app, ["data", "fetch", "--symbol", "SPY", "--start", "2020-01-01"]
            )
            assert result.exit_code == 1

    def test_success_exits_0(self, cli_runner, mock_fetcher):
        with (
            patch("trade_advisor.cli.get_ohlcv", side_effect=mock_fetcher),
            patch("trade_advisor.cli.load_cached", return_value=None),
            patch("trade_advisor.cli.detect_anomalies") as mock_validate,
        ):
            from trade_advisor.data.validation import ValidationLevel, ValidationResult

            mock_validate.return_value = ValidationResult(level=ValidationLevel.PASS, anomalies=[])
            result = cli_runner.invoke(
                app, ["data", "fetch", "--symbol", "SPY", "--start", "2020-01-01"]
            )
            assert result.exit_code == 0

    def test_existing_fetch_still_works(self, cli_runner, mock_fetcher):
        with patch("trade_advisor.cli.get_ohlcv", wraps=mock_fetcher) as mock_get:
            result = cli_runner.invoke(app, ["fetch", "SPY", "--start", "2020-01-01"])
            assert result.exit_code == 0
            mock_get.assert_called_once()
