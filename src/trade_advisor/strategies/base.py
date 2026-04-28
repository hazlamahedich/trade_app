"""Strategy interface.

A Strategy produces, given OHLCV data, a ``signal`` Series aligned with the
input index. Convention:

    +1  -> long the asset
     0  -> flat
    -1  -> short the asset

Signals must be computed using ONLY information available at or before each
timestamp. Any lookahead is a bug.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import pandas as pd


@dataclass
class StrategyMeta:
    name: str
    params: dict


class Strategy(ABC):
    """Abstract base. Concrete strategies implement ``generate_signals``."""

    name: str = "base"

    def __init__(self, **params):
        self.params: dict = params

    @property
    def information_latency(self) -> int:
        """Minimum data delay in bars.  Override in subclasses as needed."""
        return 0

    @property
    def warmup_period(self) -> int:
        """Bars before signals are valid.  Override in subclasses as needed."""
        return 0

    @abstractmethod
    def generate_signals(self, ohlcv: pd.DataFrame) -> pd.Series:
        """Return a Series of {-1, 0, +1}, indexed like ohlcv."""
        ...

    def describe(self) -> StrategyMeta:
        return StrategyMeta(name=self.name, params=dict(self.params))
