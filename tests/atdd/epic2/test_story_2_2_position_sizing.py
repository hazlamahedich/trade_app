"""ATDD red-phase: Story 2.2 — Position Sizing Methods.

Tests assert the expected end-state AFTER full Story 2.2 implementation.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from trade_advisor.strategies.sizing import (
    fixed_fractional,
    half_kelly,
    inverse_vol,
    vol_targeting,
)


class TestStory22PositionSizing:
    """Story 2.2: Built-in position sizing methods."""

    def test_fixed_fractional_sizing(self):
        size = fixed_fractional(equity=Decimal("100000"), fraction=Decimal("0.10"))
        assert isinstance(size, Decimal)
        assert size == Decimal("10000")

    def test_half_kelly_sizing(self):
        size = half_kelly(
            equity=Decimal("100000"),
            win_rate=0.55,
            avg_win=Decimal("0.02"),
            avg_loss=Decimal("0.01"),
        )
        assert isinstance(size, Decimal)
        assert size > Decimal("0")

    def test_vol_targeting_sizing(self):
        size = vol_targeting(
            equity=Decimal("100000"),
            target_vol=Decimal("0.15"),
            asset_vol=Decimal("0.25"),
        )
        assert isinstance(size, Decimal)
        assert size > Decimal("0")

    def test_inverse_vol_sizing(self):
        size = inverse_vol(
            equity=Decimal("100000"),
            asset_vol=Decimal("0.20"),
        )
        assert isinstance(size, Decimal)
        assert size > Decimal("0")

    def test_sizing_params_included_in_strategy_config(self):
        from trade_advisor.strategies.sizing import FixedFractionalConfig

        cfg = FixedFractionalConfig(fraction=Decimal("0.10"))
        size = cfg.compute(equity=Decimal("100000"))
        assert size == Decimal("10000")

    def test_negative_fraction_raises(self):
        with pytest.raises(ValueError):
            fixed_fractional(equity=Decimal("100000"), fraction=Decimal("-0.10"))

    def test_zero_volatility_raises(self):
        with pytest.raises(ValueError):
            vol_targeting(
                equity=Decimal("100000"),
                target_vol=Decimal("0.15"),
                asset_vol=Decimal("0.0"),
            )
