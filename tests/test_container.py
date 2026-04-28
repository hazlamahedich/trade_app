"""Tests for the composition root (AppContainer + bootstrap)."""

from __future__ import annotations

import dataclasses

import pytest

from trade_advisor.core.config import AppConfig
from trade_advisor.core.container import AppContainer, bootstrap
from trade_advisor.data.providers.base import DataProvider
from trade_advisor.data.providers.yahoo import YahooProvider
from trade_advisor.strategies.sma_cross import SmaCross


class TestBootstrap:
    def test_bootstrap_returns_container(self):
        c = bootstrap()
        assert isinstance(c, AppContainer)

    def test_bootstrap_creates_default_config(self):
        c = bootstrap()
        assert isinstance(c.config, AppConfig)

    def test_bootstrap_with_custom_config(self):
        cfg = AppConfig()  # type: ignore[call-arg]
        c = bootstrap(config=cfg)
        assert c.config is cfg

    def test_container_is_frozen(self):
        c = bootstrap()
        assert dataclasses.is_dataclass(c)
        assert c.__dataclass_params__.frozen

    def test_container_override_data_provider(self):
        from tests.helpers import StubDataProvider

        c = bootstrap()
        stub = StubDataProvider()
        c2 = dataclasses.replace(c, data_provider=stub)
        assert c2.data_provider is stub
        assert c.data_provider is not stub

    def test_strategy_registry_has_sma_cross(self):
        c = bootstrap()
        assert "sma_cross" in c.strategy_registry
        assert c.strategy_registry["sma_cross"] is SmaCross

    def test_strategy_registry_is_immutable(self):
        c = bootstrap()
        with pytest.raises(TypeError):
            c.strategy_registry["bogus"] = int  # type: ignore[index]

    def test_container_fields_use_protocol_types(self):
        import typing

        hints = typing.get_type_hints(AppContainer)
        assert hints["data_provider"] is DataProvider

    def test_bootstrap_wires_yahoo_provider(self):
        c = bootstrap()
        assert isinstance(c.data_provider, YahooProvider)

    def test_container_override_isolation(self):
        from tests.helpers import StubDataProvider

        c = bootstrap()
        stub1 = StubDataProvider()
        stub2 = StubDataProvider()
        c1 = dataclasses.replace(c, data_provider=stub1)
        c2 = dataclasses.replace(c, data_provider=stub2)
        assert c1.data_provider is stub1
        assert c2.data_provider is stub2
        assert c.data_provider is not stub1
        assert c.data_provider is not stub2
