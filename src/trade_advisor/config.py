"""Central configuration and paths."""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from trade_advisor.core.logging import configure_logging as _configure_logging

# Paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_CACHE_DIR = PROJECT_ROOT / "data_cache"
MLRUNS_DIR = PROJECT_ROOT / "mlruns"
CONFIGS_DIR = PROJECT_ROOT / "configs"

DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
MLRUNS_DIR.mkdir(parents=True, exist_ok=True)


class AppSettings(BaseModel):
    seed: int = 42


settings = AppSettings()


class CostModel(BaseModel):
    """Transaction cost assumptions.

    Defaults are reasonable for retail US equities. Override per asset class.

    TODO: commission_fixed is not yet applied by the backtest engine.
          A ValueError is raised if set to a non-zero value to prevent
          silent misconfiguration. Full implementation deferred to the
          equity-tracking engine refactor (Epic 2+).
    """

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
    initial_cash: float = Field(100_000.0, gt=0, description="Starting capital in dollars")
    cost: CostModel = CostModel()  # type: ignore[call-arg]
    freq: str = "1D"


def setup_logging(level: int = logging.INFO, json_logs: bool = False) -> None:
    _configure_logging(level=level, json_logs=json_logs)
