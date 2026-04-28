"""Simple moving-average crossover strategy.

Long when fast SMA > slow SMA, flat otherwise. Signals are shifted by 1 bar
to avoid lookahead: the decision for bar t+1 uses only information up to bar t.
"""

from __future__ import annotations

import pandas as pd

from trade_advisor.strategies.base import Strategy


class SmaCross(Strategy):
    name = "sma_cross"

    def __init__(self, fast: int = 20, slow: int = 50, allow_short: bool = False):
        if fast <= 0 or slow <= 0:
            raise ValueError("windows must be positive")
        if fast >= slow:
            raise ValueError("fast window must be strictly less than slow window")
        super().__init__(fast=fast, slow=slow, allow_short=allow_short)
        self.fast = fast
        self.slow = slow
        self.allow_short = allow_short

    @property
    def warmup_period(self) -> int:
        return self.slow

    def generate_signals(self, ohlcv: pd.DataFrame) -> pd.Series:
        close = ohlcv["adj_close"] if "adj_close" in ohlcv.columns else ohlcv["close"]
        fast_ma = close.rolling(self.fast, min_periods=self.fast).mean()
        slow_ma = close.rolling(self.slow, min_periods=self.slow).mean()

        raw = pd.Series(0.0, index=close.index, dtype="float64")
        raw[fast_ma > slow_ma] = 1.0
        if self.allow_short:
            raw[fast_ma < slow_ma] = -1.0

        shifted = raw.shift(1).fillna(0.0).astype("float64")
        shifted.name = "signal"
        return shifted
