"""End-to-end backtest smoke test using synthetic data.

This is the closest thing to an integration test for Phase 1 that does not
require a network connection.
"""

from __future__ import annotations

import pandas as pd

from trade_advisor.backtest.engine import run_backtest
from trade_advisor.config import BacktestConfig, CostModel
from trade_advisor.evaluation.metrics import compute_metrics
from trade_advisor.strategies.sma_cross import SmaCross


def test_full_pipeline_runs(synthetic_ohlcv):
    strat = SmaCross(fast=10, slow=30)
    sig = strat.generate_signals(synthetic_ohlcv)
    result = run_backtest(synthetic_ohlcv, sig, BacktestConfig())

    assert len(result.equity) == len(synthetic_ohlcv)
    assert result.equity.iloc[0] > 0
    assert isinstance(result.trades, pd.DataFrame)

    metrics = compute_metrics(result.returns)
    assert -1.0 < metrics.max_drawdown <= 0
    assert metrics.n_bars == len(synthetic_ohlcv)


def test_flat_signal_gives_flat_equity(synthetic_ohlcv):
    """Zero signal should produce equity == initial cash all the way through."""
    flat = pd.Series(0, index=range(len(synthetic_ohlcv)), dtype="int8", name="signal")
    cfg = BacktestConfig(initial_cash=100_000.0)
    result = run_backtest(synthetic_ohlcv, flat, cfg)

    assert (result.equity == cfg.initial_cash).all()
    assert result.trades.empty


def test_costs_reduce_return(synthetic_ohlcv):
    strat = SmaCross(fast=5, slow=20)
    sig = strat.generate_signals(synthetic_ohlcv)

    no_cost = run_backtest(
        synthetic_ohlcv, sig, BacktestConfig(cost=CostModel(commission_pct=0, slippage_pct=0))
    )
    with_cost = run_backtest(
        synthetic_ohlcv,
        sig,
        BacktestConfig(cost=CostModel(commission_pct=0.001, slippage_pct=0.001)),
    )
    assert with_cost.equity.iloc[-1] <= no_cost.equity.iloc[-1]
