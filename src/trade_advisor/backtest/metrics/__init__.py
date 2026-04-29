"""Backtest metrics package — performance, risk, and trade-level analysis."""

from __future__ import annotations

from dataclasses import dataclass

from trade_advisor.backtest.engine import BacktestResult
from trade_advisor.backtest.metrics.performance import (
    PerformanceMetrics,
    compute_performance_metrics,
)
from trade_advisor.backtest.metrics.risk import (
    RiskMetrics,
    compute_risk_metrics,
)
from trade_advisor.backtest.metrics.trade_analysis import (
    TradeAnalysis,
    compute_trade_analysis,
)


@dataclass
class MetricsBundle:
    __hash__ = None  # type: ignore[assignment]

    performance: PerformanceMetrics
    risk: RiskMetrics
    trade_analysis: TradeAnalysis


def compute_all_metrics(result: BacktestResult) -> MetricsBundle:
    return MetricsBundle(
        performance=compute_performance_metrics(result),
        risk=compute_risk_metrics(result),
        trade_analysis=compute_trade_analysis(result),
    )


__all__ = [
    "MetricsBundle",
    "PerformanceMetrics",
    "RiskMetrics",
    "TradeAnalysis",
    "compute_all_metrics",
    "compute_performance_metrics",
    "compute_risk_metrics",
    "compute_trade_analysis",
]
