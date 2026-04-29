"""Application configuration via pydantic-settings.

ALL configuration is loaded through ``load_config()`` — importing this module
performs **zero I/O** (no filesystem reads, no keyring calls, no directory
creation).  See AC #14.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from trade_advisor.core.logging import configure_logging as _configure_logging
from trade_advisor.core.secrets import SecretsConfig, get_api_key, load_secrets  # noqa: F401
from trade_advisor.core.types import DecimalStr

log = logging.getLogger("trade_advisor.config")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


class DataConfig(BaseModel):
    cache_dir: Path = Field(default_factory=lambda: _project_root() / "data_cache")
    staleness_threshold_sec: int = Field(3600, ge=0)
    retry_attempts: int = Field(3, ge=0)
    retry_delay_sec: float = Field(1.0, ge=0)


class CostModel(BaseModel):
    commission_pct: float = Field(0.0, ge=0, description="Fraction per trade, e.g. 0.0005 = 5bps")
    commission_fixed: float = Field(
        0.0, ge=0, description="Fixed $ per trade (not yet implemented)"
    )
    slippage_pct: float = Field(0.0005, ge=0, description="Fraction of price lost to slippage")

    @model_validator(mode="after")
    def _guard_unimplemented_fixed_commission(self):
        if self.commission_fixed != 0:
            raise ValueError(
                "commission_fixed is not yet implemented by the backtest engine. "
                "Use commission_pct for percentage-based costs, or wait for the "
                "equity-tracking engine refactor."
            )
        return self


class BacktestConfig(BaseModel):
    initial_cash: DecimalStr = Field(
        Decimal("100000"), gt=0, description="Starting capital in dollars"
    )
    cost: CostModel = CostModel()  # type: ignore[call-arg]
    freq: str = "1D"
    strict: bool = Field(
        True,
        description="If True, raise on NaN in equity curve. If False, forward-fill and warn.",
    )


class RiskConfig(BaseModel):
    max_position_size: DecimalStr = Field(..., gt=0, description="Max position size in dollars")
    max_portfolio_drawdown_pct: DecimalStr = Field(Decimal("20.0"), ge=0, le=100)
    max_sector_exposure: DecimalStr = Field(Decimal("30.0"), ge=0, le=100)
    daily_loss_limit: DecimalStr = Field(Decimal("5000"), ge=0)


class ExecutionConfig(BaseModel):
    slippage_model: Literal["fixed", "percentage", "volume-weighted"] = "percentage"
    slippage_bps: DecimalStr = Field(Decimal("5.0"), ge=0)
    commission_per_share: DecimalStr = Field(Decimal("0.005"), ge=0)
    commission_min: DecimalStr = Field(Decimal("1.0"), ge=0)


class DeterminismConfig(BaseModel):
    random_seed: int = Field(42, ge=0)
    deterministic_mode: bool = True


class DatabaseConfig(BaseModel):
    path: Path = Field(default_factory=lambda: _project_root() / "trade_advisor.db")
    wal_mode: bool = True
    backup_path: Path | None = None


class LoggingConfig(BaseModel):
    level: str = Field("INFO", pattern=r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    json_logs: bool = False
    audit_log_path: Path | None = None


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_project_root() / ".env"),
        env_file_encoding="utf-8",
        frozen=True,
        extra="forbid",
        env_nested_delimiter="__",
    )

    data: DataConfig = DataConfig()  # type: ignore[call-arg]
    backtest: BacktestConfig = BacktestConfig()  # type: ignore[call-arg]
    risk: RiskConfig | None = None
    execution: ExecutionConfig = ExecutionConfig()  # type: ignore[call-arg]
    determinism: DeterminismConfig = DeterminismConfig()  # type: ignore[call-arg]
    database: DatabaseConfig = DatabaseConfig()  # type: ignore[call-arg]
    logging: LoggingConfig = LoggingConfig()  # type: ignore[call-arg]
    secrets: SecretsConfig | None = None


class FullConfig(BaseModel):
    """Runtime config: ``AppConfig`` + resolved ``SecretsConfig``."""

    app: AppConfig
    secrets: SecretsConfig


def load_config(
    env_file: str | Path | None = None,
    *,
    override_env: dict[str, str] | None = None,
) -> FullConfig:
    kwargs: dict = {}
    if env_file is not None:
        kwargs["_env_file"] = str(env_file)
    if override_env:
        import os

        _valid_prefixes = (
            "DATA__",
            "BACKTEST__",
            "RISK__",
            "EXECUTION__",
            "DETERMINISM__",
            "DATABASE__",
            "LOGGING__",
        )
        for k in override_env:
            if not any(k.startswith(p) for p in _valid_prefixes):
                raise ValueError(f"Refusing to override non-app env var: {k}")
        old: dict[str, str | None] = {k: os.environ.get(k) for k in override_env}
        try:
            for k, v in override_env.items():
                os.environ[k] = v
            cfg = AppConfig(**kwargs)
        finally:
            for k in override_env:
                if old[k] is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = old[k]  # type: ignore[assignment]
    else:
        cfg = AppConfig(**kwargs)
    _ensure_dirs(cfg)
    secrets = load_secrets()
    return FullConfig(app=cfg, secrets=secrets)


def _ensure_dirs(cfg: AppConfig) -> None:
    for d in (cfg.data.cache_dir, _project_root() / "mlruns"):
        try:
            d.mkdir(parents=True, exist_ok=True)
        except PermissionError as exc:
            log.warning("Cannot create directory %s: %s", d, exc)


def format_config_error(exc: ValidationError) -> str:
    lines: list[str] = []
    for err in exc.errors():
        field = ".".join(str(loc) for loc in err["loc"])
        err_type = err["type"]
        if (
            err_type == "missing"
            or "input_type" in err_type
            or "decimal" in err_type
            or "int_" in err_type
        ):
            lines.append(f"Required config missing: {field}. Set it in .env or as env var.")
        else:
            lines.append(f"Config error for {field}: {err['msg']}")
    return "\n".join(lines)


def setup_logging(level: int = logging.INFO, json_logs: bool = False) -> None:
    _configure_logging(level=level, json_logs=json_logs)
