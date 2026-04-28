"""Tests for CLI config commands — validate, set-key."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from trade_advisor.cli import app

runner = CliRunner()


class TestConfigValidate:
    def test_config_validate_success(self):
        with (
            patch("trade_advisor.cli.load_config") as mock_load,
            patch("trade_advisor.cli.format_config_error"),
        ):
            mock_config = MagicMock()
            mock_config.app.data = MagicMock()
            mock_config.app.backtest = MagicMock()
            mock_config.app.execution = MagicMock()
            mock_config.app.determinism = MagicMock()
            mock_config.app.database = MagicMock()
            mock_config.app.logging = MagicMock()
            mock_config.app.risk = None
            mock_config.secrets = None
            mock_load.return_value = mock_config

            with patch("keyring.get_password", return_value=None):
                result = runner.invoke(app, ["config", "validate"])
                assert result.exit_code == 0
                assert "Validation passed" in result.output

    def test_config_validate_failure(self):

        with (
            patch("trade_advisor.cli.load_config", side_effect=Exception("missing .env")),
            patch("trade_advisor.cli._suggest_from_env_example", return_value=[]),
        ):
            result = runner.invoke(app, ["config", "validate"])
            assert result.exit_code == 1


class TestConfigSetKey:
    def test_config_set_key_empty_rejected(self):
        with patch("trade_advisor.cli.getpass.getpass", return_value="   "):
            result = runner.invoke(app, ["config", "set-key", "YAHOO_API_KEY"])
            assert result.exit_code == 1
            assert "Empty" in result.output

    def test_config_set_key_success(self):
        with (
            patch("trade_advisor.cli.getpass.getpass", return_value="secret123"),
            patch("trade_advisor.cli.set_key") as mock_set,
        ):
            result = runner.invoke(app, ["config", "set-key", "YAHOO_API_KEY"])
            assert result.exit_code == 0
            assert "Stored" in result.output
            mock_set.assert_called_once_with("YAHOO_API_KEY", "secret123")
