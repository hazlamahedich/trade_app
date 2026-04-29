"""Shared equity curve computation — structural convergence guarantee.

Both the vectorized engine and the event-driven engine call this same function
to produce their equity curves.  This STRUCTURALLY guarantees convergence
under zero-cost, market-orders-only conditions rather than hoping for it
empirically.

Formula
-------
``strategy_ret[t] = signal[t] * asset_ret[t] - cost_drag[t]``
``equity[t]      = cumprod(1 + strategy_ret) * initial_cash``
"""

from __future__ import annotations

import warnings

import pandas as pd


def compute_equity_curve(
    signal: pd.Series,
    asset_ret: pd.Series,
    cost_pct: float,
    initial_cash: float,
    *,
    strict: bool = True,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Compute equity curve from signal and asset returns.

    Parameters
    ----------
    signal : pd.Series
        Pre-shifted signal series in ``[-1.0, +1.0]``.
    asset_ret : pd.Series
        Asset returns (``pct_change().fillna(0.0)``).
    cost_pct : float
        One-way cost as fraction of traded notional (``commission + slippage``).
    initial_cash : float
        Starting capital.
    strict : bool
        If True, raise on NaN in equity. If False, forward-fill and warn.

    Returns
    -------
    tuple[equity, returns, positions]
        Equity curve, strategy returns, and position series.
    """
    pos = signal.copy()

    nan_count = int(pos.isna().sum())
    if nan_count > 0:
        raise ValueError(f"signal contains {nan_count} NaN value(s); fill or drop before computing")

    sig_min = float(pos.min())
    sig_max = float(pos.max())
    if sig_min < -1.0 or sig_max > 1.0:
        raise ValueError(f"Signal range [{sig_min}, {sig_max}] outside [-1.0, +1.0]")

    delta = pos.diff().abs().fillna(pos.abs())
    cost_drag = delta * cost_pct

    strategy_ret = pos * asset_ret - cost_drag

    equity = (1.0 + strategy_ret).cumprod() * initial_cash
    equity.name = "equity"

    nan_mask = equity.isna()
    if nan_mask.any():
        nan_idx = equity.index[nan_mask].tolist()
        if strict:
            raise ValueError(
                f"Equity curve contains NaN at {nan_idx[:10]}{'...' if len(nan_idx) > 10 else ''}. "
                f"Check for NaN prices or zero-price bars in input data."
            )
        equity = equity.ffill().fillna(initial_cash)
        warnings.warn(
            f"Equity curve had {len(nan_idx)} NaN value(s) forward-filled. "
            f"First NaN at index {nan_idx[0]}. Set strict=False to suppress.",
            RuntimeWarning,
            stacklevel=2,
        )

    return equity, strategy_ret.rename("returns"), pos.rename("position")
