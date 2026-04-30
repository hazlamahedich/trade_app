"""Tests for Story 1.3: Configuration & Secure Key Storage.

Covers:
- Config loading from .env (AC #1)
- Missing required fields (AC #2)
- Frozen model (AC #1)
- Extra fields rejected (AC #1)
- Keyring integration (AC #6-9)
- Secret masking (AC #11)
- .env.example parity (AC #12)
- Gitignore checks (AC #13)
- CLI commands (AC #15-16)
- No import-time I/O (AC #14)
- Domain validation (AC #3)
- Review patches (P1-P10, D2-D4)
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from trade_advisor.core.config import (
    AppConfig,
    BacktestConfig,
    CostModel,
    DatabaseConfig,
    DataConfig,
    DeterminismConfig,
    ExecutionConfig,
    FullConfig,
    LoggingConfig,
    RiskConfig,
    format_config_error,
    load_config,
)
from trade_advisor.core.secrets import (
    KEYRING_SERVICE,
    SecretsConfig,
    load_secrets,
    set_key,
)


class TestConfigLoadingFromEnvFile:
    """AC #1: AppConfig loads from .env via pydantic-settings."""

    @pytest.mark.test_id("1.3-UNIT-001")
    @pytest.mark.p1
    def test_loads_from_env_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        env_file = tmp_path / ".env"
        env_file.write_text(
            "DATA__CACHE_DIR=/tmp/test_cache\nDETERMINISM__RANDOM_SEED=99\nLOGGING__LEVEL=DEBUG\n"
        )
        monkeypatch.delenv("DATA__CACHE_DIR", raising=False)
        monkeypatch.delenv("DETERMINISM__RANDOM_SEED", raising=False)
        monkeypatch.delenv("LOGGING__LEVEL", raising=False)
        cfg = AppConfig(_env_file=str(env_file))
        assert cfg.data.cache_dir == Path("/tmp/test_cache")
        assert cfg.determinism.random_seed == 99
        assert cfg.logging.level == "DEBUG"

    @pytest.mark.test_id("1.3-UNIT-002")
    @pytest.mark.p1
    def test_default_values_when_no_env(self):
        cfg = AppConfig(_env_file=None)
        assert cfg.determinism.random_seed == 42
        assert cfg.backtest.initial_cash == Decimal("100000")
        assert cfg.logging.level == "INFO"

    @pytest.mark.test_id("1.3-UNIT-003")
    @pytest.mark.p1
    def test_env_var_takes_precedence_over_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        env_file = tmp_path / ".env"
        env_file.write_text("DETERMINISM__RANDOM_SEED=10\n")
        monkeypatch.setenv("DETERMINISM__RANDOM_SEED", "20")
        cfg = AppConfig(_env_file=str(env_file))
        assert cfg.determinism.random_seed == 20


class TestMissingRequiredFields:
    """AC #2: Missing required fields raise with exact variable name."""

    @pytest.mark.test_id("1.3-UNIT-004")
    @pytest.mark.p1
    def test_missing_required_field_raises_with_name(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("RISK__MAX_POSITION_SIZE", raising=False)
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(
                _env_file=None,
                risk={"max_position_size": None},
            )
        formatted = format_config_error(exc_info.value)
        assert "Required config missing:" in formatted
        assert "max_position_size" in formatted
        assert ".env" in formatted
        assert "env var" in formatted

    @pytest.mark.test_id("1.3-UNIT-005")
    @pytest.mark.p2
    def test_format_config_error_missing_field(self):
        try:
            RiskConfig(max_position_size=None)
        except ValidationError as exc:
            msg = format_config_error(exc)
        else:
            pytest.fail("Expected ValidationError")
        assert msg.startswith("Required config missing:")
        assert "max_position_size" in msg
        assert "Set it in .env or as env var." in msg


class TestFrozenModel:
    """AC #1: AppConfig is frozen."""

    @pytest.mark.test_id("1.3-UNIT-006")
    @pytest.mark.p1
    def test_frozen_model_raises_on_mutation(self):
        cfg = AppConfig(_env_file=None)
        with pytest.raises(ValidationError):
            cfg.data = DataConfig()


class TestExtraFieldsRejected:
    """AC #1: Extra fields are rejected."""

    @pytest.mark.test_id("1.3-UNIT-007")
    @pytest.mark.p2
    def test_extra_fields_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(_env_file=None, unknown_field="value")
        assert "extra" in str(exc_info.value).lower() or "forbid" in str(exc_info.value).lower()


class TestDomainValidation:
    """AC #3: Domain-aware validation rejects invalid values."""

    @pytest.mark.test_id("1.3-UNIT-008")
    @pytest.mark.p1
    def test_invalid_seed_rejected(self):
        with pytest.raises(ValidationError):
            DeterminismConfig(random_seed=-1)

    @pytest.mark.test_id("1.3-UNIT-009")
    @pytest.mark.p1
    def test_invalid_logging_level_rejected(self):
        with pytest.raises(ValidationError):
            LoggingConfig(level="INVALID")

    @pytest.mark.test_id("1.3-UNIT-010")
    @pytest.mark.p1
    def test_valid_risk_config(self):
        r = RiskConfig(max_position_size=Decimal("50000"))
        assert r.max_portfolio_drawdown_pct == Decimal("20.0")

    @pytest.mark.test_id("1.3-UNIT-011")
    @pytest.mark.p2
    def test_invalid_drawdown_pct_rejected(self):
        with pytest.raises(ValidationError):
            RiskConfig(max_position_size=Decimal("1000"), max_portfolio_drawdown_pct=Decimal("150"))

    @pytest.mark.test_id("1.3-UNIT-012")
    @pytest.mark.p1
    def test_execution_config_defaults(self):
        e = ExecutionConfig()
        assert e.slippage_model == "percentage"
        assert e.slippage_bps == Decimal("5.0")


class TestInitialCashDecimal:
    """D4: initial_cash is Decimal (not float)."""

    @pytest.mark.test_id("1.3-UNIT-013")
    @pytest.mark.p1
    def test_initial_cash_is_decimal(self):
        b = BacktestConfig()
        assert isinstance(b.initial_cash, Decimal)
        assert b.initial_cash == Decimal("100000")

    @pytest.mark.test_id("1.3-UNIT-014")
    @pytest.mark.p1
    def test_initial_cash_accepts_decimal_input(self):
        b = BacktestConfig(initial_cash=Decimal("50000"))
        assert b.initial_cash == Decimal("50000")

    @pytest.mark.test_id("1.3-UNIT-015")
    @pytest.mark.p2
    def test_initial_cash_coerces_float(self):
        b = BacktestConfig(initial_cash=50000.0)
        assert isinstance(b.initial_cash, Decimal)


class TestKeyringIntegration:
    """AC #6-9: Keyring integration with fallback."""

    @patch("trade_advisor.core.secrets._init_keyring")
    @pytest.mark.test_id("1.3-UNIT-016")
    @pytest.mark.p1
    def test_keyring_read_fallback_to_env(self, mock_init):
        mock_kr = MagicMock()
        mock_kr.get_password.return_value = None
        mock_init.return_value = mock_kr

        secrets = load_secrets(env_vars={"YAHOO_API_KEY": "env_yahoo_key"})
        assert secrets.get_secret_value("yahoo_api_key") == "env_yahoo_key"
        assert secrets._secrets_source["yahoo_api_key"] == "env_fallback"

    @patch("trade_advisor.core.secrets._init_keyring")
    @pytest.mark.test_id("1.3-UNIT-017")
    @pytest.mark.p1
    def test_keyring_hit_skips_env(self, mock_init):
        mock_kr = MagicMock()
        mock_kr.get_password.return_value = "keyring_val"
        mock_init.return_value = mock_kr

        secrets = load_secrets(env_vars={"YAHOO_API_KEY": "env_val"})
        assert secrets.get_secret_value("yahoo_api_key") == "keyring_val"
        assert secrets._secrets_source["yahoo_api_key"] == "keyring"

    @patch("trade_advisor.core.secrets._init_keyring")
    @pytest.mark.test_id("1.3-UNIT-018")
    @pytest.mark.p1
    def test_keyring_unavailable_graceful_degradation(self, mock_init):
        mock_kr = MagicMock()
        mock_kr.get_password.side_effect = RuntimeError("Keychain locked")
        mock_init.return_value = mock_kr

        secrets = load_secrets(env_vars={"YAHOO_API_KEY": "fallback_key"})
        assert secrets.get_secret_value("yahoo_api_key") == "fallback_key"

    @patch("trade_advisor.core.secrets._init_keyring")
    @pytest.mark.test_id("1.3-UNIT-019")
    @pytest.mark.p1
    def test_all_keys_none_when_no_source(self, mock_init):
        mock_kr = MagicMock()
        mock_kr.get_password.return_value = None
        mock_init.return_value = mock_kr

        secrets = load_secrets(env_vars={})
        assert secrets.yahoo_api_key is None
        assert secrets.alpha_vantage_api_key is None
        assert secrets.polygon_api_key is None

    @patch("trade_advisor.core.secrets._init_keyring")
    @pytest.mark.test_id("1.3-UNIT-020")
    @pytest.mark.p1
    def test_set_key_stores_in_keyring(self, mock_init):
        mock_kr = MagicMock()
        mock_init.return_value = mock_kr

        set_key("YAHOO_API_KEY", "my_secret")
        mock_kr.set_password.assert_called_once_with(KEYRING_SERVICE, "YAHOO_API_KEY", "my_secret")

    @pytest.mark.test_id("1.3-UNIT-021")
    @pytest.mark.p1
    def test_set_key_rejects_unknown_key(self):
        with pytest.raises(ValueError, match="Unknown key"):
            set_key("INVALID_KEY", "val")


class TestSecretMasking:
    """AC #11: SecretStr masks values in repr/dump."""

    @pytest.mark.test_id("1.3-UNIT-022")
    @pytest.mark.p2
    def test_secrets_masked_in_repr(self):
        s = SecretsConfig(yahoo_api_key="super_secret_value")
        r = repr(s)
        assert "super_secret_value" not in r

    @pytest.mark.test_id("1.3-UNIT-023")
    @pytest.mark.p2
    def test_secrets_masked_in_model_dump(self):
        s = SecretsConfig(
            yahoo_api_key="super_secret",
            _secrets_source={"yahoo_api_key": "keyring"},
        )
        d = s.model_dump()
        assert d["yahoo_api_key"] != "super_secret"
        assert d["_secrets_source"] == {"yahoo_api_key": "keyring"}


class TestEnvExampleParity:
    """AC #12: .env.example field parity with AppConfig."""

    @pytest.mark.test_id("1.3-UNIT-024")
    @pytest.mark.p2
    def test_env_example_field_parity(self):
        repo_root = Path(__file__).resolve().parents[1]
        env_example = repo_root / ".env.example"
        assert env_example.exists(), ".env.example must exist in repo root"

        content = env_example.read_text()
        expected_keys = [
            "DATA__CACHE_DIR",
            "DETERMINISM__RANDOM_SEED",
            "LOGGING__LEVEL",
            "BACKTEST__INITIAL_CASH",
            "RISK__MAX_POSITION_SIZE",
            "EXECUTION__SLIPPAGE_MODEL",
            "DATABASE__PATH",
        ]
        for key in expected_keys:
            assert key in content, f".env.example missing key: {key}"


class TestGitignore:
    """AC #13: .env is gitignored."""

    @pytest.mark.test_id("1.3-UNIT-025")
    @pytest.mark.p2
    def test_gitignore_contains_env(self):
        gitignore = Path(__file__).resolve().parents[1] / ".gitignore"
        content = gitignore.read_text()
        assert ".env" in content
        assert "data_cache/" in content
        assert "mlruns/" in content


class TestNoImportTimeIO:
    """AC #14: Importing core.config performs no I/O."""

    @pytest.mark.test_id("1.3-UNIT-026")
    @pytest.mark.p1
    def test_import_config_no_filesystem_access(self):
        original_mkdir = Path.mkdir
        calls: list[Path] = []

        def track_mkdir(self, *a, **kw):
            calls.append(self)
            return original_mkdir(self, *a, **kw)

        with patch.object(Path, "mkdir", track_mkdir):
            import trade_advisor.core.config

            config_module = trade_advisor.core.config
            assert hasattr(config_module, "AppConfig")
            assert hasattr(config_module, "load_config")
            mkdir_calls = list(calls)
            assert len(mkdir_calls) == 0, f"Import-time mkdir calls: {mkdir_calls}"


class TestLoadConfigFunction:
    """AC #14: load_config() creates dirs and returns FullConfig."""

    @pytest.mark.test_id("1.3-UNIT-027")
    @pytest.mark.p1
    def test_load_config_returns_full_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        full = load_config()
        assert isinstance(full, FullConfig)
        assert isinstance(full.app, AppConfig)
        assert isinstance(full.secrets, SecretsConfig)

    @pytest.mark.test_id("1.3-UNIT-028")
    @pytest.mark.p1
    def test_load_config_creates_dirs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        cache_dir = tmp_path / "data_cache"
        monkeypatch.setenv("DATA__CACHE_DIR", str(cache_dir))
        load_config()
        assert cache_dir.exists()

    @pytest.mark.test_id("1.3-UNIT-029")
    @pytest.mark.p2
    def test_load_config_restores_env_on_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.delenv("DETERMINISM__RANDOM_SEED", raising=False)
        load_config(override_env={"DETERMINISM__RANDOM_SEED": "99"})
        import os

        assert os.environ.get("DETERMINISM__RANDOM_SEED") is None

    @pytest.mark.test_id("1.3-UNIT-030")
    @pytest.mark.p1
    def test_load_config_rejects_non_app_env_var(self):
        with pytest.raises(ValueError, match="Refusing to override"):
            load_config(override_env={"PATH": "/evil"})


class TestCLICommands:
    """AC #15-16: CLI config commands."""

    @pytest.mark.test_id("1.3-UNIT-031")
    @pytest.mark.p1
    def test_config_validate_command_success(self, monkeypatch: pytest.MonkeyPatch):
        from trade_advisor.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["config", "validate"])
        assert result.exit_code == 0
        assert "passed" in result.output.lower() or "loaded" in result.output.lower()

    @pytest.mark.test_id("1.3-UNIT-032")
    @pytest.mark.p1
    def test_config_set_key_rejects_unknown(self):
        from trade_advisor.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["config", "set-key", "INVALID_KEY"], input="val\n")
        assert result.exit_code != 0

    @pytest.mark.test_id("1.3-UNIT-033")
    @pytest.mark.p2
    def test_config_set_key_rejects_empty(self):
        from trade_advisor.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["config", "set-key", "YAHOO_API_KEY"], input="\n")
        assert result.exit_code != 0
        assert "empty" in result.output.lower() or "not allowed" in result.output.lower()


class TestConfigModelStructure:
    """AC #10: Nested sub-models with correct types."""

    @pytest.mark.test_id("1.3-UNIT-034")
    @pytest.mark.p1
    def test_appconfig_has_all_submodels(self):
        cfg = AppConfig(_env_file=None)
        assert isinstance(cfg.data, DataConfig)
        assert isinstance(cfg.backtest, BacktestConfig)
        assert isinstance(cfg.execution, ExecutionConfig)
        assert isinstance(cfg.determinism, DeterminismConfig)
        assert isinstance(cfg.database, DatabaseConfig)
        assert isinstance(cfg.logging, LoggingConfig)
        assert cfg.risk is None

    @pytest.mark.test_id("1.3-UNIT-035")
    @pytest.mark.p1
    def test_risk_config_with_required_field(self):
        r = RiskConfig(max_position_size=Decimal("100000"))
        assert r.daily_loss_limit == Decimal("5000")
        assert r.max_sector_exposure == Decimal("30.0")

    @pytest.mark.test_id("1.3-UNIT-036")
    @pytest.mark.p1
    def test_backtest_config_preserves_cost_model(self):
        b = BacktestConfig()
        assert b.cost.slippage_pct == 0.0
        assert b.cost.commission_pct == 0.0
        assert b.cost.commission_fixed == 0.0
        assert b.cost.slippage_atr_fraction == 0.0
        b2 = BacktestConfig(cost=CostModel(slippage_pct=0.0005, commission_pct=0.001))
        assert b2.cost.slippage_pct == 0.0005
        assert b2.cost.commission_pct == 0.001
        dumped = b2.model_dump()
        assert dumped["cost"]["slippage_pct"] == 0.0005
        restored = BacktestConfig(**dumped)
        assert restored.cost.slippage_pct == 0.0005


class TestReviewPatches:
    """Patches from code review (P1-P10, D2-D4)."""

    @patch("trade_advisor.core.secrets._init_keyring")
    @pytest.mark.test_id("1.3-UNIT-037")
    @pytest.mark.p1
    def test_p1_empty_env_vars_dict_does_not_leak_os_environ(self, mock_init):
        mock_kr = MagicMock()
        mock_kr.get_password.return_value = None
        mock_init.return_value = mock_kr
        import os

        os.environ["YAHOO_API_KEY"] = "should_not_appear"
        try:
            secrets = load_secrets(env_vars={})
            assert secrets.yahoo_api_key is None
        finally:
            os.environ.pop("YAHOO_API_KEY", None)

    @patch("trade_advisor.core.secrets._init_keyring")
    @pytest.mark.test_id("1.3-UNIT-038")
    @pytest.mark.p1
    def test_p4_empty_string_keyring_ignored(self, mock_init):
        mock_kr = MagicMock()
        mock_kr.get_password.return_value = ""
        mock_init.return_value = mock_kr
        secrets = load_secrets(env_vars={"YAHOO_API_KEY": "real_value"})
        assert secrets.get_secret_value("yahoo_api_key") == "real_value"

    @pytest.mark.test_id("1.3-UNIT-039")
    @pytest.mark.p1
    def test_p4_set_key_rejects_empty_string(self):
        with pytest.raises(ValueError, match="empty"):
            set_key("YAHOO_API_KEY", "")

    @pytest.mark.test_id("1.3-UNIT-040")
    @pytest.mark.p2
    def test_p4_set_key_rejects_whitespace_only(self):
        with pytest.raises(ValueError, match="empty"):
            set_key("YAHOO_API_KEY", "   ")

    @pytest.mark.test_id("1.3-UNIT-041")
    @pytest.mark.p1
    def test_p8_get_secret_value_rejects_unknown_field(self):
        s = SecretsConfig(yahoo_api_key="test")
        with pytest.raises(ValueError, match="Unknown secret field"):
            s.get_secret_value("nonexistent_key")

    @pytest.mark.test_id("1.3-UNIT-042")
    @pytest.mark.p1
    def test_p3_secrets_source_defensive_copy(self):
        shared = {"yahoo_api_key": "keyring"}
        s = SecretsConfig(yahoo_api_key="x", _secrets_source=shared)
        shared["yahoo_api_key"] = "modified"
        assert s._secrets_source["yahoo_api_key"] == "keyring"
