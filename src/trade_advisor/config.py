"""Backward-compatible re-export shim.

All new code should import from ``trade_advisor.core.config`` instead.
This module exists so that existing imports in ``conftest.py``, CLI, and
other modules continue to work during the migration period.
"""

from __future__ import annotations

from pathlib import Path

from trade_advisor.core.config import (
    AppConfig,
    BacktestConfig,
    CostModel,
    DatabaseConfig,
    DataConfig,
    DeterminismConfig,
    ExecutionConfig,
    LoggingConfig,
    RiskConfig,
    load_config,
    setup_logging,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_CACHE_DIR = PROJECT_ROOT / "data_cache"
MLRUNS_DIR = PROJECT_ROOT / "mlruns"
CONFIGS_DIR = PROJECT_ROOT / "configs"

DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
MLRUNS_DIR.mkdir(parents=True, exist_ok=True)


class AppSettings:
    """Legacy shim — use ``DeterminismConfig`` or ``load_config()`` instead."""

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed


settings = AppSettings()

__all__ = [
    "CONFIGS_DIR",
    "DATA_CACHE_DIR",
    "MLRUNS_DIR",
    "PROJECT_ROOT",
    "AppConfig",
    "AppSettings",
    "BacktestConfig",
    "CostModel",
    "DataConfig",
    "DatabaseConfig",
    "DeterminismConfig",
    "ExecutionConfig",
    "LoggingConfig",
    "RiskConfig",
    "load_config",
    "settings",
    "setup_logging",
]
