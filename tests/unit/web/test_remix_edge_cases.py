from __future__ import annotations

import pytest

from trade_advisor.web.services.remix import (
    MAX_VARIANTS,
    VariantSuggestion,
    _validate_sma_params,
    generate_variants,
)


class TestValidateSmaParams:
    @pytest.mark.parametrize("fast,slow", [(1, 2), (5, 10), (19, 20)])
    def test_valid_params(self, fast, slow):
        assert _validate_sma_params(fast, slow) is True

    @pytest.mark.parametrize("fast,slow", [(0, 5), (-1, 5), (1, 1), (5, 3), (1, 1)])
    def test_invalid_params(self, fast, slow):
        assert _validate_sma_params(fast, slow) is False


class TestGenerateVariantsEdgeCases:
    def test_unknown_strategy_returns_empty(self):
        assert generate_variants({"fast": 20, "slow": 50}, strategy_type="rsi") == []

    def test_empty_config_uses_defaults(self):
        variants = generate_variants({})
        assert len(variants) >= 1

    def test_fast_equals_slow_returns_empty(self):
        assert generate_variants({"fast": 20, "slow": 20}) == []

    def test_narrow_excluded_when_fast_le_6(self):
        variants = generate_variants({"fast": 6, "slow": 50})
        assert not any("more signals" in v.hint for v in variants)

    def test_narrow_included_when_fast_gt_6(self):
        variants = generate_variants({"fast": 7, "slow": 50})
        assert any("more signals" in v.hint for v in variants)

    def test_golden_cross_excluded_when_slow_gte_150(self):
        variants = generate_variants({"fast": 20, "slow": 200})
        assert not any("long-term trend" in v.hint for v in variants)

    def test_boolean_values_excluded_from_params(self):
        variants = generate_variants({"fast": 20, "slow": 50, "flag": True})
        for v in variants:
            assert "flag" not in v.params

    def test_excluded_keys_do_not_leak(self):
        variants = generate_variants(
            {
                "fast": 20,
                "slow": 50,
                "source_run_id": "abc",
                "symbol": "SPY",
                "strategy_type": "sma",
            }
        )
        for v in variants:
            assert "source_run_id" not in v.params
            assert "symbol" not in v.params

    def test_max_variants_cap(self):
        import trade_advisor.web.services.remix as remix_mod

        def _huge_generator(config_dict):
            return [
                VariantSuggestion(label=f"v{i}", hint="h", params={"fast": i}) for i in range(20)
            ]

        old = remix_mod._VARIANT_DISPATCH.copy()
        try:
            remix_mod._VARIANT_DISPATCH["test_huge"] = _huge_generator
            result = generate_variants({"fast": 20, "slow": 50}, strategy_type="test_huge")
            assert len(result) <= MAX_VARIANTS
        finally:
            remix_mod._VARIANT_DISPATCH = old
