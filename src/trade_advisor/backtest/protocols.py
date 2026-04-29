"""Backtest engine protocol contracts.

Defines the ``BacktestEngine`` Protocol shared by both the vectorized engine
(Story 2.3) and the future event-driven engine (Story 2.4).

Both engines satisfy the Protocol via structural subtyping — no inheritance
required.  The Protocol takes batch ``pd.DataFrame`` input; the event-driven
engine wraps that internally in its own bar-by-bar iterator.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import pandas as pd

from trade_advisor.backtest.engine import BacktestResult
from trade_advisor.config import BacktestConfig


@runtime_checkable
class BacktestEngine(Protocol):
    """Structural protocol for backtest engines.

    Method contract
    ---------------
    - ``ohlcv``: OHLCV bar data with at minimum a ``close`` column and a
      ``timestamp`` column (or DatetimeIndex).
    - ``signal``: pre-shifted signal series in ``[-1.0, +1.0]``.  The strategy
      is responsible for lookahead protection (shift by 1 bar).  The engine
      does NOT add its own shift.
    - ``config``: optional ``BacktestConfig``; defaults constructed if ``None``.

    Return convention
    -----------------
    - ``BacktestResult`` with equity curve, trade list, portfolio states.
    - Signals are treated as **target weights** — constant-weight rebalancing:
      each bar the position is implicitly rebalanced to maintain the signal
      as a fraction of equity.
    """

    def run(
        self,
        ohlcv: pd.DataFrame,
        signal: pd.Series,
        config: BacktestConfig | None = None,
    ) -> BacktestResult: ...
