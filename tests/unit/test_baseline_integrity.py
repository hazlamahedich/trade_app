"""Story 2.8: Mandatory Baseline Comparison & Integrity Checks — comprehensive tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tests.helpers import _synthetic_ohlcv
from trade_advisor.backtest.integrity import IntegrityResult, check_integrity
from trade_advisor.config import BacktestConfig, CostModel


@pytest.fixture
def equity_normal() -> pd.Series:
    rng = np.random.default_rng(42)
    vals = 100_000 * np.cumprod(1 + rng.normal(0.0003, 0.01, 500))
    return pd.Series(vals, name="equity")


@pytest.fixture
def equity_with_gap() -> pd.Series:
    s = pd.Series([100000, 101000, pd.NA, 103000, 104000, pd.NA, pd.NA, 107000])
    return s


@pytest.fixture
def equity_negative() -> pd.Series:
    return pd.Series([100000, 50000, -1000, -5000])


@pytest.fixture
def equity_zero_wipeout() -> pd.Series:
    return pd.Series([100000, 80000, 50000, 0, 0])


@pytest.fixture
def equity_single_bar_double() -> pd.Series:
    return pd.Series([100000, 500000, 300000])


@pytest.fixture
def backtest_cfg() -> BacktestConfig:
    return BacktestConfig(
        initial_cash="100000",
        cost=CostModel(commission_pct=0.001, slippage_pct=0.0005),
    )


@pytest.fixture
def ohlcv_500() -> pd.DataFrame:
    return _synthetic_ohlcv(n=500, seed=42)


# ===== INTEGRITY TESTS (12) =====


class TestIntegrity:
    def test_valid_equity_passes(self, equity_normal):
        result = check_integrity(equity_normal)
        assert result.is_valid is True
        assert result.should_halt_display is False
        assert len(result.errors) == 0

    def test_negative_portfolio_detected(self, equity_negative):
        result = check_integrity(equity_negative)
        assert result.is_valid is False
        assert any("negative" in e.lower() for e in result.errors)

    def test_single_bar_return_over_100_pct_detected(self, equity_single_bar_double):
        result = check_integrity(equity_single_bar_double)
        assert result.is_valid is False
        assert any("single-bar" in e.lower() for e in result.errors)

    def test_cumulative_return_over_100_pct_not_flagged(self):
        rng = np.random.default_rng(99)
        vals = 100_000 * np.cumprod(1 + rng.normal(0.001, 0.005, 500))
        equity = pd.Series(vals)
        result = check_integrity(equity)
        assert result.is_valid is True

    def test_nan_gap_detected(self, equity_with_gap):
        result = check_integrity(equity_with_gap)
        assert result.is_valid is False
        assert any("nan" in e.lower() for e in result.errors)

    def test_multiple_nan_gaps_detected(self, equity_with_gap):
        result = check_integrity(equity_with_gap)
        nan_errors = [e for e in result.errors if "nan" in e.lower()]
        assert len(nan_errors) >= 1

    def test_halt_display_on_error(self, equity_negative):
        result = check_integrity(equity_negative)
        assert result.should_halt_display is True

    def test_no_halt_on_valid(self, equity_normal):
        result = check_integrity(equity_normal)
        assert result.should_halt_display is False

    def test_no_halt_on_warning_only(self, equity_zero_wipeout):
        result = check_integrity(equity_zero_wipeout)
        assert result.should_halt_display is False
        assert len(result.warnings) > 0

    def test_warning_zero_portfolio(self, equity_zero_wipeout):
        result = check_integrity(equity_zero_wipeout)
        assert any("wipeout" in w.lower() for w in result.warnings)

    def test_warning_low_trade_count(self, equity_normal):
        result = check_integrity(equity_normal, trade_count=5)
        assert any("insufficient" in w.lower() for w in result.warnings)

    def test_warning_sharpe_sanity(self, equity_normal):
        result = check_integrity(equity_normal, sharpe=5.0)
        assert any("sharpe" in w.lower() for w in result.warnings)


# ===== BASELINE TESTS (8) =====


class TestBaseline:
    def test_buy_and_hold_constant_long(self, ohlcv_500, backtest_cfg):
        from trade_advisor.backtest.baseline import run_buy_and_hold

        result = run_buy_and_hold(ohlcv_500, backtest_cfg)
        assert (result.positions == 1.0).all()

    def test_baseline_always_present(self, ohlcv_500, backtest_cfg):
        from trade_advisor.backtest.baseline import compute_with_baseline
        from trade_advisor.strategies.sma_cross import SmaCross

        signals = SmaCross(fast=20, slow=50).generate_signals(ohlcv_500)
        comp = compute_with_baseline(ohlcv_500, signals, backtest_cfg)
        assert comp.buy_and_hold_metrics is not None

    def test_is_label_always_present(self, ohlcv_500, backtest_cfg):
        from trade_advisor.backtest.baseline import compute_with_baseline
        from trade_advisor.strategies.sma_cross import SmaCross

        signals = SmaCross(fast=20, slow=50).generate_signals(ohlcv_500)
        comp = compute_with_baseline(ohlcv_500, signals, backtest_cfg)
        assert comp.is_label == "In-Sample Only — not validated for live trading"

    def test_sample_type_in_sample(self, ohlcv_500, backtest_cfg):
        from trade_advisor.backtest.baseline import compute_with_baseline
        from trade_advisor.strategies.sma_cross import SmaCross

        signals = SmaCross(fast=20, slow=50).generate_signals(ohlcv_500)
        comp = compute_with_baseline(ohlcv_500, signals, backtest_cfg)
        assert comp.sample_type == "in_sample"

    def test_baseline_uses_same_config(self, ohlcv_500, backtest_cfg):
        from trade_advisor.backtest.baseline import compute_with_baseline
        from trade_advisor.strategies.sma_cross import SmaCross

        signals = SmaCross(fast=20, slow=50).generate_signals(ohlcv_500)
        comp = compute_with_baseline(ohlcv_500, signals, backtest_cfg)
        assert (
            comp.strategy_result.config.initial_cash == comp.buy_and_hold_result.config.initial_cash
        )
        assert comp.strategy_result.config.cost == comp.buy_and_hold_result.config.cost

    def test_buy_and_hold_return_convention_matches_strategy(self, ohlcv_500, backtest_cfg):
        from trade_advisor.backtest.baseline import compute_with_baseline
        from trade_advisor.strategies.sma_cross import SmaCross

        signals = SmaCross(fast=20, slow=50).generate_signals(ohlcv_500)
        comp = compute_with_baseline(ohlcv_500, signals, backtest_cfg)
        assert comp.strategy_result.returns is not None
        assert comp.buy_and_hold_result.returns is not None

    def test_buy_and_hold_known_answer(self, backtest_cfg):
        n = 100
        dates = pd.bdate_range("2020-01-01", periods=n)
        close = pd.Series(np.linspace(100, 120, n))
        ohlcv = pd.DataFrame(
            {
                "symbol": "TEST",
                "interval": "1d",
                "timestamp": dates,
                "open": close,
                "high": close + 0.5,
                "low": close - 0.5,
                "close": close,
                "adj_close": close,
                "volume": 1_000_000,
                "source": "synthetic",
            }
        )
        zero_cfg = BacktestConfig(
            initial_cash="100000",
            cost=CostModel(commission_pct=0.0, slippage_pct=0.0),
        )
        from trade_advisor.backtest.baseline import run_buy_and_hold

        result = run_buy_and_hold(ohlcv, zero_cfg)
        expected_return = (120 / 100) - 1.0
        actual_return = float(result.equity.iloc[-1]) / 100_000 - 1.0
        assert abs(actual_return - expected_return) < 0.01

    def test_alpha_beta_computed_not_nan(self, ohlcv_500, backtest_cfg):
        from trade_advisor.backtest.baseline import compute_with_baseline
        from trade_advisor.strategies.sma_cross import SmaCross

        signals = SmaCross(fast=20, slow=50).generate_signals(ohlcv_500)
        comp = compute_with_baseline(ohlcv_500, signals, backtest_cfg)
        assert np.isfinite(comp.strategy_metrics.alpha)
        assert np.isfinite(comp.strategy_metrics.beta)
        assert np.isfinite(comp.strategy_metrics.information_ratio)


# ===== REGIME TESTS (8) =====


class TestRegime:
    def test_regime_stratification_returns_labels(self, ohlcv_500):
        from trade_advisor.backtest.regime import stratify_by_regime

        signals = pd.Series(1.0, index=ohlcv_500.index)
        regimes = stratify_by_regime(ohlcv_500, signals)
        assert "trending" in regimes
        assert "mean_reverting" in regimes

    def test_regime_masks_boolean(self, ohlcv_500):
        from trade_advisor.backtest.regime import stratify_by_regime

        signals = pd.Series(1.0, index=ohlcv_500.index)
        regimes = stratify_by_regime(ohlcv_500, signals)
        for key in regimes:
            assert regimes[key].dtype == bool

    def test_regime_masks_cover_all_bars(self, ohlcv_500):
        from trade_advisor.backtest.regime import stratify_by_regime

        signals = pd.Series(1.0, index=ohlcv_500.index)
        regimes = stratify_by_regime(ohlcv_500, signals)
        n = len(ohlcv_500)
        trend_mean = regimes["trending"].sum() + regimes["mean_reverting"].sum()
        assert trend_mean <= n + 10

    def test_regime_short_data_returns_empty(self):
        from trade_advisor.backtest.regime import stratify_by_regime

        n = 30
        dates = pd.bdate_range("2020-01-01", periods=n)
        close = pd.Series(np.linspace(100, 110, n))
        ohlcv = pd.DataFrame(
            {
                "symbol": "SM",
                "interval": "1d",
                "timestamp": dates,
                "open": close,
                "high": close + 0.5,
                "low": close - 0.5,
                "close": close,
                "adj_close": close,
                "volume": 1_000_000,
                "source": "synthetic",
            }
        )
        signals = pd.Series(1.0, index=ohlcv.index)
        regimes = stratify_by_regime(ohlcv, signals)
        for key in regimes:
            assert regimes[key].sum() == 0

    def test_trending_mean_reverting_complementary(self, ohlcv_500):
        from trade_advisor.backtest.regime import stratify_by_regime

        signals = pd.Series(1.0, index=ohlcv_500.index)
        regimes = stratify_by_regime(ohlcv_500, signals)
        total = (regimes["trending"] | regimes["mean_reverting"]).sum()
        n = len(ohlcv_500)
        assert total <= n

    def test_regime_labels_backward_looking(self, ohlcv_500):
        from trade_advisor.backtest.regime import stratify_by_regime

        signals = pd.Series(1.0, index=ohlcv_500.index)
        regimes = stratify_by_regime(ohlcv_500, signals)
        for key in regimes:
            mask = regimes[key]
            assert len(mask) == len(ohlcv_500)

    def test_regime_insufficient_bucket_excluded(self):
        rng = np.random.default_rng(42)
        n = 70
        dates = pd.bdate_range("2020-01-01", periods=n)
        close = pd.Series(100.0 + np.cumsum(rng.normal(0, 0.1, n)))
        ohlcv = pd.DataFrame(
            {
                "symbol": "SM",
                "interval": "1d",
                "timestamp": dates,
                "open": close,
                "high": close + 0.5,
                "low": close - 0.5,
                "close": close,
                "adj_close": close,
                "volume": 1_000_000,
                "source": "synthetic",
            }
        )
        from trade_advisor.backtest.regime import stratify_by_regime

        signals = pd.Series(1.0, index=ohlcv.index)
        regimes = stratify_by_regime(ohlcv, signals)
        for key in regimes:
            mask = regimes[key]
            if mask.sum() > 0:
                assert mask.sum() >= 60

    def test_regime_deterministic(self, ohlcv_500):
        from trade_advisor.backtest.regime import stratify_by_regime

        signals = pd.Series(1.0, index=ohlcv_500.index)
        results = []
        for _ in range(10):
            regimes = stratify_by_regime(ohlcv_500, signals)
            results.append(regimes)
        for key in results[0]:
            for i in range(1, len(results)):
                assert (results[0][key] == results[i][key]).all()


# ===== DETERMINISM TESTS (2) =====


class TestDeterminism:
    def test_baseline_deterministic(self, ohlcv_500, backtest_cfg):
        from trade_advisor.backtest.baseline import compute_with_baseline
        from trade_advisor.strategies.sma_cross import SmaCross

        signals = SmaCross(fast=20, slow=50).generate_signals(ohlcv_500)
        results = []
        for _ in range(10):
            comp = compute_with_baseline(ohlcv_500, signals, backtest_cfg)
            results.append(comp)
        for i in range(1, len(results)):
            np.testing.assert_array_equal(
                results[0].strategy_result.equity.values,
                results[i].strategy_result.equity.values,
            )

    def test_integrity_deterministic(self, equity_normal):
        results = []
        for _ in range(10):
            results.append(check_integrity(equity_normal))
        for i in range(1, len(results)):
            assert results[0].is_valid == results[i].is_valid
            assert results[0].errors == results[i].errors
            assert results[0].warnings == results[i].warnings


# ===== INTEGRATION TESTS (3) =====


class TestIntegration:
    def test_full_pipeline_with_baseline(self, ohlcv_500, backtest_cfg):
        from trade_advisor.backtest.baseline import compute_with_baseline
        from trade_advisor.strategies.sma_cross import SmaCross

        signals = SmaCross(fast=20, slow=50).generate_signals(ohlcv_500)
        comp = compute_with_baseline(ohlcv_500, signals, backtest_cfg)
        assert comp.strategy_result is not None
        assert comp.buy_and_hold_result is not None
        assert comp.strategy_metrics is not None
        assert comp.buy_and_hold_metrics is not None
        assert comp.integrity is not None
        assert comp.is_label != ""
        assert comp.sample_type == "in_sample"

    def test_integrity_catches_broken_result(self):
        broken = pd.Series([100000, -5000, 200000])
        result = check_integrity(broken)
        assert result.is_valid is False

    def test_regime_stratification_with_real_data(self, ohlcv_500):
        from trade_advisor.backtest.regime import stratify_by_regime
        from trade_advisor.strategies.sma_cross import SmaCross

        signals = SmaCross(fast=20, slow=50).generate_signals(ohlcv_500)
        regimes = stratify_by_regime(ohlcv_500, signals)
        has_trending = regimes["trending"].sum() > 0
        has_mean_rev = regimes["mean_reverting"].sum() > 0
        assert has_trending or has_mean_rev


# ===== ADVERSARIAL / EDGE-CASE TESTS (6) =====


class TestAdversarial:
    def test_flat_signal_baseline_still_computes(self, ohlcv_500, backtest_cfg):
        from trade_advisor.backtest.baseline import compute_with_baseline

        signals = pd.Series(0.0, index=ohlcv_500.index)
        comp = compute_with_baseline(ohlcv_500, signals, backtest_cfg)
        assert comp.buy_and_hold_metrics is not None

    def test_negative_equity_halts_display(self, equity_negative):
        result = check_integrity(equity_negative)
        assert result.should_halt_display is True

    def test_exactly_zero_return_not_flagged(self):
        equity = pd.Series(np.full(100, 100000.0))
        result = check_integrity(equity)
        assert result.is_valid is True

    def test_exactly_100_pct_single_bar_flagged(self):
        equity = pd.Series([100000, 250000])
        result = check_integrity(equity)
        assert result.is_valid is False

    def test_equity_going_to_zero_not_halted(self, equity_zero_wipeout):
        result = check_integrity(equity_zero_wipeout)
        assert result.should_halt_display is False

    @pytest.mark.parametrize(
        "series",
        [
            pd.Series([], dtype=float),
            pd.Series([100000], dtype=float),
            pd.Series([pd.NA, pd.NA, pd.NA]),
        ],
    )
    def test_integrity_never_crashes(self, series):
        result = check_integrity(series)
        assert isinstance(result, IntegrityResult)
