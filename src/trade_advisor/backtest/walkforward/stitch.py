from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

from trade_advisor.backtest.walkforward.engine import (
    WalkForwardConfig,
    WalkForwardResult,
)


@dataclass(frozen=True)
class WFEThresholds:
    healthy_min: float = 0.7
    caution_min: float = 0.5


@dataclass
class StitchedOOSResult:
    stitched_equity: pd.Series
    total_oos_return: float
    total_is_return: float
    wfe: float
    wfe_status: Literal["healthy", "caution", "unreliable"]
    wfe_per_fold: list[float] = field(default_factory=list)
    baseline_equity: pd.Series = field(default_factory=lambda: pd.Series(dtype="float64"))
    expected_return_per_active_bar: float = 0.0
    n_active_bars_oos: int = 0
    window_0_oos_is_baseline: bool = False

    @property
    def expected_value_per_trade(self) -> float:
        return self.expected_return_per_active_bar

    @property
    def n_oos_trades(self) -> int:
        return self.n_active_bars_oos


def stitch_oos_equity(oos_segments: list[pd.Series], initial_cash: float = 100_000.0) -> pd.Series:
    """Stitch OOS segments into a continuous equity curve using compounded returns.

    This avoids the 'sawtooth' artifact where each segment resets to initial capital.
    """
    clean_segments = [s.dropna() for s in oos_segments if len(s) > 0]
    if not clean_segments:
        return pd.Series(dtype="float64")

    # Explicit cast to float to handle Decimal from config
    initial_cash_f = float(initial_cash)

    all_returns = []
    for s in clean_segments:
        # Each segment's first value is initial_cash * (1 + first_bar_ret)
        # So first_bar_ret = s.iloc[0] / initial_cash - 1
        first_ret = float(s.iloc[0]) / initial_cash_f - 1.0
        subsequent_rets = s.pct_change().dropna()
        segment_rets = pd.Series([first_ret, *subsequent_rets.values], index=s.index)
        all_returns.append(segment_rets)

    returns = pd.concat(all_returns).sort_index(kind="mergesort")

    # Handle duplicates by taking the first occurrence (preventing double-counting returns)
    if returns.index.has_duplicates:
        returns = returns[~returns.index.duplicated(keep="first")]

    # Compounded equity curve
    equity = (1.0 + returns).cumprod() * initial_cash_f
    return equity.rename("equity")



def compute_wfe(oos_return: float, is_return: float) -> float:
    if is_return == 0.0:
        return 0.0
    return oos_return / is_return


def wfe_status(
    wfe: float,
    thresholds: WFEThresholds | None = None,
    total_is_return: float = 0.0,
    total_oos_return: float = 0.0,
) -> Literal["healthy", "caution", "unreliable"]:
    if thresholds is None:
        thresholds = WFEThresholds()

    # AC-3: Negative WFE (OOS lost money while IS gained) -> unreliable
    # Also handle double-negative: if IS lost money, it's unreliable regardless of ratio
    if total_is_return <= 0 or total_oos_return < 0 or wfe < 0:
        return "unreliable"

    if wfe >= thresholds.healthy_min:
        return "healthy"
    if wfe >= thresholds.caution_min:
        return "caution"
    return "unreliable"


def _compound_returns(
    valid: list,
) -> tuple[float, float]:
    # Ensure we only compound finite values
    is_compound = math.prod(1.0 + w.is_return for w in valid if math.isfinite(w.is_return)) - 1.0
    oos_compound = math.prod(1.0 + w.oos_return for w in valid if math.isfinite(w.oos_return)) - 1.0
    return is_compound, oos_compound


def compute_wfe_from_result(
    result: WalkForwardResult,
    thresholds: WFEThresholds | None = None,
) -> tuple[float, Literal["healthy", "caution", "unreliable"], list[float], float, float]:
    valid = [w for w in result.windows if w.status == "OK"]
    if not valid:
        return 0.0, "unreliable", [], 0.0, 0.0

    is_compound, oos_compound = _compound_returns(valid)
    aggregate_wfe = compute_wfe(oos_compound, is_compound)
    status = wfe_status(aggregate_wfe, thresholds, is_compound, oos_compound)
    per_fold = [compute_wfe(w.oos_return, w.is_return) for w in valid]

    return aggregate_wfe, status, per_fold, is_compound, oos_compound


def compute_expected_value(trade_returns: list[float] | pd.Series) -> float:
    if isinstance(trade_returns, pd.Series):
        trade_returns = trade_returns.tolist()
    if not trade_returns:
        return 0.0
    # AC-6: Arithmetic mean of trade returns.
    # We MUST include 0.0 returns for statistical integrity if they are valid data points.
    clean = [v for v in trade_returns if math.isfinite(v)]
    if not clean:
        return 0.0
    return sum(clean) / len(clean)


def compute_oos_baseline(
    stitched_equity: pd.Series,
    ohlcv: pd.DataFrame,
    config: WalkForwardConfig,
) -> pd.Series:
    if len(stitched_equity) == 0:
        return pd.Series(dtype="float64")

    close_candidates = [c for c in ohlcv.columns if c.lower() == "close"]

    if not close_candidates:
        raise ValueError(f"No 'close' column in ohlcv: {list(ohlcv.columns)}")
    close_col = close_candidates[0]

    # Filter OHLCV to exactly the indices present in stitched_equity for precise comparison
    # This avoids including gap bars or IS periods in the baseline
    subset = ohlcv.loc[ohlcv.index.isin(stitched_equity.index), close_col]
    if len(subset) < 2:
        return pd.Series(dtype="float64")

    returns = subset.pct_change().dropna()
    cum = (1.0 + returns).cumprod()

    # AC-5: Baseline starts at 1.0 (relative).
    # To enable direct comparison with stitched_equity, we scale it by the initial equity value.
    initial_value = float(stitched_equity.iloc[0])
    baseline_values = [initial_value, *(cum * initial_value).tolist()]

    baseline = pd.Series(
        baseline_values,
        index=[subset.index[0], *list(cum.index)],
        dtype="float64",
    )
    return baseline.rename("baseline")


def _extract_active_bar_returns(stitched_equity: pd.Series) -> list[float]:
    """Extract per-bar returns from the stitched equity curve.

    Note: This returns bar-level returns, not discrete trade-level returns.
    We include 0.0 returns to avoid biasing the mean.
    """
    if len(stitched_equity) < 2:
        return []
    returns = stitched_equity.pct_change().dropna()
    return [float(r) for r in returns]


def build_stitched_result(
    result: WalkForwardResult,
    ohlcv: pd.DataFrame,
    thresholds: WFEThresholds | None = None,
) -> StitchedOOSResult:
    valid_windows = [w for w in result.windows if w.status == "OK"]

    # Use the initial_cash from the backtest config for proper re-compounding
    initial_cash = float(result.config.backtest.initial_cash)
    stitched_equity = stitch_oos_equity(
        [w.oos_equity for w in valid_windows], initial_cash=initial_cash
    )


    wfe, status, per_fold, is_compound, oos_compound = compute_wfe_from_result(
        result, thresholds
    )
    baseline_equity = compute_oos_baseline(stitched_equity, ohlcv, result.config)

    # Currently Story 4.4a approximates EV via per-bar returns.
    # Story 4.4b will invest in full signal-based trade reconstruction.
    active_bar_returns = _extract_active_bar_returns(stitched_equity)
    ev = compute_expected_value(active_bar_returns)

    return StitchedOOSResult(
        stitched_equity=stitched_equity,
        total_oos_return=oos_compound,
        total_is_return=is_compound,
        wfe=wfe,
        wfe_status=status,
        wfe_per_fold=per_fold,
        baseline_equity=baseline_equity,
        expected_return_per_active_bar=ev,
        n_active_bars_oos=len(active_bar_returns),
        window_0_oos_is_baseline=result.config.frozen_params_mode,
    )

