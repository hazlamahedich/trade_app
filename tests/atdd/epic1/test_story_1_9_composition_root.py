"""ATDD red-phase: Story 1.9 — Composition Root & Strategy Protocol.

All tests are SKIPPED (TDD red phase). Remove when implementing Story 1.9.
"""

from __future__ import annotations

import pytest


class TestStory19CompositionRoot:
    """Story 1.9: Protocol-based DI, single composition root, Strategy Protocol."""

    @pytest.mark.skip(reason="ATDD red phase — Story 1.9 not implemented")
    def test_bootstrap_composition_root_exists(self):
        from trade_advisor.core.container import bootstrap

        assert callable(bootstrap)

    @pytest.mark.skip(reason="ATDD red phase — Story 1.9 not implemented")
    def test_strategy_protocol_exists(self):
        from trade_advisor.strategy.interface import Strategy

        assert hasattr(Strategy, "generate_signals")

    @pytest.mark.skip(reason="ATDD red phase — Story 1.9 not implemented")
    def test_strategy_protocol_has_information_latency(self):
        """SE-5: information latency declaration is part of Strategy Protocol."""
        from trade_advisor.strategy.interface import Strategy

        assert hasattr(Strategy, "information_latency") or hasattr(Strategy, "max_lookback")

    @pytest.mark.skip(reason="ATDD red phase — Story 1.9 not implemented")
    def test_signal_models_exist(self):
        from trade_advisor.strategy.schemas import Signal

        sig = Signal(direction="BUY", confidence=0.8, timestamp="2024-01-01T00:00:00Z")
        assert sig.direction == "BUY"

    @pytest.mark.skip(reason="ATDD red phase — Story 1.9 not implemented")
    def test_real_wiring_data_provider_to_yahoo(self):
        from trade_advisor.core.container import bootstrap

        container = bootstrap()
        assert container.data_provider is not None
        from trade_advisor.data.providers.base import DataProvider

        assert isinstance(container.data_provider, DataProvider)

    @pytest.mark.skip(reason="ATDD red phase — Story 1.9 not implemented")
    def test_cross_module_imports_use_protocols_only(self):
        """No module imports concrete implementations from another module."""
        from pathlib import Path

        src = Path(__file__).resolve().parents[4] / "src" / "trade_advisor"
        for py_file in src.rglob("*.py"):
            if "container" in py_file.name:
                continue
            content = py_file.read_text()
            if "from trade_advisor.data.providers.yahoo import" in content:
                rel = py_file.relative_to(src.parent.parent)
                if "container" not in str(rel) and "providers" not in str(rel):
                    pytest.fail(f"{rel} imports concrete YahooProvider")

    @pytest.mark.skip(reason="ATDD red phase — Story 1.9 not implemented")
    def test_strategy_universe_features_signals_contract(self):
        """SE-3: Strategy interface defines universe, features, signals, sizing."""
        from trade_advisor.strategy.interface import Strategy

        proto_attrs = dir(Strategy)
        assert "generate_signals" in proto_attrs
