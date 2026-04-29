"""Trade-level analysis: holding period, MFE, MAE, distributions."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

import numpy as np
import pandas as pd

from trade_advisor.backtest.engine import BacktestResult
from trade_advisor.core.types import from_float

_QUANT = Decimal("0.0000000001")


def _q(v: float) -> Decimal:
    if not np.isfinite(v):
        return Decimal("0")
    return from_float(v).quantize(_QUANT, rounding=ROUND_HALF_EVEN)


@dataclass
class TradeAnalysis:
    __hash__ = None  # type: ignore[assignment]

    avg_holding_period: float
    avg_mfe: Decimal
    avg_mae: Decimal
    entry_return_dist: pd.Series
    exit_return_dist: pd.Series


def _empty_analysis() -> TradeAnalysis:
    return TradeAnalysis(
        avg_holding_period=0.0,
        avg_mfe=Decimal("0"),
        avg_mae=Decimal("0"),
        entry_return_dist=pd.Series(dtype=float),
        exit_return_dist=pd.Series(dtype=float),
    )


def compute_trade_analysis(result: BacktestResult) -> TradeAnalysis:
    trades = result.trades

    if trades.empty:
        return _empty_analysis()

    equity = result.equity
    holding_periods: list[float] = []
    mfes: list[float] = []
    maes: list[float] = []
    entry_returns: list[float] = []
    exit_returns: list[float] = []

    for _, trade in trades.iterrows():
        entry_ts = trade["entry_ts"]
        exit_ts = trade["exit_ts"]
        side = int(trade["side"])

        entry_idx = equity.index.get_indexer(pd.Index([entry_ts]), method="nearest")[0]
        exit_idx = equity.index.get_indexer(pd.Index([exit_ts]), method="nearest")[0]
        if entry_idx < 0 or exit_idx < 0:
            continue

        if entry_idx >= exit_idx:
            holding_periods.append(0.0)
        else:
            holding_periods.append(float(exit_idx - entry_idx))

        equity_slice = equity.iloc[entry_idx : exit_idx + 1]
        if equity_slice.empty:
            mfes.append(0.0)
            maes.append(0.0)
            entry_returns.append(0.0)
            exit_returns.append(float(trade["return"]))
            continue

        entry_equity = float(equity.iloc[entry_idx])
        if entry_equity == 0:
            mfes.append(0.0)
            maes.append(0.0)
            entry_returns.append(0.0)
            exit_returns.append(float(trade["return"]))
            continue

        ratios = np.asarray(equity_slice.values, dtype=float) / entry_equity

        if side == 1:
            mfe = float(np.max(ratios)) - 1.0
            mae = float(np.min(ratios)) - 1.0
        elif side == -1:
            mfe = 1.0 - float(np.min(ratios))
            mae = 1.0 - float(np.max(ratios))
        else:
            mfe = 0.0
            mae = 0.0

        mfes.append(mfe)
        maes.append(mae)

        if len(equity_slice) >= 2:
            entry_returns.append(float(equity_slice.iloc[1] / equity_slice.iloc[0]) - 1.0)
        else:
            entry_returns.append(0.0)
        exit_returns.append(float(trade["return"]))

    if not holding_periods:
        return _empty_analysis()

    avg_holding = sum(holding_periods) / len(holding_periods)
    avg_mfe = _q(sum(mfes) / len(mfes)) if mfes else Decimal("0")
    avg_mae = _q(sum(maes) / len(maes)) if maes else Decimal("0")

    return TradeAnalysis(
        avg_holding_period=avg_holding,
        avg_mfe=avg_mfe,
        avg_mae=avg_mae,
        entry_return_dist=pd.Series(entry_returns, dtype=float),
        exit_return_dist=pd.Series(exit_returns, dtype=float),
    )
