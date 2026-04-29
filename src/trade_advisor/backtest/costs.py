"""Transaction cost engine for realistic backtest cost modeling.

Provides ``CostEngine`` — a frozen dataclass that computes per-trade costs
from fixed, basis-point, and ATR-based slippage components.  Also provides
``forex_carry_cost`` for overnight carry and ``apply_costs`` for post-hoc
trade-level cost attribution.

Cost components
---------------
- **fixed_per_trade**: Flat dollar fee per trade (e.g., $1 per fill).
- **bps**: Cost in basis points of traded notional (e.g., 5 bps = 0.05%).
- **slippage_atr_fraction**: Slippage as a fraction of ATR per share,
  scaled by position size ``(trade_notional / price)`` shares.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from trade_advisor.config import CostModel


@dataclass(frozen=True)
class CostEngine:
    """Immutable transaction cost calculator.

    All fields default to zero (zero-cost engine).

    Raises ``ValueError`` if any field is negative.

    Examples
    --------
    >>> CostEngine().compute(100_000)  # zero-cost
    0.0
    >>> CostEngine(bps=5.0).compute(100_000)  # 5 bps
    50.0
    """

    fixed_per_trade: float = 0.0
    bps: float = 0.0
    slippage_atr_fraction: float = 0.0

    def __post_init__(self) -> None:
        if self.fixed_per_trade < 0:
            raise ValueError(f"fixed_per_trade must be >= 0, got {self.fixed_per_trade}")
        if self.bps < 0:
            raise ValueError(f"bps must be >= 0, got {self.bps}")
        if self.slippage_atr_fraction < 0:
            raise ValueError(
                f"slippage_atr_fraction must be >= 0, got {self.slippage_atr_fraction}"
            )

    def compute(
        self, trade_notional: float, atr: float | None = None, price: float | None = None
    ) -> float:
        """Compute total per-trade cost.

        Parameters
        ----------
        trade_notional : float
            Absolute dollar value of the trade (sign ignored via ``abs()``).
        atr : float | None
            Average True Range for ATR-based slippage.  Ignored when
            ``slippage_atr_fraction`` is zero or ``atr`` is ``None``.
        price : float | None
            Price per share used to convert ATR-based slippage from
            per-share to total dollar cost.  Required when ``atr`` is
            provided and ``slippage_atr_fraction > 0``.

        Returns
        -------
        float
            Total cost in dollars (always >= 0).
        """
        notional = abs(trade_notional)
        bps_cost = notional * (self.bps / 10_000)
        slippage_cost = 0.0
        if atr is not None and self.slippage_atr_fraction > 0:
            if price is not None and price > 0:
                shares = notional / price
                slippage_cost = self.slippage_atr_fraction * atr * shares
            elif price is None:
                raise ValueError(
                    "price is required when slippage_atr_fraction > 0 and atr is provided"
                )
        return self.fixed_per_trade + bps_cost + slippage_cost

    def compute_breakdown(
        self, trade_notional: float, atr: float | None = None, price: float | None = None
    ) -> dict[str, float]:
        """Return cost decomposition dict.

        Returns
        -------
        dict[str, float]
            ``{"commission": fixed + bps_cost, "slippage": slippage_cost, "total": sum}``
        """
        notional = abs(trade_notional)
        bps_cost = notional * (self.bps / 10_000)
        commission = self.fixed_per_trade + bps_cost
        slippage_cost = 0.0
        if atr is not None and self.slippage_atr_fraction > 0:
            if price is not None and price > 0:
                shares = notional / price
                slippage_cost = self.slippage_atr_fraction * atr * shares
            elif price is None:
                raise ValueError(
                    "price is required when slippage_atr_fraction > 0 and atr is provided"
                )
        return {
            "commission": commission,
            "slippage": slippage_cost,
            "total": commission + slippage_cost,
        }

    @classmethod
    def reality_check(cls) -> CostEngine:
        """Return an institutional-grade cost preset.

        US equity institutional estimate.  Adjust for asset class, venue,
        geography.

        Returns
        -------
        CostEngine
            ``CostEngine(fixed_per_trade=1.0, bps=5.0, slippage_atr_fraction=0.05)``
        """
        return cls(fixed_per_trade=1.0, bps=5.0, slippage_atr_fraction=0.05)

    def sensitivity(self, factor: float) -> CostEngine:
        """Return a new CostEngine with ALL cost fields scaled by *factor*.

        Useful for sensitivity analysis — crank costs up/down to see impact
        on alpha.

        Parameters
        ----------
        factor : float
            Multiplicative scaling factor (e.g., 2.0 doubles all costs).
            Must be >= 0.

        Returns
        -------
        CostEngine
            New engine with scaled fields.

        Raises
        ------
        ValueError
            If *factor* is negative.
        """
        if factor < 0:
            raise ValueError(f"sensitivity factor must be >= 0, got {factor}")
        return CostEngine(
            fixed_per_trade=self.fixed_per_trade * factor,
            bps=self.bps * factor,
            slippage_atr_fraction=self.slippage_atr_fraction * factor,
        )

    @classmethod
    def from_model(cls, model: CostModel) -> CostEngine:
        """Construct a CostEngine from a Pydantic ``CostModel`` config.

        Maps config-layer fields to runtime-layer fields via the canonical
        mapping:

        - ``commission_pct`` + ``slippage_pct`` → ``bps`` (combined, in bp)
        - ``commission_fixed`` → ``fixed_per_trade`` (direct)
        - ``slippage_atr_fraction`` → ``slippage_atr_fraction`` (direct)
        """
        total_bps = (model.commission_pct + model.slippage_pct) * 10_000
        return cls(
            fixed_per_trade=model.commission_fixed,
            bps=total_bps,
            slippage_atr_fraction=model.slippage_atr_fraction,
        )


def forex_carry_cost(position_notional: float, swap_points: float, days: int) -> float:
    """Compute cumulative forex overnight carry cost.

    Parameters
    ----------
    position_notional : float
        Dollar value of the position (sign ignored via ``abs()``).
    swap_points : float
        Overnight swap points in basis-point-like units.  Must be >= 0.
    days : int
        Number of holding days.  Must be >= 0.

    Returns
    -------
    float
        Cumulative carry cost in dollars (always >= 0).

    Limitations (deferred to Phase 2 data pipeline):
        - No Wednesday 3x rollover adjustment
        - No long/short swap asymmetry
        - Constant ``swap_points`` assumed (no time-varying rates)
        - No settlement lag (T+2) modelling
        - Data pipeline for live swap rates not yet available
    """
    if swap_points < 0:
        raise ValueError(f"swap_points must be >= 0, got {swap_points}")
    if days < 0:
        raise ValueError(f"days must be >= 0, got {days}")
    return abs(position_notional) * swap_points * days / 10_000


def apply_costs(result: object, cost_model: CostModel) -> object:
    """Add a ``"cost"`` column (float64) to ``result.trades``.

    Internally builds a ``CostEngine`` from *cost_model* and computes
    per-trade cost based on the trade's notional value.

    Parameters
    ----------
    result : BacktestResult
        Backtest result with a ``trades`` DataFrame.
    cost_model : CostModel
        Pydantic cost configuration.

    Returns
    -------
    BacktestResult
        Same result with ``trades`` DataFrame now containing a ``"cost"``
        column (float64).

    Raises
    ------
    TypeError
        If *result* is not a ``BacktestResult``.
    ValueError
        If *result.trades* is missing required columns.
    """
    from trade_advisor.backtest.engine import BacktestResult

    if not isinstance(result, BacktestResult):
        raise TypeError(
            f"apply_costs expects a BacktestResult, got {type(result).__name__}"
        )
    engine = CostEngine.from_model(cost_model)

    trades = result.trades.copy()
    if trades.empty:
        trades["cost"] = pd.Series(dtype="float64")
        return BacktestResult(
            equity=result.equity,
            returns=result.returns,
            positions=result.positions,
            trades=trades,
            config=result.config,
            meta=result.meta,
        )

    required_cols = {"entry_price", "weight"}
    missing = required_cols - set(trades.columns)
    if missing:
        raise ValueError(
            f"trades DataFrame is missing required columns: {sorted(missing)}. "
            f"Available columns: {list(trades.columns)}"
        )

    prices = trades["entry_price"]
    notionals = (prices * trades["weight"]).abs()
    costs = notionals.apply(lambda n: engine.compute(n, price=n if n > 0 else 1.0))
    trades["cost"] = costs.astype("float64")

    return BacktestResult(
        equity=result.equity,
        returns=result.returns,
        positions=result.positions,
        trades=trades,
        config=result.config,
        meta=result.meta,
    )
