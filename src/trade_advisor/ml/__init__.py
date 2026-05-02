"""ML module — prediction-to-strategy bridge and (future) training pipeline."""

from __future__ import annotations

from trade_advisor.ml.backtest_adapter import (
    MLStrategy,
    MLStrategyConfig,
    PredictionProvider,
    SignalMode,
)

__all__ = [
    "MLStrategy",
    "MLStrategyConfig",
    "PredictionProvider",
    "SignalMode",
]
