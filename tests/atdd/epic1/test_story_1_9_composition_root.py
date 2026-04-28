"""ATDD tests: Story 1.9 — Composition Root & Strategy Protocol.

Validates that the composition root, Strategy Protocol, and signal schemas
are wired correctly and accessible from the public API.
"""

from __future__ import annotations

import pytest

from trade_advisor.core.container import AppContainer, bootstrap
from trade_advisor.strategies.interface import Strategy
from trade_advisor.strategies.schemas import SignalModel
from trade_advisor.strategies.sma_cross import SmaCross


class TestStory19BootstrapCompositionRoot:
    def test_bootstrap_composition_root_exists(self):
        assert callable(bootstrap)
        c = bootstrap()
        assert isinstance(c, AppContainer)

    def test_strategy_protocol_exists(self):
        assert hasattr(Strategy, "generate_signals")
        assert hasattr(Strategy, "information_latency")
        assert hasattr(Strategy, "warmup_period")

    def test_strategy_protocol_has_information_latency(self):
        s = SmaCross(fast=10, slow=30)
        assert hasattr(s, "information_latency")
        assert s.information_latency >= 0

    def test_signal_models_exist(self):
        sig = SignalModel(
            timestamp="2024-01-01T00:00:00Z",
            symbol="SPY",
            signal=1.0,
            strategy_name="sma",
        )
        assert sig.signal == 1.0

    def test_real_wiring_data_provider_to_yahoo(self):
        container = bootstrap()
        assert container.data_provider is not None
        from trade_advisor.data.providers.base import DataProvider

        assert isinstance(container.data_provider, DataProvider)

    def test_cross_module_imports_use_protocols_only(self):
        from pathlib import Path

        src = Path(__file__).resolve().parents[3] / "src" / "trade_advisor"
        for py_file in src.rglob("*.py"):
            if "container" in py_file.name:
                continue
            content = py_file.read_text(errors="replace")
            if "from trade_advisor.data.providers.yahoo import" in content:
                rel = py_file.relative_to(src.parent.parent)
                if (
                    "container" not in str(rel)
                    and "providers" not in str(rel)
                    and "routes" not in str(rel)
                ):
                    pytest.fail(f"{rel} imports concrete YahooProvider")

    def test_strategy_satisfies_protocol_structurally(self):
        s = SmaCross(fast=10, slow=30)
        assert isinstance(s, Strategy)
