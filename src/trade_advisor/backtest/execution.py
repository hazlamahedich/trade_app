"""Order execution types and router protocol.

Defines ``OrderSpec``, ``FillResult``, the ``ExecutionRouter`` Protocol,
and ``MarketExecutionRouter`` — the default implementation that fills market
orders at bar close.

Order lifecycle (Phase 1):
    PENDING → SUBMITTED → FILLED | REJECTED

Partial fills and GTC/IOC time-in-force are deferred.  The ``FillResult``
interface supports ``fill_qty < order.quantity`` for future use.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol

import pandas as pd

Side = Literal["buy", "sell"]
OrderType = Literal["market", "limit", "stop", "market_on_open", "market_on_close"]


@dataclass(frozen=True)
class OrderSpec:
    """Immutable order specification.

    Raises ``ValueError`` on construction if:
    - ``quantity`` is negative or zero
    - ``order_type`` is ``"limit"`` and ``limit_price`` is ``None`` or <= 0
    - ``order_type`` is ``"stop"`` and ``stop_price`` is ``None`` or <= 0
    """

    side: Side
    order_type: OrderType
    quantity: float
    limit_price: float | None = None
    stop_price: float | None = None

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError(f"OrderSpec.quantity must be positive, got {self.quantity}")
        if self.order_type == "limit":
            if self.limit_price is None:
                raise ValueError("limit orders require a limit_price")
            if self.limit_price <= 0:
                raise ValueError(f"limit_price must be positive, got {self.limit_price}")
        if self.order_type == "stop":
            if self.stop_price is None:
                raise ValueError("stop orders require a stop_price")
            if self.stop_price <= 0:
                raise ValueError(f"stop_price must be positive, got {self.stop_price}")


@dataclass(frozen=True)
class FillResult:
    """Immutable fill record.

    ``cost_components`` is an extensible dict for future cost types
    (e.g., forex overnight carry for BT-9).
    """

    fill_price: float
    fill_qty: float
    commission: float = 0.0
    slippage_bps: float = 0.0
    filled_at: datetime | None = None
    cost_components: dict[str, float] = field(default_factory=dict)


class ExecutionRouter(Protocol):
    """Protocol for order execution routers."""

    def submit(self, order: OrderSpec, bar: pd.Series) -> FillResult | None: ...


class MarketExecutionRouter:
    """Default execution router — fills market orders at bar close price.

    Limit, stop, MOO, and MOC orders are not supported by this router;
    ``submit`` returns ``None`` for unsupported order types.
    """

    def submit(self, order: OrderSpec, bar: pd.Series) -> FillResult | None:
        if order.order_type != "market":
            return None
        fill_price = float(bar["close"])
        return FillResult(
            fill_price=fill_price,
            fill_qty=order.quantity,
            filled_at=(bar.get("timestamp") if "timestamp" in bar.index else None),
        )
