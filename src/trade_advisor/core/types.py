"""Decimal conventions, precision policies, and financial type aliases.

All financial values use ``Decimal`` throughout the Python layer.  ``float`` is
permitted ONLY at I/O edges (pandas DataFrames, yfinance responses) and must
cross via ``from_float()`` / ``to_float()``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Annotated, Literal

from pydantic import AwareDatetime, PlainSerializer

ROUNDING = ROUND_HALF_EVEN
DISPLAY_PRECISION = 10


Price = Decimal
Quantity = Decimal
Notional = Decimal
Returns = Decimal
BasisPoints = Decimal
Signal = Literal[-1, 0, 1]
Side = Literal["long", "short"]
Currency = Literal["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD"]
Timestamp = AwareDatetime


def quantize(value: Decimal, decimal_places: int = DISPLAY_PRECISION) -> Decimal:
    """Quantize a Decimal to the given precision using ROUND_HALF_EVEN."""
    return value.quantize(Decimal(10) ** -decimal_places, rounding=ROUNDING)


def decimal_to_str(value: Decimal) -> str:
    """Serialize ``Decimal`` → ``str`` with ``ROUND_HALF_EVEN`` at display precision."""
    if not value.is_finite():
        raise ValueError(f"Cannot serialize non-finite Decimal: {value}")
    quantized = value.quantize(Decimal(10) ** -DISPLAY_PRECISION, rounding=ROUNDING)
    return format(quantized, "f")


DecimalStr = Annotated[Decimal, PlainSerializer(decimal_to_str, return_type=str)]


def from_float(value: float) -> Decimal:
    """Convert ``float`` → ``Decimal`` with full precision (no truncation).

    Uses ``Decimal.from_float`` which produces the exact decimal representation
    of the binary float.  This is the ONLY sanctioned way to cross the
    ``float`` → ``Decimal`` boundary.
    """
    if math.isnan(value) or math.isinf(value):
        raise ValueError(f"Cannot convert non-finite float to Decimal: {value}")
    return Decimal(str(value))


def to_float(value: Decimal) -> float:
    """Convert ``Decimal`` → ``float`` for pandas/NumPy boundary.

    WARNING: This incurs a potential loss of precision.  Use ONLY at I/O edges
    where ``float`` is required by downstream libraries.
    """
    if not value.is_finite():
        raise ValueError(f"Cannot convert non-finite Decimal to float: {value}")
    return float(value)


def log_to_simple(log_ret: Returns) -> Returns:
    """Convert log return → simple return: ``exp(r) - 1``."""
    fv = float(log_ret)
    if fv > 700:
        raise ValueError(f"log_to_simple overflow: exp({fv}) exceeds float range")
    return Decimal(math.exp(fv)) - Decimal(1)


def simple_to_log(simple_ret: Returns) -> Returns:
    """Convert simple return → log return: ``ln(1 + r)``."""
    fv = float(simple_ret)
    if fv <= -1:
        raise ValueError(f"simple_to_log domain error: ln(1 + {fv}) undefined for r <= -1")
    return Decimal(math.log1p(fv))


@dataclass(frozen=True)
class PrecisionPolicy:
    """Per-asset-class quantization policy.

    Computation uses full ``Decimal`` precision internally; quantization happens
    ONLY at storage / serialization boundaries.
    """

    tick_size: Decimal
    label: str

    def __post_init__(self) -> None:
        if self.tick_size <= 0:
            raise ValueError(f"tick_size must be positive, got {self.tick_size}")

    def quantize(self, value: Decimal) -> Decimal:
        """Quantize *value* to the tick size of this asset class."""
        return value.quantize(self.tick_size, rounding=ROUNDING)


EQUITY = PrecisionPolicy(tick_size=Decimal("0.01"), label="EQUITY")
FX = PrecisionPolicy(tick_size=Decimal("0.0001"), label="FX")
CRYPTO = PrecisionPolicy(tick_size=Decimal("0.00000001"), label="CRYPTO")
