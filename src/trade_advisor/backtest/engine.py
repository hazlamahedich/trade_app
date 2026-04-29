"""Vectorized backtest engine — shared types and backward-compatible entry point.

This module defines ``BacktestResult`` and ``run_backtest()``.  The actual
vectorized computation lives in :mod:`trade_advisor.backtest.vectorized`;
``run_backtest()`` is a thin backward-compatible wrapper that delegates to
:func:`run_vectorized_backtest`.

Model assumptions (shared by both entry points):
- Daily bars; signals at bar close, executed at same bar's close (conservative
  for daily swing strategies since signal itself is already shifted by 1).
- Costs charged on turnover: commission_pct * |delta_position| * price + slippage.
- No leverage, no fractional borrowing interest.
- Signals are treated as target weights in constant-weight rebalancing.
- The engine does NOT add its own shift — the strategy is responsible for
  lookahead protection via ``shift(1)``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from trade_advisor.config import BacktestConfig
from trade_advisor.strategies.interface import Strategy  # noqa: F401 — AC-4: Protocol import


@dataclass
class BacktestResult:
    equity: pd.Series
    returns: pd.Series
    positions: pd.Series
    trades: pd.DataFrame
    config: BacktestConfig
    meta: dict = field(default_factory=dict)

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "equity": self.equity,
                "returns": self.returns,
                "position": self.positions,
            }
        )


def run_backtest(
    ohlcv: pd.DataFrame,
    signal: pd.Series,
    config: BacktestConfig | None = None,
) -> BacktestResult:
    """Run a simple vectorized backtest (backward-compatible wrapper).

    Delegates to :func:`run_vectorized_backtest` from
    :mod:`trade_advisor.backtest.vectorized`.

    ``signal`` values must be in ``[-1.0, +1.0]`` and must already be
    lookahead-safe (i.e., the strategy has shifted them).
    """
    from trade_advisor.backtest.vectorized import run_vectorized_backtest

    return run_vectorized_backtest(ohlcv, signal, config)


def _extract_trades(pos: pd.Series, price: pd.Series) -> pd.DataFrame:
    """Extract trade records from a position series.

    For continuous float signals, ``weight`` captures the mean absolute
    position held during the trade.  For discrete ``{-1, 0, +1}`` signals
    the weight is always ``1.0``.
    """
    if pos.empty:
        return pd.DataFrame(
            columns=[
                "entry_ts",
                "exit_ts",
                "side",
                "entry_price",
                "exit_price",
                "return",
                "weight",
            ]
        )

    records: list[dict] = []
    current_side: int = 0
    entry_ts = None
    entry_price = np.nan
    weight_accum: list[float] = []

    for ts, new_pos in pos.items():
        new_side = int(np.sign(new_pos))
        if new_side == current_side:
            if current_side != 0:
                weight_accum.append(abs(float(new_pos)))
            continue
        if current_side != 0 and entry_ts is not None:
            exit_px = float(price.at[ts])
            ret = (exit_px / entry_price - 1.0) * current_side
            avg_weight = sum(weight_accum) / len(weight_accum) if weight_accum else 1.0
            records.append(
                {
                    "entry_ts": entry_ts,
                    "exit_ts": ts,
                    "side": current_side,
                    "entry_price": entry_price,
                    "exit_price": exit_px,
                    "return": ret,
                    "weight": avg_weight,
                }
            )
        if new_side != 0:
            entry_ts = ts
            entry_price = float(price.at[ts])
            weight_accum = [abs(float(new_pos))]
        else:
            entry_ts = None
            entry_price = np.nan
            weight_accum = []
        current_side = new_side

    return pd.DataFrame.from_records(
        records,
        columns=[
            "entry_ts",
            "exit_ts",
            "side",
            "entry_price",
            "exit_price",
            "return",
            "weight",
        ],
    )
