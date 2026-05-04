"""Hypothesis-driven convergence tests: vectorized vs event-driven engine.

Fuzzes across random price paths and signal patterns to verify engine parity
under diverse conditions. Tier 1 strict convergence (zero-cost, market-at-close).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from tests.helpers import _synthetic_ohlcv
from trade_advisor.backtest.engine import run_backtest
from trade_advisor.backtest.event_driven import EventDrivenEngine
from trade_advisor.config import BacktestConfig, CostModel

_zero_cost = BacktestConfig(
    initial_cash="100000", cost=CostModel(commission_pct=0.0, slippage_pct=0.0)
)


@st.composite
def signal_series(draw: st.DrawFn, length: int) -> np.ndarray:
    raw = draw(
        arrays(
            dtype=np.float64,
            shape=length,
            elements=st.floats(
                min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False
            ),
        )
    )
    return raw


@st.composite
def block_signal(draw: st.DrawFn, length: int) -> np.ndarray:
    n_blocks = draw(st.integers(min_value=1, max_value=min(10, length // 5 + 1)))
    rng = np.random.default_rng(draw(st.integers(min_value=0, max_value=2**31 - 1)))
    boundaries = sorted(
        rng.choice(range(1, length), size=min(n_blocks - 1, length - 2), replace=False)
    )
    boundaries = [0, *list(boundaries), length]
    levels = rng.choice([-1.0, 0.0, 1.0], size=len(boundaries) - 1)
    sig = np.zeros(length, dtype=np.float64)
    for i, level in enumerate(levels):
        sig[boundaries[i] : boundaries[i + 1]] = level
    return sig


@st.composite
def ohlcv_and_signal(draw: st.DrawFn):
    n_bars = draw(st.integers(min_value=50, max_value=300))
    seed = draw(st.integers(min_value=0, max_value=2**31 - 1))
    trend = draw(st.floats(min_value=-0.002, max_value=0.002))
    vol = draw(st.floats(min_value=0.005, max_value=0.04))
    ohlcv = _synthetic_ohlcv(n=n_bars, seed=seed, trend=trend, vol=vol)
    sig_arr = draw(st.one_of(signal_series(n_bars), block_signal(n_bars)))
    signal = pd.Series(sig_arr, dtype="float64", name="signal")
    return ohlcv, signal


@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(data=ohlcv_and_signal())
@pytest.mark.test_id("2.4-HYP-001")
@pytest.mark.p0
@pytest.mark.convergence
def test_hypothesis_convergence(data: tuple[pd.DataFrame, pd.Series]):
    ohlcv, signal = data
    vec_result = run_backtest(ohlcv, signal, _zero_cost)
    ed_engine = EventDrivenEngine(_zero_cost)
    ed_result = ed_engine.run(ohlcv, signal)

    np.testing.assert_allclose(
        vec_result.equity.values,
        ed_result.equity.values,
        atol=1e-10,
        rtol=1e-8,
    )
    assert len(vec_result.trades) == len(ed_result.trades)


@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(data=ohlcv_and_signal())
@pytest.mark.test_id("2.4-HYP-002")
@pytest.mark.p1
@pytest.mark.convergence
def test_hypothesis_returns_shape_match(data: tuple[pd.DataFrame, pd.Series]):
    ohlcv, signal = data
    vec_result = run_backtest(ohlcv, signal, _zero_cost)
    ed_result = ed_engine = EventDrivenEngine(_zero_cost)
    ed_result = ed_engine.run(ohlcv, signal)

    assert len(vec_result.returns) == len(ed_result.returns)
    assert len(vec_result.positions) == len(ed_result.positions)
    assert vec_result.equity.index.equals(ed_result.equity.index)


@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(data=ohlcv_and_signal())
@pytest.mark.test_id("2.4-HYP-003")
@pytest.mark.p1
@pytest.mark.convergence
def test_hypothesis_position_values_match(data: tuple[pd.DataFrame, pd.Series]):
    ohlcv, signal = data
    vec_result = run_backtest(ohlcv, signal, _zero_cost)
    ed_engine = EventDrivenEngine(_zero_cost)
    ed_result = ed_engine.run(ohlcv, signal)

    np.testing.assert_allclose(
        vec_result.positions.values,
        ed_result.positions.values,
        atol=1e-10,
        rtol=1e-8,
    )
