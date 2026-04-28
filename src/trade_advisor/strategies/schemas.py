"""Pydantic schemas for strategy signal output.

Frozen (immutable) models for validated signal transport between
strategy, backtest, and tracking layers.  Signal values use ``float``
to support continuous signals from ML strategies (SE-2); the
discrete set ``{-1, 0, +1}`` is the Phase 1 special case.
"""

from __future__ import annotations

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class SignalModel(BaseModel):
    """A single strategy signal at a point in time."""

    model_config = ConfigDict(frozen=True)

    timestamp: AwareDatetime
    symbol: str
    signal: float
    confidence: float | None = Field(default=1.0, ge=0.0, le=1.0)
    strategy_name: str

    @field_validator("signal")
    @classmethod
    def _signal_in_range(cls, v: float) -> float:
        if not (-1.0 <= v <= 1.0):
            raise ValueError(f"signal must be in [-1.0, +1.0], got {v}")
        return v

    @field_validator("confidence")
    @classmethod
    def _confidence_in_range(cls, v: float | None) -> float | None:
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError(f"confidence must be in [0.0, 1.0], got {v}")
        return v


class SignalBatch(BaseModel):
    """A batch of signals produced by a single strategy run."""

    model_config = ConfigDict(frozen=True)

    signals: list[SignalModel]
    strategy_name: str
    generated_at: AwareDatetime

    @model_validator(mode="after")
    def _check_strategy_names(self) -> SignalBatch:
        if self.signals is not None and len(self.signals) > 0:
            mismatched = [s for s in self.signals if s.strategy_name != self.strategy_name]
            if mismatched:
                raise ValueError(
                    f"SignalBatch.strategy_name is {self.strategy_name!r} but contains "
                    f"signals with strategy_name={mismatched[0].strategy_name!r}"
                )
        return self
