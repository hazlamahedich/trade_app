"""Optimized vectorized backtest engine.

This module provides ``run_vectorized_backtest`` — a fast, deterministic,
pure NumPy/Pandas backtest engine for single-asset strategies.

Return convention
-----------------
Signals are treated as **target weights** in constant-weight rebalancing.
``strategy_ret[t] = signal[t] * asset_ret[t] - cost_drag[t]`` means each bar
the position is implicitly rebalanced to maintain the signal as a fraction of
equity.  This is NOT constant-shares / buy-and-hold sizing.

Cost model
----------
Costs are applied via ``CostEngine`` (Story 2.6).  The vectorized path uses a
constant ``effective_cost_pct`` derived from the engine's fixed and bps
components.  ATR-varying slippage is applied only in the event-driven path.

Determinism
-----------
The computation is purely deterministic from inputs — no internal randomness,
no thread scheduling dependency, no hash ordering.  Same inputs always produce
bitwise-identical ``BacktestResult``.

Execution model
---------------
Signal at bar T is used to compute the position held during bar T, earning
bar T's return.  The strategy is responsible for shifting signals by 1 bar
(via ``shift(1)``) to prevent lookahead bias.  The engine does NOT add its
own shift.

Float64 precision
-----------------
Internally the engine operates in ``float64``.  ``BacktestConfig.initial_cash``
is ``DecimalStr`` but converts to ``float`` at the engine boundary.  This is
the sanctioned I/O edge per the project Decimal convention.
"""

from __future__ import annotations

import pandas as pd

from trade_advisor.backtest._equity import compute_equity_curve
from trade_advisor.backtest.costs import CostEngine
from trade_advisor.backtest.engine import BacktestResult, _extract_trades
from trade_advisor.config import BacktestConfig


class VectorizedEngine:
    """Structural ``BacktestEngine`` adapter — delegates to :func:`run_vectorized_backtest`.

    Satisfies the ``BacktestEngine`` Protocol via structural subtyping::

        isinstance(VectorizedEngine(), BacktestEngine)  # True
    """

    def run(
        self,
        ohlcv: pd.DataFrame,
        signal: pd.Series,
        config: BacktestConfig | None = None,
    ) -> BacktestResult:
        return run_vectorized_backtest(ohlcv, signal, config)


def run_vectorized_backtest(
    ohlcv: pd.DataFrame,
    signal: pd.Series,
    config: BacktestConfig | None = None,
    sizing: object | None = None,
) -> BacktestResult:
    """Run a vectorized backtest on single-asset OHLCV data.

    Parameters
    ----------
    ohlcv : pd.DataFrame
        OHLCV bar data with ``close`` (or ``adj_close``) and ``timestamp``
        columns.
    signal : pd.Series
        Pre-shifted signal series in ``[-1.0, +1.0]``.  The strategy is
        responsible for lookahead protection (shift by 1 bar).
    config : BacktestConfig | None
        Backtest configuration.  Defaults constructed if ``None``.
    sizing : object | None
        Position sizing integration point (deferred).  When ``None``,
        positions equal signal values directly.

    Returns
    -------
    BacktestResult
        Equity curve, trade list, portfolio states.

    Raises
    ------
    ValueError
        If signal contains values outside ``[-1.0, +1.0]``.
    """
    cfg = config or BacktestConfig()  # type: ignore[call-arg]

    if len(ohlcv) == 0:
        return BacktestResult(
            equity=pd.Series(dtype="float64", name="equity"),
            returns=pd.Series(dtype="float64", name="returns"),
            positions=pd.Series(dtype="float64", name="position"),
            trades=_extract_trades(
                pd.Series(dtype="float64", name="position"),
                pd.Series(dtype="float64"),
            ),
            config=cfg,
            meta={"bars": 0, "n_trades": 0},
        )

    if "timestamp" not in ohlcv.columns:
        raise ValueError("OHLCV DataFrame must contain a 'timestamp' column")

    if "adj_close" in ohlcv.columns:
        price = ohlcv["adj_close"].astype("float64")
    elif "close" in ohlcv.columns:
        price = ohlcv["close"].astype("float64")
    else:
        raise ValueError("OHLCV DataFrame must contain 'close' or 'adj_close' column")

    ts = pd.to_datetime(ohlcv["timestamp"])
    price.index = ts
    sig = signal.copy()
    sig.index = ts
    sig = sig.reindex(price.index).fillna(0.0).astype("float64")

    _sig_min = float(sig.min())
    _sig_max = float(sig.max())
    if _sig_min < -1.0 or _sig_max > 1.0:
        raise ValueError(
            f"Signal values must be in [-1.0, +1.0]; got range [{_sig_min}, {_sig_max}]"
        )

    asset_ret = price.pct_change().fillna(0.0)
    cost_engine = CostEngine.from_model(cfg.cost)

    equity, strategy_ret, pos = compute_equity_curve(
        signal=sig,
        asset_ret=asset_ret,
        initial_cash=float(cfg.initial_cash),
        cost_engine=cost_engine,
        strict=cfg.strict,
    )

    trades = _extract_trades(pos, price)

    return BacktestResult(
        equity=equity,
        returns=strategy_ret,
        positions=pos,
        trades=trades,
        config=cfg,
        meta={"bars": len(price), "n_trades": len(trades)},
    )
