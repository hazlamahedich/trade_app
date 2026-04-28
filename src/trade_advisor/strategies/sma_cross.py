"""Simple moving-average crossover strategy.

Long when fast SMA > slow SMA, flat otherwise. Signals are shifted by 1 bar
to avoid lookahead: the decision for bar t+1 uses only information up to bar t.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator

from trade_advisor.strategies.base import Strategy
from trade_advisor.strategies.schemas import SignalBatch, SignalModel


class SmaCrossConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    fast: int = Field(gt=0, description="Fast SMA lookback period")
    slow: int = Field(gt=0, description="Slow SMA lookback period")
    allow_short: bool = Field(default=False, description="Allow short signals")

    @model_validator(mode="after")
    def fast_less_than_slow(self) -> SmaCrossConfig:
        if self.fast >= self.slow:
            raise ValueError(f"fast ({self.fast}) must be < slow ({self.slow})")
        return self


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
    def information_latency(self) -> int:
        return 1

    @property
    def warmup_period(self) -> int:
        return self.slow

    def generate_signals(self, ohlcv: pd.DataFrame) -> pd.Series:
        if ohlcv.empty:
            return pd.Series(dtype="float64", name="signal")

        close = ohlcv["adj_close"] if "adj_close" in ohlcv.columns else ohlcv["close"]
        fast_ma = close.rolling(self.fast, min_periods=self.fast).mean()
        slow_ma = close.rolling(self.slow, min_periods=self.slow).mean()

        raw = pd.Series(0.0, index=close.index, dtype="float64")
        raw[fast_ma > slow_ma] = 1.0
        if self.allow_short:
            raw[fast_ma < slow_ma] = -1.0

        shifted = raw.shift(1)
        shifted.iloc[: self.slow] = 0.0
        shifted = shifted.fillna(0.0).astype("float64")
        shifted.name = "signal"
        return shifted

    def to_config(self) -> SmaCrossConfig:
        return SmaCrossConfig(fast=self.fast, slow=self.slow, allow_short=self.allow_short)

    @classmethod
    def from_config(cls, config: SmaCrossConfig) -> SmaCross:
        return cls(fast=config.fast, slow=config.slow, allow_short=config.allow_short)

    def to_signal_batch(self, ohlcv: pd.DataFrame, symbol: str) -> SignalBatch:
        signals = self.generate_signals(ohlcv)
        if not isinstance(signals.index, pd.DatetimeIndex):
            raise TypeError(
                f"to_signal_batch requires DatetimeIndex, got {type(signals.index).__name__}"
            )
        now = datetime.now(UTC)
        signal_models = []
        for ts, val in zip(signals.index, signals.values, strict=True):
            if val != 0.0:
                signal_models.append(
                    SignalModel(
                        timestamp=ts,
                        symbol=symbol,
                        signal=float(val),
                        strategy_name=self.name,
                    )
                )
        return SignalBatch(signals=signal_models, strategy_name=self.name, generated_at=now)
