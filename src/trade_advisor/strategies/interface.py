"""Protocol-based Strategy interface for structural typing.

This module defines the canonical Strategy contract using ``typing.Protocol``
so that any class with matching method signatures satisfies the interface
without explicit inheritance.  Static type-checking (mypy) verifies
signatures; ``@runtime_checkable`` enables ``isinstance()`` guards at
wire-up time.

Signal contract
---------------
``generate_signals`` returns a ``pd.Series[float]`` whose values lie in
``[-1.0, +1.0]``.  The discrete set ``{-1, 0, +1}`` is the Phase 1
subset; future ML strategies (SE-2) may emit continuous values.

**Lookahead prohibition:** signals must use ONLY data at or before each
timestamp.  Any lookahead is a defect.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class Strategy(Protocol):
    """Structural interface for trading strategies.

    Implementations must provide:

    - ``name`` — human-readable strategy identifier
    - ``information_latency`` — bars of minimum data delay (SE-5)
    - ``warmup_period`` — bars required before signals are valid
    - ``generate_signals`` — produces a signal Series from OHLCV data
    """

    name: str

    @property
    def information_latency(self) -> int:
        """Minimum data delay in bars (SE-5).

        Number of bars between the latest available observation and the
        current bar for which a signal is produced.  A value of 0 means
        the strategy sees data up to the current bar (no additional
        latency beyond what the data source itself introduces).
        """
        ...

    @property
    def warmup_period(self) -> int:
        """Bars required before signals are statistically valid.

        Signals produced before ``warmup_period`` bars are unreliable
        and should be treated as neutral (0) by consumers.
        """
        ...

    def generate_signals(self, ohlcv: pd.DataFrame) -> pd.Series:
        """Return a ``pd.Series[float]`` of signals in [-1.0, +1.0].

        Signals must use ONLY data at or before each timestamp.
        Any lookahead is a defect.

        Parameters
        ----------
        ohlcv : pd.DataFrame
            OHLCV price data with columns including ``close`` or
            ``adj_close``.

        Returns
        -------
        pd.Series
            Signal values aligned with ``ohlcv`` index.
        """
        ...
