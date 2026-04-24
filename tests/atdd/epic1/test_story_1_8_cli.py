"""ATDD red-phase: Story 1.8 — CLI for Data Operations.

All tests are SKIPPED (TDD red phase). Remove when implementing Story 1.8.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

runner = CliRunner()


class TestStory18CLI:
    """Story 1.8: CLI data fetch, status, validate commands."""

    @pytest.mark.skip(reason="ATDD red phase — Story 1.8 not implemented")
    def test_cli_app_exists(self):
        from trade_advisor.cli.commands import app

        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0

    @pytest.mark.skip(reason="ATDD red phase — Story 1.8 not implemented")
    def test_data_fetch_command(self):
        from trade_advisor.cli.commands import app

        mock_df = __import__("pandas").DataFrame(
            {
                "timestamp": __import__("pandas").date_range("2024-01-01", periods=5, tz="UTC"),
                "open": [100.0] * 5,
                "high": [101.0] * 5,
                "low": [99.0] * 5,
                "close": [100.5] * 5,
                "volume": [1e6] * 5,
                "adj_close": [100.5] * 5,
                "symbol": "SPY",
                "interval": "1d",
            }
        )
        with patch("trade_advisor.cli.commands.fetch_data", return_value=mock_df):
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
                    "2024-12-31",
                ],
            )
            assert result.exit_code == 0

    @pytest.mark.skip(reason="ATDD red phase — Story 1.8 not implemented")
    def test_data_status_command(self):
        from trade_advisor.cli.commands import app

        result = runner.invoke(app, ["data", "status"])
        assert result.exit_code == 0

    @pytest.mark.skip(reason="ATDD red phase — Story 1.8 not implemented")
    def test_data_validate_command(self):
        from trade_advisor.cli.commands import app

        result = runner.invoke(app, ["data", "validate", "--symbol", "SPY"])
        assert result.exit_code == 0

    @pytest.mark.skip(reason="ATDD red phase — Story 1.8 not implemented")
    def test_cli_uses_typer_with_rich(self):
        from trade_advisor.cli.commands import app

        assert app.info.pretty_exceptions_enable is True or hasattr(app, "rich_markup_mode")

    @pytest.mark.skip(reason="ATDD red phase — Story 1.8 not implemented")
    def test_cli_error_exit_code(self):
        from trade_advisor.cli.commands import app

        result = runner.invoke(app, ["data", "fetch", "--symbol", "INVALID_SYMBOL_12345"])
        assert result.exit_code == 1

    @pytest.mark.skip(reason="ATDD red phase — Story 1.8 not implemented")
    def test_cli_success_exit_code_zero(self):
        from trade_advisor.cli.commands import app

        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
