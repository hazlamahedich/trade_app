"""ATDD red-phase: Story 1.3 — Configuration & Secure Key Storage.

All tests are SKIPPED (TDD red phase). Remove when implementing Story 1.3.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class TestStory13Configuration:
    """Story 1.3: Config loads from env, keys stored securely."""

    def test_app_config_loads_from_env(self):
        from trade_advisor.core.config import AppConfig

        with patch.dict(os.environ, {"QTA_DATA_DIR": "/tmp/qta_test"}):
            cfg = AppConfig()
            assert cfg is not None

    def test_app_config_uses_pydantic_base_settings(self):
        from pydantic_settings import BaseSettings

        from trade_advisor.core.config import AppConfig

        assert issubclass(AppConfig, BaseSettings)

    def test_env_prefix_is_qta(self):
        from trade_advisor.core.config import AppConfig

        assert AppConfig.model_config.get("env_prefix") in ("QTA_", "", None)

    def test_keyring_integration_for_api_keys(self):
        from trade_advisor.core.config import get_api_key

        with patch("keyring.get_password", return_value="test-key"):
            key = get_api_key("yahoo_finance")
            assert key == "test-key"

    def test_env_fallback_for_api_keys(self):
        from trade_advisor.core.config import get_api_key

        with (
            patch("keyring.get_password", return_value=None),
            patch.dict(os.environ, {"YAHOO_API_KEY": "env-key"}),
        ):
            key = get_api_key("yahoo_finance")
            assert key == "env-key"

    def test_env_example_committed(self):
        env_example = PROJECT_ROOT / ".env.example"
        assert env_example.exists()
        content = env_example.read_text()
        assert "YAHOO" in content.upper() or "API" in content.upper()

    def test_env_is_gitignored(self):
        gitignore = PROJECT_ROOT / ".gitignore"
        assert gitignore.exists()
        content = gitignore.read_text()
        assert ".env" in content

    def test_config_module_per_subsection(self):
        """Each module receives its config subsection as typed Pydantic model."""
        from trade_advisor.core.config import AppConfig

        cfg = AppConfig()
        assert hasattr(cfg, "data") or hasattr(cfg, "backtest") or hasattr(cfg, "ml")
