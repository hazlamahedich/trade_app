"""ATDD red-phase: Story 1.3 — Configuration & Secure Key Storage.

All tests are SKIPPED (TDD red phase). Remove when implementing Story 1.3.
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[4]


class TestStory13Configuration:
    """Story 1.3: Config loads from env, keys stored securely."""

    @pytest.mark.skip(reason="ATDD red phase — Story 1.3 not implemented")
    def test_app_config_loads_from_env(self):
        from trade_advisor.core.config import AppConfig

        with patch.dict(os.environ, {"QTA_DATA_DIR": "/tmp/qta_test"}):
            cfg = AppConfig()
            assert cfg is not None

    @pytest.mark.skip(reason="ATDD red phase — Story 1.3 not implemented")
    def test_app_config_uses_pydantic_base_settings(self):
        from pydantic_settings import BaseSettings

        from trade_advisor.core.config import AppConfig

        assert issubclass(AppConfig, BaseSettings)

    @pytest.mark.skip(reason="ATDD red phase — Story 1.3 not implemented")
    def test_env_prefix_is_qta(self):
        from trade_advisor.core.config import AppConfig

        assert AppConfig.model_config.get("env_prefix") == "QTA_"

    @pytest.mark.skip(reason="ATDD red phase — Story 1.3 not implemented")
    def test_missing_required_config_raises_clear_error(self):
        from trade_advisor.core.config import AppConfig

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(Exception) as exc_info:
                AppConfig()
            error_msg = str(exc_info.value)
            assert any(var in error_msg for var in ("QTA_", "required", "missing")), (
                f"Error message not clear enough: {error_msg}"
            )

    @pytest.mark.skip(reason="ATDD red phase — Story 1.3 not implemented")
    def test_keyring_integration_for_api_keys(self):
        from trade_advisor.core.config import get_api_key

        with patch("keyring.get_password", return_value="test-key"):
            key = get_api_key("yahoo_finance")
            assert key == "test-key"

    @pytest.mark.skip(reason="ATDD red phase — Story 1.3 not implemented")
    def test_env_fallback_for_api_keys(self):
        from trade_advisor.core.config import get_api_key

        with patch("keyring.get_password", return_value=None):
            with patch.dict(os.environ, {"QTA_YAHOO_API_KEY": "env-key"}):
                key = get_api_key("yahoo_finance")
                assert key == "env-key"

    @pytest.mark.skip(reason="ATDD red phase — Story 1.3 not implemented")
    def test_env_example_committed(self):
        env_example = PROJECT_ROOT / ".env.example"
        assert env_example.exists()
        content = env_example.read_text()
        assert "YAHOO" in content.upper() or "API" in content.upper()

    @pytest.mark.skip(reason="ATDD red phase — Story 1.3 not implemented")
    def test_env_is_gitignored(self):
        gitignore = PROJECT_ROOT / ".gitignore"
        assert gitignore.exists()
        content = gitignore.read_text()
        assert ".env" in content

    @pytest.mark.skip(reason="ATDD red phase — Story 1.3 not implemented")
    def test_config_module_per_subsection(self):
        """Each module receives its config subsection as typed Pydantic model."""
        from trade_advisor.core.config import AppConfig

        cfg = AppConfig()
        assert hasattr(cfg, "data") or hasattr(cfg, "backtest") or hasattr(cfg, "ml")
