"""Central configuration and paths."""
from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel, Field

# Paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_CACHE_DIR = PROJECT_ROOT / "data_cache"
MLRUNS_DIR = PROJECT_ROOT / "mlruns"
CONFIGS_DIR = PROJECT_ROOT / "configs"

DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
MLRUNS_DIR.mkdir(parents=True, exist_ok=True)


class CostModel(BaseModel):
    """Transaction cost assumptions.

    Defaults are reasonable for retail US equities. Override per asset class.
    """

    commission_pct: float = Field(0.0, ge=0, description="Fraction per trade, e.g. 0.0005 = 5bps")
    commission_fixed: float = Field(0.0, ge=0, description="Fixed $ per trade")
    slippage_pct: float = Field(0.0005, ge=0, description="Fraction of price lost to slippage")


class BacktestConfig(BaseModel):
    initial_cash: float = 100_000.0
    cost: CostModel = CostModel()
    freq: str = "1D"


def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
