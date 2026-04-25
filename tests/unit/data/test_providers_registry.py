from __future__ import annotations

import pytest


def test_register_and_get_provider():
    from trade_advisor.data.providers.registry import _providers, register_provider, get_provider

    class FakeProvider:
        @property
        def name(self) -> str:
            return "fake"

        @property
        def supported_intervals(self) -> list[str]:
            return ["1d"]

        async def fetch(self, symbol, *, start=None, end=None, interval="1d"):
            pass

        def validate(self, df):
            return []

        async def check_connectivity(self):
            pass

    try:
        register_provider("fake_test", FakeProvider)
        retrieved = get_provider("fake_test")
        assert retrieved is FakeProvider
    finally:
        _providers.pop("fake_test", None)


def test_list_providers_includes_yahoo():
    from trade_advisor.data.providers.registry import list_providers

    assert "yahoo" in list_providers()


def test_list_providers_includes_twelvedata():
    from trade_advisor.data.providers.registry import list_providers

    assert "twelvedata" in list_providers()


def test_register_duplicate_raises():
    from trade_advisor.data.providers.registry import _providers, register_provider

    class Dummy:
        pass

    _providers["dup_test"] = Dummy
    try:
        with pytest.raises(ValueError, match="already registered"):
            register_provider("dup_test", Dummy)
    finally:
        _providers.pop("dup_test", None)
