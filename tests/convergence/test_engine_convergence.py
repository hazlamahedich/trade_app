"""Convergence tests: vectorized vs event-driven engine.

These tests verify that under zero-cost, market-orders-only conditions,
both engines produce numerically-equivalent results.

Tier 1 — Strict Convergence: market-at-close, zero-cost → numerically equivalent.
Uses np.testing.assert_allclose(atol=1e-12, rtol=1e-9) for float comparison.
Trade counts use exact equality.
"""

from __future__ import annotations

import numpy as np
import pytest

from trade_advisor.backtest.engine import run_backtest
from trade_advisor.backtest.event_driven import EventDrivenEngine


def _run_both(ohlcv, signal, zero_cost_config):
    vec_result = run_backtest(ohlcv, signal, zero_cost_config)
    ed_engine = EventDrivenEngine(zero_cost_config)
    ed_result = ed_engine.run(ohlcv, signal)
    return vec_result, ed_result


@pytest.mark.convergence
def test_convergence_flat_signal(ohlcv_500, flat_signal, zero_cost_config):
    vec_result, ed_result = _run_both(ohlcv_500, flat_signal, zero_cost_config)
    np.testing.assert_allclose(
        vec_result.equity.values,
        ed_result.equity.values,
        atol=1e-12,
        rtol=1e-9,
    )
    assert len(vec_result.trades) == len(ed_result.trades)


@pytest.mark.convergence
def test_convergence_sma_crossover(ohlcv_500, sma_crossover_signal, zero_cost_config):
    vec_result, ed_result = _run_both(ohlcv_500, sma_crossover_signal, zero_cost_config)
    np.testing.assert_allclose(
        vec_result.equity.values,
        ed_result.equity.values,
        atol=1e-12,
        rtol=1e-9,
    )
    assert len(vec_result.trades) == len(ed_result.trades)


@pytest.mark.convergence
def test_convergence_single_trade(ohlcv_500, single_long_signal, zero_cost_config):
    vec_result, ed_result = _run_both(ohlcv_500, single_long_signal, zero_cost_config)
    np.testing.assert_allclose(
        vec_result.equity.values,
        ed_result.equity.values,
        atol=1e-12,
        rtol=1e-9,
    )
    assert len(vec_result.trades) == len(ed_result.trades)


@pytest.mark.convergence
def test_convergence_signal_reversal(ohlcv_500, reversal_signal, zero_cost_config):
    vec_result, ed_result = _run_both(ohlcv_500, reversal_signal, zero_cost_config)
    np.testing.assert_allclose(
        vec_result.equity.values,
        ed_result.equity.values,
        atol=1e-12,
        rtol=1e-9,
    )
    assert len(vec_result.trades) == len(ed_result.trades)


@pytest.mark.convergence
def test_convergence_divergence_detected(ohlcv_500, sma_crossover_signal):
    from trade_advisor.config import BacktestConfig, CostModel

    zero_cfg = BacktestConfig(
        initial_cash="100000",
        cost=CostModel(commission_pct=0.0, slippage_pct=0.0),
    )
    cost_cfg = BacktestConfig(
        initial_cash="100000",
        cost=CostModel(commission_pct=0.001, slippage_pct=0.0005),
    )

    vec_result = run_backtest(ohlcv_500, sma_crossover_signal, cost_cfg)
    ed_engine = EventDrivenEngine(zero_cfg)
    ed_result = ed_engine.run(ohlcv_500, sma_crossover_signal)

    assert not np.allclose(
        vec_result.equity.values,
        ed_result.equity.values,
        atol=1e-12,
        rtol=1e-9,
    ), "Expected divergence when cost configs differ"
