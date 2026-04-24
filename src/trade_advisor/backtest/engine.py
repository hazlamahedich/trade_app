"""Vectorized backtest engine.

This module intentionally uses pandas/numpy directly rather than vectorbt
for portability and readability. In Phase 2 we will add a vectorbt-backed
engine alongside this one; strategies are agnostic.

Model assumptions:
- Daily bars; signals at bar close, executed at next bar's open is not modelled;
  we instead assume execution at the same bar's close (conservative for daily
  swing strategies since signal itself is already shifted by 1).
- Costs charged on turnover: commission_pct * |delta_position| * price + slippage.
- No leverage, no fractional borrowing interest.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from trade_advisor.config import BacktestConfig


@dataclass
class BacktestResult:
    equity: pd.Series
    returns: pd.Series
    positions: pd.Series
    trades: pd.DataFrame
    config: BacktestConfig
    meta: dict = field(default_factory=dict)

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame({
            "equity": self.equity,
            "returns": self.returns,
            "position": self.positions,
        })


def run_backtest(
    ohlcv: pd.DataFrame,
    signal: pd.Series,
    config: BacktestConfig | None = None,
) -> BacktestResult:
    """Run a simple vectorized backtest.

    ``signal`` values are in {-1, 0, +1} and must already be lookahead-safe
    (i.e., the strategy has shifted them).
    """
    cfg = config or BacktestConfig()
    if "adj_close" in ohlcv.columns:
        price = ohlcv["adj_close"].astype("float64")
    else:
        price = ohlcv["close"].astype("float64")

    ts = pd.to_datetime(ohlcv["timestamp"])
    price.index = ts
    sig = signal.copy()
    sig.index = ts
    sig = sig.reindex(price.index).fillna(0).astype("int8")

    # Bar-to-bar asset returns
    asset_ret = price.pct_change().fillna(0.0)

    # Position held DURING bar t is sig[t] (already 1-shifted by the strategy).
    pos = sig.astype("float64")
    delta = pos.diff().abs().fillna(pos.abs())

    # Per-bar cost as a return drag.
    # Commission charged on notional turned over; slippage same.
    cost_pct = cfg.cost.commission_pct + cfg.cost.slippage_pct
    cost_drag = delta * cost_pct  # fractional return lost

    # Fixed commission as equity drag (approx): convert to fractional by dividing
    # by notional = equity * |pos before change|. We approximate with cash.
    # For a single-asset, 1x-leverage model this is typically zero (retail brokers).
    # Keep math simple for Phase 1.
    strategy_ret = pos * asset_ret - cost_drag

    equity = (1.0 + strategy_ret).cumprod() * cfg.initial_cash
    equity.name = "equity"

    trades = _extract_trades(pos, price)

    return BacktestResult(
        equity=equity,
        returns=strategy_ret.rename("returns"),
        positions=pos.rename("position"),
        trades=trades,
        config=cfg,
        meta={"bars": len(price), "n_trades": len(trades)},
    )


def _extract_trades(pos: pd.Series, price: pd.Series) -> pd.DataFrame:
    """Extract discrete trade records from a position series."""
    changes = pos.diff().fillna(pos.iloc[0])
    events = changes[changes != 0]
    records: list[dict] = []
    current_side: int = 0
    entry_ts = None
    entry_price = np.nan

    for ts, new_pos in pos.items():
        new_side = int(np.sign(new_pos))
        if new_side != current_side:
            # Close the previous position, if any.
            if current_side != 0 and entry_ts is not None:
                exit_px = float(price.loc[ts])
                ret = (exit_px / entry_price - 1.0) * current_side
                records.append({
                    "entry_ts": entry_ts,
                    "exit_ts": ts,
                    "side": current_side,
                    "entry_price": entry_price,
                    "exit_price": exit_px,
                    "return": ret,
                })
            # Open a new position, if nonzero.
            if new_side != 0:
                entry_ts = ts
                entry_price = float(price.loc[ts])
            else:
                entry_ts = None
                entry_price = np.nan
            current_side = new_side

    return pd.DataFrame.from_records(records, columns=[
        "entry_ts", "exit_ts", "side", "entry_price", "exit_price", "return",
    ])
