from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from pydantic import AwareDatetime, BaseModel, ConfigDict, field_validator, model_validator


class Bar(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    timestamp: AwareDatetime
    resolution: timedelta
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    vwap: Decimal | None = None
    trade_count: int | None = None

    @field_validator("open", "high", "low", "close")
    @classmethod
    def _prices_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("OHLC prices must be positive (> 0)")
        return v

    @field_validator("volume")
    @classmethod
    def _volume_non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("volume must be non-negative (>= 0)")
        return v

    # Architecture spec calls for @field_validator(mode="after") for OHLC relationships,
    # but Pydantic V2 field_validator cannot access sibling fields. model_validator is correct.
    @model_validator(mode="after")
    def _validate_ohlc_relationships(self) -> Bar:
        if self.high < self.low:
            raise ValueError(f"high ({self.high}) must be >= low ({self.low})")
        if self.high < max(self.open, self.close):
            raise ValueError(
                f"high ({self.high}) must be >= max(open, close) ({max(self.open, self.close)})"
            )
        if self.low > min(self.open, self.close):
            raise ValueError(
                f"low ({self.low}) must be <= min(open, close) ({min(self.open, self.close)})"
            )
        return self
