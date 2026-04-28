"""Position sizing methods: fixed-fractional, half-Kelly, vol-targeting, inverse-vol.

Each function returns a ``Decimal`` notional dollar amount, quantized to
``DISPLAY_PRECISION`` via ``core/types.py:quantize()``.  All arithmetic uses
``Decimal`` exclusively — floats cross the boundary only through ``from_float()``.
"""

from __future__ import annotations

import math
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from trade_advisor.core.types import DecimalStr, from_float, quantize

VOL_FLOOR = Decimal("0.01")
MAX_FRACTION = Decimal("1.0")


def _validate_equity(equity: Decimal) -> None:
    if not isinstance(equity, Decimal):
        raise ValueError(f"equity must be a Decimal, got {type(equity).__name__}")
    if not equity.is_finite():
        raise ValueError(f"equity must be finite, got {equity}")
    if equity < 0:
        raise ValueError(f"equity must be non-negative, got {equity}")


def _validate_fraction(fraction: Decimal) -> None:
    if not isinstance(fraction, Decimal):
        raise ValueError(f"fraction must be a Decimal, got {type(fraction).__name__}")
    if not fraction.is_finite():
        raise ValueError(f"fraction must be finite, got {fraction}")
    if fraction <= 0:
        raise ValueError(f"fraction must be positive, got {fraction}")


def _validate_volatility(vol: Decimal, name: str) -> None:
    if not isinstance(vol, Decimal):
        raise ValueError(f"{name} must be a Decimal, got {type(vol).__name__}")
    if not vol.is_finite():
        raise ValueError(f"{name} must be finite, got {vol}")
    if vol <= 0:
        raise ValueError(f"{name} must be positive, got {vol}")


def _validate_avg_win(avg_win: Decimal) -> None:
    if not isinstance(avg_win, Decimal):
        raise ValueError(f"avg_win must be a Decimal, got {type(avg_win).__name__}")
    if not avg_win.is_finite() or avg_win <= 0:
        raise ValueError(f"avg_win must be positive and finite, got {avg_win}")


def _validate_avg_loss(avg_loss: Decimal) -> None:
    if not isinstance(avg_loss, Decimal):
        raise ValueError(f"avg_loss must be a Decimal, got {type(avg_loss).__name__}")
    if not avg_loss.is_finite() or avg_loss <= 0:
        raise ValueError(f"avg_loss must be positive and finite, got {avg_loss}")


def _validate_win_rate(win_rate: float) -> None:
    if not isinstance(win_rate, (int, float)):
        raise ValueError(f"win_rate must be a float, got {type(win_rate).__name__}")
    if math.isnan(win_rate) or math.isinf(win_rate):
        raise ValueError(f"win_rate must be finite, got {win_rate}")
    if win_rate <= 0 or win_rate > 1:
        raise ValueError(f"win_rate must be in (0, 1], got {win_rate}")


def _validate_signal(signal: float) -> None:
    if not isinstance(signal, (int, float)):
        raise ValueError(f"signal must be a float, got {type(signal).__name__}")
    if math.isnan(signal) or math.isinf(signal):
        raise ValueError(f"signal must be finite, got {signal}")
    if abs(signal) > 1.0:
        raise ValueError(f"signal magnitude must be in [0.0, 1.0], got {signal}")


def fixed_fractional(equity: Decimal, fraction: Decimal, *, signal: float = 1.0) -> Decimal:
    _validate_equity(equity)
    _validate_fraction(fraction)
    _validate_signal(signal)
    if equity == Decimal("0"):
        return Decimal("0")
    clamped = min(fraction, MAX_FRACTION)
    return quantize(equity * clamped * from_float(abs(signal)))


def half_kelly(
    equity: Decimal,
    win_rate: float,
    avg_win: Decimal,
    avg_loss: Decimal,
    *,
    signal: float = 1.0,
) -> Decimal:
    _validate_equity(equity)
    _validate_win_rate(win_rate)
    _validate_signal(signal)
    _validate_avg_win(avg_win)
    _validate_avg_loss(avg_loss)
    if equity == Decimal("0"):
        return Decimal("0")

    wr = from_float(win_rate)
    edge = wr * avg_win - (Decimal("1") - wr) * avg_loss
    if edge <= 0:
        return Decimal("0")
    f_star = edge / (avg_win * avg_loss)
    f_star = min(f_star, MAX_FRACTION)
    return quantize(equity * Decimal("0.5") * f_star * from_float(abs(signal)))


def vol_targeting(
    equity: Decimal,
    target_vol: Decimal,
    asset_vol: Decimal,
    *,
    signal: float = 1.0,
) -> Decimal:
    _validate_equity(equity)
    _validate_volatility(target_vol, "target_vol")
    _validate_volatility(asset_vol, "asset_vol")
    _validate_signal(signal)
    if equity == Decimal("0"):
        return Decimal("0")
    effective_vol = max(asset_vol, VOL_FLOOR)
    scale = target_vol / effective_vol
    scale = min(scale, MAX_FRACTION)
    return quantize(equity * scale * from_float(abs(signal)))


def inverse_vol(equity: Decimal, asset_vol: Decimal, *, signal: float = 1.0) -> Decimal:
    _validate_equity(equity)
    _validate_volatility(asset_vol, "asset_vol")
    _validate_signal(signal)
    if equity == Decimal("0"):
        return Decimal("0")
    effective_vol = max(asset_vol, VOL_FLOOR)
    fraction = Decimal("1.0") / (effective_vol * Decimal("100"))  # 100 = pct-to-decimal
    fraction = min(fraction, MAX_FRACTION)
    return quantize(equity * fraction * from_float(abs(signal)))


# ── Pydantic config models ────────────────────────────────────


class SizingConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    method: str


class FixedFractionalConfig(SizingConfig):
    method: str = "fixed_fractional"
    fraction: DecimalStr = Field(gt=0, le=1, description="Fraction of equity per trade")

    def compute(self, equity: Decimal, *, signal: float = 1.0) -> Decimal:
        return fixed_fractional(equity, self.fraction, signal=signal)


class HalfKellyConfig(SizingConfig):
    method: str = "half_kelly"
    win_rate: float = Field(gt=0, le=1)
    avg_win: DecimalStr = Field(gt=0)
    avg_loss: DecimalStr = Field(gt=0)

    def compute(self, equity: Decimal, *, signal: float = 1.0) -> Decimal:
        return half_kelly(equity, self.win_rate, self.avg_win, self.avg_loss, signal=signal)


class VolTargetingConfig(SizingConfig):
    method: str = "vol_targeting"
    target_vol: DecimalStr = Field(gt=0, description="Target annualized volatility")
    asset_vol: DecimalStr = Field(gt=0, description="Current asset volatility estimate")

    def compute(self, equity: Decimal, *, signal: float = 1.0) -> Decimal:
        return vol_targeting(equity, self.target_vol, self.asset_vol, signal=signal)


class InverseVolConfig(SizingConfig):
    method: str = "inverse_vol"
    asset_vol: DecimalStr = Field(gt=0)

    def compute(self, equity: Decimal, *, signal: float = 1.0) -> Decimal:
        return inverse_vol(equity, self.asset_vol, signal=signal)
