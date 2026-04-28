"""Unit tests for strategies/sizing.py — position sizing methods.

Covers: fixed_fractional, half_kelly, vol_targeting, inverse_vol,
all validators, edge cases, signal modulation, and config models.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from trade_advisor.core.types import quantize
from trade_advisor.strategies.sizing import (
    MAX_FRACTION,
    VOL_FLOOR,
    FixedFractionalConfig,
    HalfKellyConfig,
    InverseVolConfig,
    VolTargetingConfig,
    fixed_fractional,
    half_kelly,
    inverse_vol,
    vol_targeting,
)

# ── fixed_fractional ──────────────────────────────────────────


class TestFixedFractional:
    def test_basic(self):
        size = fixed_fractional(Decimal("100000"), Decimal("0.10"))
        assert size == Decimal("10000")

    def test_full_allocation(self):
        size = fixed_fractional(Decimal("100000"), Decimal("1.0"))
        assert size == Decimal("100000")

    def test_signal_modulation(self):
        size = fixed_fractional(Decimal("100000"), Decimal("0.10"), signal=0.5)
        assert size == Decimal("5000")

    def test_negative_fraction_raises(self):
        with pytest.raises(ValueError, match="fraction"):
            fixed_fractional(Decimal("100000"), Decimal("-0.10"))

    def test_zero_fraction_raises(self):
        with pytest.raises(ValueError, match="fraction"):
            fixed_fractional(Decimal("100000"), Decimal("0"))

    def test_fraction_over_100pct_clamped(self):
        size = fixed_fractional(Decimal("100000"), Decimal("1.5"))
        assert size == Decimal("100000")

    def test_output_quantized(self):
        size = fixed_fractional(Decimal("100001"), Decimal("0.33333"))
        expected = quantize(Decimal("100001") * Decimal("0.33333"))
        assert size == expected


# ── half_kelly ────────────────────────────────────────────────


class TestHalfKelly:
    def test_basic_positive(self):
        size = half_kelly(
            Decimal("100000"),
            win_rate=0.55,
            avg_win=Decimal("0.02"),
            avg_loss=Decimal("0.01"),
        )
        assert isinstance(size, Decimal)
        assert size > Decimal("0")

    def test_zero_edge_returns_zero(self):
        size = half_kelly(
            Decimal("100000"),
            win_rate=0.5,
            avg_win=Decimal("0.01"),
            avg_loss=Decimal("0.01"),
        )
        assert size == Decimal("0")

    def test_negative_edge_returns_zero(self):
        size = half_kelly(
            Decimal("100000"),
            win_rate=0.3,
            avg_win=Decimal("0.01"),
            avg_loss=Decimal("0.05"),
        )
        assert size == Decimal("0")

    def test_perfect_win_rate_finite(self):
        size = half_kelly(
            Decimal("100000"),
            win_rate=1.0,
            avg_win=Decimal("0.02"),
            avg_loss=Decimal("0.01"),
        )
        assert isinstance(size, Decimal)
        assert size.is_finite()
        assert size > Decimal("0")

    def test_zero_avg_loss_raises(self):
        with pytest.raises(ValueError, match="avg_loss"):
            half_kelly(
                Decimal("100000"),
                win_rate=0.55,
                avg_win=Decimal("0.02"),
                avg_loss=Decimal("0"),
            )

    def test_zero_avg_win_raises(self):
        with pytest.raises(ValueError, match="avg_win"):
            half_kelly(
                Decimal("100000"),
                win_rate=0.55,
                avg_win=Decimal("0"),
                avg_loss=Decimal("0.01"),
            )

    def test_nan_avg_loss_raises(self):
        with pytest.raises(ValueError, match="avg_loss"):
            half_kelly(
                Decimal("100000"),
                win_rate=0.55,
                avg_win=Decimal("0.02"),
                avg_loss=Decimal("NaN"),
            )

    def test_negative_avg_win_raises(self):
        with pytest.raises(ValueError, match="avg_win"):
            half_kelly(
                Decimal("100000"),
                win_rate=0.55,
                avg_win=Decimal("-0.02"),
                avg_loss=Decimal("0.01"),
            )

    def test_nan_avg_win_raises(self):
        with pytest.raises(ValueError, match="avg_win"):
            half_kelly(
                Decimal("100000"),
                win_rate=0.55,
                avg_win=Decimal("NaN"),
                avg_loss=Decimal("0.01"),
            )

    def test_infinity_avg_loss_raises(self):
        with pytest.raises(ValueError, match="avg_loss"):
            half_kelly(
                Decimal("100000"),
                win_rate=0.55,
                avg_win=Decimal("0.02"),
                avg_loss=Decimal("Infinity"),
            )

    def test_signal_modulation(self):
        size_full = half_kelly(
            Decimal("100000"),
            win_rate=0.6,
            avg_win=Decimal("0.02"),
            avg_loss=Decimal("0.01"),
        )
        size_half = half_kelly(
            Decimal("100000"),
            win_rate=0.6,
            avg_win=Decimal("0.02"),
            avg_loss=Decimal("0.01"),
            signal=0.5,
        )
        assert size_half * 2 == size_full


# ── vol_targeting ─────────────────────────────────────────────


class TestVolTargeting:
    def test_basic_target_less_than_asset(self):
        size = vol_targeting(Decimal("100000"), Decimal("0.15"), Decimal("0.25"))
        assert size < Decimal("100000")
        assert size > Decimal("0")

    def test_equal_vol_returns_equity(self):
        size = vol_targeting(Decimal("100000"), Decimal("0.20"), Decimal("0.20"))
        assert size == Decimal("100000")

    def test_leverage_clamped(self):
        size = vol_targeting(Decimal("100000"), Decimal("0.40"), Decimal("0.20"))
        assert size == Decimal("100000")

    def test_vol_floor(self):
        size = vol_targeting(Decimal("100000"), Decimal("0.15"), Decimal("0.001"))
        expected = quantize(Decimal("100000") * min(Decimal("0.15") / VOL_FLOOR, MAX_FRACTION))
        assert size == expected
        assert size.is_finite()

    def test_zero_target_vol_raises(self):
        with pytest.raises(ValueError, match="target_vol"):
            vol_targeting(Decimal("100000"), Decimal("0"), Decimal("0.20"))

    def test_zero_asset_vol_raises(self):
        with pytest.raises(ValueError, match="asset_vol"):
            vol_targeting(Decimal("100000"), Decimal("0.15"), Decimal("0"))

    def test_nan_target_vol_raises(self):
        with pytest.raises(ValueError, match="target_vol"):
            vol_targeting(Decimal("100000"), Decimal("NaN"), Decimal("0.20"))

    def test_nan_asset_vol_raises(self):
        with pytest.raises(ValueError, match="asset_vol"):
            vol_targeting(Decimal("100000"), Decimal("0.15"), Decimal("NaN"))

    def test_infinity_target_vol_raises(self):
        with pytest.raises(ValueError, match="target_vol"):
            vol_targeting(Decimal("100000"), Decimal("Infinity"), Decimal("0.20"))

    def test_infinity_asset_vol_raises(self):
        with pytest.raises(ValueError, match="asset_vol"):
            vol_targeting(Decimal("100000"), Decimal("0.15"), Decimal("Infinity"))

    def test_signal_modulation(self):
        full = vol_targeting(Decimal("100000"), Decimal("0.15"), Decimal("0.25"))
        half = vol_targeting(Decimal("100000"), Decimal("0.15"), Decimal("0.25"), signal=0.5)
        assert half * 2 == full


# ── inverse_vol ───────────────────────────────────────────────


class TestInverseVol:
    def test_basic(self):
        size = inverse_vol(Decimal("100000"), Decimal("0.20"))
        assert isinstance(size, Decimal)
        assert size > Decimal("0")

    def test_tiny_vol_clamped(self):
        size = inverse_vol(Decimal("100000"), Decimal("0.001"))
        assert isinstance(size, Decimal)
        assert size > Decimal("0")
        assert size.is_finite()

    def test_high_vol_positive(self):
        size = inverse_vol(Decimal("100000"), Decimal("2.0"))
        assert size > Decimal("0")

    def test_signal_modulation(self):
        full = inverse_vol(Decimal("100000"), Decimal("0.20"))
        half = inverse_vol(Decimal("100000"), Decimal("0.20"), signal=0.5)
        assert half * 2 == full

    def test_zero_vol_raises(self):
        with pytest.raises(ValueError, match="asset_vol"):
            inverse_vol(Decimal("100000"), Decimal("0"))


# ── shared: equity validation ────────────────────────────────


class TestEquityValidation:
    def test_negative_equity_fixed_fractional(self):
        with pytest.raises(ValueError, match="equity"):
            fixed_fractional(Decimal("-100"), Decimal("0.10"))

    def test_negative_equity_half_kelly(self):
        with pytest.raises(ValueError, match="equity"):
            half_kelly(Decimal("-100"), 0.6, Decimal("0.02"), Decimal("0.01"))

    def test_negative_equity_vol_targeting(self):
        with pytest.raises(ValueError, match="equity"):
            vol_targeting(Decimal("-100"), Decimal("0.15"), Decimal("0.25"))

    def test_negative_equity_inverse_vol(self):
        with pytest.raises(ValueError, match="equity"):
            inverse_vol(Decimal("-100"), Decimal("0.20"))

    def test_zero_equity_returns_zero_fixed_fractional(self):
        assert fixed_fractional(Decimal("0"), Decimal("0.10")) == Decimal("0")

    def test_zero_equity_returns_zero_half_kelly(self):
        assert half_kelly(Decimal("0"), 0.6, Decimal("0.02"), Decimal("0.01")) == Decimal("0")

    def test_zero_equity_returns_zero_vol_targeting(self):
        assert vol_targeting(Decimal("0"), Decimal("0.15"), Decimal("0.25")) == Decimal("0")

    def test_zero_equity_returns_zero_inverse_vol(self):
        assert inverse_vol(Decimal("0"), Decimal("0.20")) == Decimal("0")

    def test_zero_equity_with_invalid_fraction_still_raises(self):
        with pytest.raises(ValueError, match="fraction"):
            fixed_fractional(Decimal("0"), Decimal("-0.10"))

    def test_zero_equity_with_invalid_signal_still_raises(self):
        with pytest.raises(ValueError, match="signal"):
            fixed_fractional(Decimal("0"), Decimal("0.10"), signal=2.0)

    def test_nan_equity_raises(self):
        with pytest.raises(ValueError, match="equity"):
            fixed_fractional(Decimal("NaN"), Decimal("0.10"))

    def test_infinity_equity_raises(self):
        with pytest.raises(ValueError, match="equity"):
            fixed_fractional(Decimal("Infinity"), Decimal("0.10"))


# ── shared: signal validation ────────────────────────────────


class TestSignalValidation:
    def test_signal_out_of_range_raises(self):
        with pytest.raises(ValueError, match="signal"):
            fixed_fractional(Decimal("100000"), Decimal("0.10"), signal=1.5)

    def test_nan_signal_raises(self):
        with pytest.raises(ValueError, match="signal"):
            fixed_fractional(Decimal("100000"), Decimal("0.10"), signal=float("nan"))

    def test_infinity_signal_raises(self):
        with pytest.raises(ValueError, match="signal"):
            fixed_fractional(Decimal("100000"), Decimal("0.10"), signal=float("inf"))

    def test_signal_zero_produces_zero(self):
        assert fixed_fractional(Decimal("100000"), Decimal("0.10"), signal=0.0) == Decimal("0")
        assert half_kelly(Decimal("100000"), 0.6, Decimal("0.02"), Decimal("0.01"), signal=0.0) == Decimal("0")
        assert vol_targeting(Decimal("100000"), Decimal("0.15"), Decimal("0.25"), signal=0.0) == Decimal("0")
        assert inverse_vol(Decimal("100000"), Decimal("0.20"), signal=0.0) == Decimal("0")

    def test_negative_signal_same_as_positive(self):
        pos = fixed_fractional(Decimal("100000"), Decimal("0.10"), signal=0.5)
        neg = fixed_fractional(Decimal("100000"), Decimal("0.10"), signal=-0.5)
        assert pos == neg
        assert half_kelly(Decimal("100000"), 0.6, Decimal("0.02"), Decimal("0.01"), signal=-0.5) == half_kelly(Decimal("100000"), 0.6, Decimal("0.02"), Decimal("0.01"), signal=0.5)
        assert vol_targeting(Decimal("100000"), Decimal("0.15"), Decimal("0.25"), signal=-0.5) == vol_targeting(Decimal("100000"), Decimal("0.15"), Decimal("0.25"), signal=0.5)
        assert inverse_vol(Decimal("100000"), Decimal("0.20"), signal=-0.5) == inverse_vol(Decimal("100000"), Decimal("0.20"), signal=0.5)


# ── shared: win_rate validation ───────────────────────────────


class TestWinRateValidation:
    def test_nan_win_rate_raises(self):
        with pytest.raises(ValueError, match="win_rate"):
            half_kelly(Decimal("100000"), float("nan"), Decimal("0.02"), Decimal("0.01"))

    def test_inf_win_rate_raises(self):
        with pytest.raises(ValueError, match="win_rate"):
            half_kelly(Decimal("100000"), float("inf"), Decimal("0.02"), Decimal("0.01"))

    def test_zero_win_rate_raises(self):
        with pytest.raises(ValueError, match="win_rate"):
            half_kelly(Decimal("100000"), 0.0, Decimal("0.02"), Decimal("0.01"))

    def test_over_one_win_rate_raises(self):
        with pytest.raises(ValueError, match="win_rate"):
            half_kelly(Decimal("100000"), 1.5, Decimal("0.02"), Decimal("0.01"))

    def test_negative_win_rate_raises(self):
        with pytest.raises(ValueError, match="win_rate"):
            half_kelly(Decimal("100000"), -0.1, Decimal("0.02"), Decimal("0.01"))


# ── output precision ─────────────────────────────────────────


class TestOutputPrecision:
    def test_fixed_fractional_quantized(self):
        size = fixed_fractional(Decimal("99999"), Decimal("0.33333"))
        assert size == quantize(size)

    def test_half_kelly_quantized(self):
        size = half_kelly(Decimal("99999"), 0.6, Decimal("0.02"), Decimal("0.01"))
        assert size == quantize(size)

    def test_vol_targeting_quantized(self):
        size = vol_targeting(Decimal("99999"), Decimal("0.15"), Decimal("0.25"))
        assert size == quantize(size)

    def test_inverse_vol_quantized(self):
        size = inverse_vol(Decimal("99999"), Decimal("0.20"))
        assert size == quantize(size)

    def test_all_outputs_non_negative(self):
        for fn, args in [
            (fixed_fractional, (Decimal("100000"), Decimal("0.10"))),
            (half_kelly, (Decimal("100000"), 0.6, Decimal("0.02"), Decimal("0.01"))),
            (vol_targeting, (Decimal("100000"), Decimal("0.15"), Decimal("0.25"))),
            (inverse_vol, (Decimal("100000"), Decimal("0.20"))),
        ]:
            assert fn(*args) >= Decimal("0")


# ── config models ────────────────────────────────────────────


class TestConfigModels:
    def test_fixed_fractional_config_roundtrip(self):
        cfg = FixedFractionalConfig(fraction=Decimal("0.10"))
        data = cfg.model_dump()
        cfg2 = FixedFractionalConfig(**data)
        assert cfg2 == cfg

    def test_half_kelly_config_roundtrip(self):
        cfg = HalfKellyConfig(win_rate=0.55, avg_win=Decimal("0.02"), avg_loss=Decimal("0.01"))
        data = cfg.model_dump()
        cfg2 = HalfKellyConfig(**data)
        assert cfg2 == cfg

    def test_vol_targeting_config_roundtrip(self):
        cfg = VolTargetingConfig(target_vol=Decimal("0.15"), asset_vol=Decimal("0.25"))
        data = cfg.model_dump()
        cfg2 = VolTargetingConfig(**data)
        assert cfg2 == cfg

    def test_inverse_vol_config_roundtrip(self):
        cfg = InverseVolConfig(asset_vol=Decimal("0.20"))
        data = cfg.model_dump()
        cfg2 = InverseVolConfig(**data)
        assert cfg2 == cfg

    def test_fixed_fractional_config_compute(self):
        cfg = FixedFractionalConfig(fraction=Decimal("0.10"))
        direct = fixed_fractional(Decimal("100000"), Decimal("0.10"))
        assert cfg.compute(Decimal("100000")) == direct

    def test_half_kelly_config_compute(self):
        cfg = HalfKellyConfig(win_rate=0.55, avg_win=Decimal("0.02"), avg_loss=Decimal("0.01"))
        direct = half_kelly(Decimal("100000"), 0.55, Decimal("0.02"), Decimal("0.01"))
        assert cfg.compute(Decimal("100000")) == direct

    def test_vol_targeting_config_compute(self):
        cfg = VolTargetingConfig(target_vol=Decimal("0.15"), asset_vol=Decimal("0.25"))
        direct = vol_targeting(Decimal("100000"), Decimal("0.15"), Decimal("0.25"))
        assert cfg.compute(Decimal("100000")) == direct

    def test_inverse_vol_config_compute(self):
        cfg = InverseVolConfig(asset_vol=Decimal("0.20"))
        direct = inverse_vol(Decimal("100000"), Decimal("0.20"))
        assert cfg.compute(Decimal("100000")) == direct

    def test_configs_frozen(self):
        cfg = FixedFractionalConfig(fraction=Decimal("0.10"))
        with pytest.raises((AttributeError, ValueError)):
            cfg.fraction = Decimal("0.20")  # type: ignore[misc]

    def test_config_method_discriminator(self):
        assert FixedFractionalConfig(fraction=Decimal("0.10")).method == "fixed_fractional"
        assert (
            HalfKellyConfig(win_rate=0.55, avg_win=Decimal("0.02"), avg_loss=Decimal("0.01")).method
            == "half_kelly"
        )
        assert (
            VolTargetingConfig(target_vol=Decimal("0.15"), asset_vol=Decimal("0.25")).method
            == "vol_targeting"
        )
        assert InverseVolConfig(asset_vol=Decimal("0.20")).method == "inverse_vol"

    def test_config_json_roundtrip(self):
        cfg = VolTargetingConfig(target_vol=Decimal("0.15"), asset_vol=Decimal("0.25"))
        json_str = cfg.model_dump_json()
        cfg2 = VolTargetingConfig.model_validate_json(json_str)
        assert cfg2 == cfg

    def test_config_compute_with_signal(self):
        cfg = FixedFractionalConfig(fraction=Decimal("0.10"))
        assert cfg.compute(Decimal("100000"), signal=0.5) == Decimal("5000")
