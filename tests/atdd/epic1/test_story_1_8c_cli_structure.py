"""ATDD tests: Story 1.8 — CLI structure and backward compatibility.

Tests CLI help visibility, subcommand listing, exit codes, and legacy commands.
"""

from __future__ import annotations

from unittest.mock import patch

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
        gen_start = start if start else "2020-01-01"
        df = _synthetic_ohlcv(n=500, symbol=symbol, start=str(gen_start)[:10])
        import pandas as pd

        if start is not None:
            df = df[df["timestamp"] >= pd.to_datetime(start, utc=True)]
        return df.reset_index(drop=True)

    return _f


@pytest.fixture
def cli_runner():
    return runner


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
