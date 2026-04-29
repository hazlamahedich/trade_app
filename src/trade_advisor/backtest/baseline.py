"""Buy-and-hold baseline comparison and composite :class:`BaselineComparison`.

Runs the strategy and a constant-long (``signal=1.0``) buy-and-hold benchmark
through the **same** vectorized engine with the **same** ``BacktestConfig``,
guaranteeing cost parity and return-convention parity.

Also computes relative metrics (alpha, beta, information ratio) by comparing
strategy returns against benchmark returns, replacing the NaN stubs left by
:mod:`trade_advisor.backtest.metrics.performance`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from trade_advisor.backtest.integrity import IntegrityResult, check_integrity
from trade_advisor.backtest.metrics.performance import compute_performance_metrics

if TYPE_CHECKING:
    from trade_advisor.backtest.engine import BacktestResult
    from trade_advisor.backtest.metrics.performance import PerformanceMetrics
    from trade_advisor.backtest.regime import RegimeStratification
    from trade_advisor.config import BacktestConfig


def compute_relative_metrics(
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
    ann: float,
) -> tuple[float, float, float]:
    s, b = strategy_returns.align(benchmark_returns, join="inner")
    combined = pd.DataFrame({"s": s, "b": b}).dropna()
    s = combined["s"]
    b = combined["b"]
    if len(s) < 2:
        return (float("nan"), float("nan"), float("nan"))

    cov_mat = np.cov(s.values, b.values, ddof=1)
    beta = float(cov_mat[0, 1] / cov_mat[1, 1]) if cov_mat[1, 1] != 0 else float("nan")

    mean_s = float(s.mean())
    mean_b = float(b.mean())

    alpha = (mean_s - beta * mean_b) * ann**2 if np.isfinite(beta) else float("nan")

    diff = (s - b).values
    daily_te = float(np.std(diff, ddof=1))
    information_ratio = (mean_s - mean_b) * ann / daily_te if daily_te > 0 else 0.0

    return (float(alpha), float(beta), float(information_ratio))


@dataclass
class BaselineComparison:
    strategy_result: BacktestResult
    buy_and_hold_result: BacktestResult
    strategy_metrics: PerformanceMetrics
    buy_and_hold_metrics: PerformanceMetrics
    integrity: IntegrityResult
    is_label: str
    sample_type: str
    regime: RegimeStratification | None = None


def run_buy_and_hold(
    ohlcv: pd.DataFrame,
    config: BacktestConfig,
) -> BacktestResult:
    from trade_advisor.backtest.vectorized import run_vectorized_backtest

    signal = pd.Series(1.0, index=ohlcv.index)
    signal.name = "signal"
    return run_vectorized_backtest(ohlcv, signal, config)


def _signal_entropy(signals: pd.Series) -> float:
    vc = signals.value_counts(normalize=True)
    probs = vc.values
    entropy = abs(float(np.sum(probs * np.log(probs))))
    max_entropy = float(np.log(len(probs))) if len(probs) > 1 else 1.0
    return entropy / max_entropy if max_entropy > 0 else 0.0


def compute_with_baseline(
    ohlcv: pd.DataFrame,
    signals: pd.Series,
    config: BacktestConfig,
) -> BaselineComparison:
    from trade_advisor.backtest.metrics._helpers import _annualization_factor
    from trade_advisor.backtest.vectorized import run_vectorized_backtest

    strategy_result = run_vectorized_backtest(ohlcv, signals, config)
    buy_hold_result = run_buy_and_hold(ohlcv, config)

    strategy_metrics = compute_performance_metrics(strategy_result)
    buy_hold_metrics = compute_performance_metrics(buy_hold_result)

    ann = _annualization_factor(config)
    alpha, beta, ir = compute_relative_metrics(
        strategy_result.returns, buy_hold_result.returns, ann
    )
    strategy_metrics.alpha = alpha
    strategy_metrics.beta = beta
    strategy_metrics.information_ratio = ir

    signal_entropy = _signal_entropy(signals)

    integrity = check_integrity(
        strategy_result.equity,
        trade_count=len(strategy_result.trades),
        signal_entropy=signal_entropy,
        sharpe=strategy_metrics.sharpe,
    )

    regime: RegimeStratification | None = None
    if len(ohlcv) >= 60:
        try:
            from trade_advisor.backtest.regime import stratify_by_regime

            regime = stratify_by_regime(ohlcv, signals)
        except Exception as exc:
            logging.warning("Regime stratification failed: %s", exc)
            regime = None

    return BaselineComparison(
        strategy_result=strategy_result,
        buy_and_hold_result=buy_hold_result,
        strategy_metrics=strategy_metrics,
        buy_and_hold_metrics=buy_hold_metrics,
        integrity=integrity,
        is_label="In-Sample Only — not validated for live trading",
        sample_type="in_sample",
        regime=regime,
    )
