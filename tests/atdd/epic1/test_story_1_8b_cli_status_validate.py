"""ATDD tests: Story 1.8 — CLI `data status` and `data validate` commands.

Tests status display, JSON output, anomaly reporting, and validation commands.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from tests.conftest import _synthetic_ohlcv
from trade_advisor.cli import app

runner = CliRunner()


@pytest.fixture
def cli_runner():
    return runner


def _make_symbol_entry(**overrides):
    base = {
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
    base.update(overrides)
    return base


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
        symbols = [_make_symbol_entry(warnings=2)]
        with patch("trade_advisor.cli._query_cached_symbols", return_value=symbols):
            result = cli_runner.invoke(app, ["data", "status"])
            assert result.exit_code == 0
            assert "SPY" in result.output

    def test_status_highlights_stale(self, cli_runner):
        symbols = [
            _make_symbol_entry(
                last_updated=(datetime.now(UTC) - timedelta(days=7)).isoformat(),
                is_stale=True,
            )
        ]
        with patch("trade_advisor.cli._query_cached_symbols", return_value=symbols):
            result = cli_runner.invoke(app, ["data", "status"])
            assert result.exit_code == 0

    def test_status_anomaly_counts(self, cli_runner):
        symbols = [_make_symbol_entry(warnings=3, errors=1)]
        with patch("trade_advisor.cli._query_cached_symbols", return_value=symbols):
            result = cli_runner.invoke(app, ["data", "status"])
            assert result.exit_code == 0
            assert "3" in result.output
            assert "1" in result.output

    def test_status_format_json(self, cli_runner):
        symbols = [_make_symbol_entry()]
        with patch("trade_advisor.cli._query_cached_symbols", return_value=symbols):
            result = cli_runner.invoke(app, ["data", "status", "--format", "json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert isinstance(data, list)
            assert data[0]["symbol"] == "SPY"

    def test_status_symbol_filter(self, cli_runner):
        symbols = [_make_symbol_entry()]
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
