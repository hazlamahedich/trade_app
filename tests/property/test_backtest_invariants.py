"""Property-based tests for backtest result invariants.

Verifies structural properties that must hold for any BacktestResult
regardless of input data, signal pattern, or configuration.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tests.helpers import _synthetic_ohlcv
from trade_advisor.backtest.engine import run_backtest
from trade_advisor.config import BacktestConfig, CostModel


@st.composite
def backtest_scenario(draw: st.DrawFn):
    n_bars = draw(st.integers(min_value=20, max_value=500))
    seed = draw(st.integers(min_value=0, max_value=2**31 - 1))
    initial_cash = draw(st.sampled_from(["10000", "100000", "1000000"]))
    commission = draw(st.floats(min_value=0.0, max_value=0.01))
    slippage = draw(st.floats(min_value=0.0, max_value=0.005))
    strict_mode = draw(st.booleans())

    ohlcv = _synthetic_ohlcv(n=n_bars, seed=seed)
    rng = np.random.default_rng(seed)

    sig = rng.choice([-1.0, 0.0, 1.0], size=n_bars).astype(np.float64)
    n_flips = draw(st.integers(min_value=0, max_value=min(5, n_bars // 10)))
    flip_indices = rng.choice(range(5, n_bars), size=n_flips, replace=False)
    for idx in flip_indices:
        sig[idx:] = rng.choice([-1.0, 0.0, 1.0])

    signal = pd.Series(sig, dtype="float64", name="signal")

    config = BacktestConfig(
        initial_cash=initial_cash,
        cost=CostModel(commission_pct=commission, slippage_pct=slippage),
        strict=strict_mode,
    )

    return ohlcv, signal, config, float(initial_cash)


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(scenario=backtest_scenario())
@pytest.mark.test_id("BT-PROP-001")
@pytest.mark.p0
def test_equity_near_initial_cash_at_start(scenario: tuple):
    ohlcv, signal, config, initial_cash = scenario
    result = run_backtest(ohlcv, signal, config)
    if len(result.equity) == 0:
        pytest.skip("empty equity curve")
    max_first_bar_cost = (
        float(config.initial_cash)
        * (float(config.cost.commission_pct) + float(config.cost.slippage_pct))
        * 2.0
    )
    assert result.equity.iloc[0] == pytest.approx(
        initial_cash, abs=max(max_first_bar_cost, initial_cash * 0.05)
    )


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(scenario=backtest_scenario())
@pytest.mark.test_id("BT-PROP-002")
@pytest.mark.p0
def test_equity_never_negative_under_normal_mode(scenario: tuple):
    ohlcv, signal, config, _initial_cash = scenario
    if config.strict:
        pytest.skip("strict mode allows assertion on negative equity")
    result = run_backtest(ohlcv, signal, config)
    if len(result.equity) == 0:
        pytest.skip("empty equity curve")
    assert (result.equity >= -1e-6).all(), f"Negative equity found: min={result.equity.min()}"


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(scenario=backtest_scenario())
@pytest.mark.test_id("BT-PROP-003")
@pytest.mark.p0
def test_series_lengths_match_ohlcv(scenario: tuple):
    ohlcv, signal, config, _ = scenario
    result = run_backtest(ohlcv, signal, config)
    n = len(ohlcv)
    assert len(result.equity) == n
    assert len(result.returns) == n
    assert len(result.positions) == n


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(scenario=backtest_scenario())
@pytest.mark.test_id("BT-PROP-004")
@pytest.mark.p0
def test_positions_in_valid_range(scenario: tuple):
    ohlcv, signal, config, _ = scenario
    result = run_backtest(ohlcv, signal, config)
    assert (result.positions >= -1.0 - 1e-9).all()
    assert (result.positions <= 1.0 + 1e-9).all()


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(scenario=backtest_scenario())
@pytest.mark.test_id("BT-PROP-005")
@pytest.mark.p1
def test_flat_signal_preserves_capital(scenario: tuple):
    ohlcv, _signal, config, initial_cash = scenario
    n = len(ohlcv)
    flat = pd.Series(np.zeros(n), dtype="float64", name="signal")
    result = run_backtest(ohlcv, flat, config)
    if len(result.equity) == 0:
        pytest.skip("empty equity curve")
    assert result.equity.iloc[-1] == pytest.approx(initial_cash, rel=1e-6)
    assert len(result.trades) == 0


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(scenario=backtest_scenario())
@pytest.mark.test_id("BT-PROP-006")
@pytest.mark.p1
def test_zero_cost_no_slippage_equality(scenario: tuple):
    ohlcv, signal, config, _ = scenario
    zero_config = BacktestConfig(
        initial_cash=config.initial_cash,
        cost=CostModel(commission_pct=0.0, slippage_pct=0.0),
        strict=config.strict,
    )
    result = run_backtest(ohlcv, signal, zero_config)
    if len(result.equity) < 2:
        pytest.skip("too few bars")

    equity = result.equity.values
    manual_equity = np.zeros_like(equity)
    manual_equity[0] = equity[0]
    asset_ret = ohlcv["close"].astype(float).pct_change().fillna(0.0).values
    positions = result.positions.values
    for i in range(1, len(equity)):
        manual_equity[i] = manual_equity[i - 1] * (1.0 + positions[i] * asset_ret[i])

    np.testing.assert_allclose(equity, manual_equity, atol=1e-6, rtol=1e-6)


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(scenario=backtest_scenario())
@pytest.mark.test_id("BT-PROP-007")
@pytest.mark.p1
def test_equity_compound_from_returns(scenario: tuple):
    ohlcv, signal, config, initial_cash = scenario
    result = run_backtest(ohlcv, signal, config)
    if len(result.equity) < 2:
        pytest.skip("too few bars")

    equity = result.equity.values
    strategy_ret = result.returns.values
    reconstructed = np.empty_like(equity)
    reconstructed[0] = initial_cash * (1.0 + strategy_ret[0])
    for i in range(1, len(equity)):
        reconstructed[i] = reconstructed[i - 1] * (1.0 + strategy_ret[i])

    np.testing.assert_allclose(equity, reconstructed, atol=0.01, rtol=1e-4)


@settings(max_examples=80, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(scenario=backtest_scenario())
@pytest.mark.test_id("BT-PROP-008")
@pytest.mark.p1
def test_deterministic_same_seed_same_result(scenario: tuple):
    ohlcv, signal, config, _ = scenario
    result1 = run_backtest(ohlcv, signal, config)
    result2 = run_backtest(ohlcv, signal, config)

    np.testing.assert_array_equal(result1.equity.values, result2.equity.values)
    assert len(result1.trades) == len(result2.trades)
    if len(result1.trades) > 0:
        np.testing.assert_array_equal(
            result1.trades["return"].values, result2.trades["return"].values
        )
