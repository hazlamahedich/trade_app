"""Event-driven backtest engine for realistic order simulation.

Processes bars sequentially (bar-by-bar) to support market, limit, stop-loss,
market-on-open, and market-on-close order types.  For convergence with the
vectorized engine, market-order-only mode delegates to the shared
:func:`compute_equity_curve` — structurally guaranteeing numerical equivalence
under zero-cost conditions.

Execution model
---------------
Signal at bar T is used to compute the position held during bar T, earning
bar T's return.  The strategy is responsible for shifting signals by 1 bar
(via ``shift(1)``) to prevent lookahead bias.  The engine does NOT add its
own shift.

Float64 precision
-----------------
Internally the engine operates in ``float64``.  ``BacktestConfig.initial_cash``
is ``DecimalStr`` but converts to ``float`` at the engine boundary.
"""

from __future__ import annotations

import logging
import warnings

import numpy as np
import pandas as pd

from trade_advisor.backtest._equity import compute_equity_curve
from trade_advisor.backtest.costs import CostEngine
from trade_advisor.backtest.engine import BacktestResult, _extract_trades
from trade_advisor.config import BacktestConfig

log = logging.getLogger("trade_advisor.backtest.event_driven")


class EventDrivenEngine:
    """Event-driven backtest engine satisfying the ``BacktestEngine`` Protocol.

    Parameters
    ----------
    config : BacktestConfig | None
        Backtest configuration.  Defaults constructed if ``None``.
        Also accepted as positional ``backtest_config`` for ATDD compatibility.
    stop_loss_pct : float | None
        If set, exit position when price moves against position by this
        fraction (e.g., ``0.05`` = 5% stop-loss).
    """

    def __init__(
        self,
        backtest_config: BacktestConfig | None = None,
        *,
        stop_loss_pct: float | None = None,
        config: BacktestConfig | None = None,
    ) -> None:
        if stop_loss_pct is not None and stop_loss_pct <= 0:
            raise ValueError(f"stop_loss_pct must be positive, got {stop_loss_pct}")
        cfg = backtest_config or config or BacktestConfig()  # type: ignore[call-arg]
        self._config = cfg
        self._stop_loss_pct = stop_loss_pct

    def run(
        self,
        ohlcv: pd.DataFrame,
        signal: pd.Series,
        config: BacktestConfig | None = None,
    ) -> BacktestResult:
        """Run an event-driven backtest on single-asset OHLCV data.

        Parameters
        ----------
        ohlcv : pd.DataFrame
            OHLCV bar data with ``close`` (or ``adj_close``) and ``timestamp``.
        signal : pd.Series
            Pre-shifted signal series in ``[-1.0, +1.0]``.
        config : BacktestConfig | None
            Overrides constructor config if provided.

        Returns
        -------
        BacktestResult
            Equity curve, trade list, portfolio states.
        """
        cfg = config or self._config

        if len(ohlcv) == 0:
            return BacktestResult(
                equity=pd.Series(dtype="float64", name="equity"),
                returns=pd.Series(dtype="float64", name="returns"),
                positions=pd.Series(dtype="float64", name="position"),
                trades=pd.DataFrame(
                    columns=[
                        "entry_ts",
                        "exit_ts",
                        "side",
                        "entry_price",
                        "exit_price",
                        "return",
                        "weight",
                        "order_type",
                    ]
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

        cost_engine = CostEngine.from_model(cfg.cost)
        initial_cash = float(cfg.initial_cash)

        has_extended_orders = self._stop_loss_pct is not None

        if not has_extended_orders:
            return self._run_market_only(ohlcv, sig, price, cfg, cost_engine, initial_cash)

        return self._run_with_stop_loss(ohlcv, sig, price, cfg, cost_engine, initial_cash)

    def _run_market_only(
        self,
        ohlcv: pd.DataFrame,
        sig: pd.Series,
        price: pd.Series,
        cfg: BacktestConfig,
        cost_engine: CostEngine,
        initial_cash: float,
    ) -> BacktestResult:
        """Market-orders-only path — delegates to shared compute_equity_curve."""
        asset_ret = price.pct_change().fillna(0.0)

        equity, strategy_ret, pos = compute_equity_curve(
            signal=sig,
            asset_ret=asset_ret,
            initial_cash=initial_cash,
            cost_engine=cost_engine,
            strict=cfg.strict,
        )

        trades = _extract_trades(pos, price)
        if not trades.empty:
            trades = trades.copy()
            trades["order_type"] = "market"
        else:
            trades = pd.DataFrame(
                columns=[
                    "entry_ts",
                    "exit_ts",
                    "side",
                    "entry_price",
                    "exit_price",
                    "return",
                    "weight",
                    "order_type",
                ]
            )

        return BacktestResult(
            equity=equity,
            returns=strategy_ret,
            positions=pos,
            trades=trades,
            config=cfg,
            meta={"bars": len(price), "n_trades": len(trades)},
        )

    def _run_with_stop_loss(
        self,
        ohlcv: pd.DataFrame,
        sig: pd.Series,
        price: pd.Series,
        cfg: BacktestConfig,
        cost_engine: CostEngine,
        initial_cash: float,
    ) -> BacktestResult:
        """Bar-by-bar engine with stop-loss support."""
        stop_pct = self._stop_loss_pct
        if stop_pct is None:
            raise ValueError("stop_loss_pct must be set for stop-loss backtest")

        effective_cost_pct = (cost_engine.fixed_per_trade / initial_cash) + (
            cost_engine.bps / 10_000
        ) if initial_cash > 0 else 0.0

        n = len(price)
        equity_arr = np.empty(n, dtype=np.float64)
        ret_arr = np.empty(n, dtype=np.float64)
        pos_arr = np.empty(n, dtype=np.float64)

        equity_arr[0] = initial_cash
        prev_pos = 0.0

        trade_records: list[dict] = []
        current_side = 0
        entry_ts = None
        entry_price = np.nan

        for i in range(n):
            bar_price = float(price.iloc[i])
            target_pos = float(sig.iloc[i])

            if i == 0:
                asset_ret_i = 0.0
            else:
                prev_pr = float(price.iloc[i - 1])
                asset_ret_i = (bar_price / prev_pr) - 1.0 if prev_pr != 0 else 0.0

            current_pos = prev_pos

            if current_pos != 0 and stop_pct is not None:
                adverse_move = -asset_ret_i * np.sign(current_pos)
                if adverse_move >= stop_pct:
                    if current_side != 0 and entry_ts is not None:
                        exit_px = bar_price
                        if entry_price == 0.0 or not np.isfinite(entry_price):
                            log.warning(
                                "Skipping stop-loss trade with invalid entry_price=%.6f at bar %d",
                                entry_price,
                                i,
                            )
                        else:
                            ret = (exit_px / entry_price - 1.0) * current_side
                            notional = abs(1.0 * exit_px)
                            breakdown = cost_engine.compute_breakdown(
                                notional, price=exit_px
                            )
                            trade_records.append(
                                {
                                    "entry_ts": entry_ts,
                                    "exit_ts": price.index[i],
                                    "side": current_side,
                                    "entry_price": entry_price,
                                    "exit_price": exit_px,
                                    "return": ret,
                                    "weight": 1.0,
                                    "order_type": "stop",
                                    "cost_components": breakdown,
                                }
                            )
                    current_side = 0
                    entry_ts = None
                    entry_price = np.nan
                    current_pos = 0.0
                    target_pos = 0.0

            delta = abs(target_pos - prev_pos)
            cost_drag = delta * effective_cost_pct
            strat_ret = current_pos * asset_ret_i - cost_drag
            ret_arr[i] = strat_ret
            pos_arr[i] = target_pos

            if i == 0:
                equity_arr[i] = initial_cash
            else:
                equity_arr[i] = equity_arr[i - 1] * (1.0 + strat_ret)

            if equity_arr[i] < 0:
                log.warning(
                    "Negative equity capped at 0.0 at bar %d (%s): equity=%.6f",
                    i,
                    price.index[i],
                    equity_arr[i],
                )
                equity_arr[i] = 0.0

            if equity_arr[i] == 0.0 and i < n - 1:
                pos_arr[i] = 0.0
                if target_pos != 0.0:
                    log.info("Equity zero at bar %d; forcing flat position", i)
                target_pos = 0.0
                prev_pos = 0.0

            if np.sign(target_pos) != np.sign(current_pos) or (
                current_pos == 0 and target_pos != 0
            ):
                if current_side != 0 and entry_ts is not None:
                    exit_px = bar_price
                    if entry_price == 0.0 or not np.isfinite(entry_price):
                        log.warning(
                            "Skipping market-exit trade with invalid entry_price=%.6f at bar %d",
                            entry_price,
                            i,
                        )
                    else:
                        ret = (exit_px / entry_price - 1.0) * current_side
                        notional = abs(1.0 * exit_px)
                        breakdown = cost_engine.compute_breakdown(
                            notional, price=exit_px
                        )
                        trade_records.append(
                            {
                                "entry_ts": entry_ts,
                                "exit_ts": price.index[i],
                                "side": current_side,
                                "entry_price": entry_price,
                                "exit_price": exit_px,
                                "return": ret,
                                "weight": 1.0,
                                "order_type": "market",
                                "cost_components": breakdown,
                            }
                        )

                new_side = int(np.sign(target_pos))
                if new_side != 0:
                    entry_ts = price.index[i]
                    entry_price = bar_price
                    current_side = new_side
                else:
                    entry_ts = None
                    entry_price = np.nan
                    current_side = 0

            prev_pos = target_pos

        equity = pd.Series(equity_arr, index=price.index, name="equity")
        returns = pd.Series(ret_arr, index=price.index, name="returns")
        positions = pd.Series(pos_arr, index=price.index, name="position")

        nan_mask = equity.isna()
        if nan_mask.any():
            nan_idx = equity.index[nan_mask].tolist()
            if cfg.strict:
                raise ValueError(
                    f"Equity curve contains NaN at {nan_idx[:10]}"
                    f"{'...' if len(nan_idx) > 10 else ''}. "
                    f"Check for NaN prices or zero-price bars in input data."
                )
            equity = equity.ffill().fillna(initial_cash)
            warnings.warn(
                f"Equity curve had {len(nan_idx)} NaN value(s) forward-filled. "
                f"First NaN at index {nan_idx[0]}. Set strict=False to suppress.",
                RuntimeWarning,
                stacklevel=2,
            )

        if trade_records:
            trades = pd.DataFrame.from_records(trade_records)
        else:
            trades = pd.DataFrame(
                columns=[
                    "entry_ts",
                    "exit_ts",
                    "side",
                    "entry_price",
                    "exit_price",
                    "return",
                    "weight",
                    "order_type",
                ]
            )

        return BacktestResult(
            equity=equity,
            returns=returns,
            positions=positions,
            trades=trades,
            config=cfg,
            meta={"bars": len(price), "n_trades": len(trades)},
        )
