from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from trade_advisor.data.providers.base import DataProvider

log = logging.getLogger(__name__)

_providers: dict[str, type[DataProvider]] = {}


def register_provider(name: str, provider_class: type[DataProvider]) -> None:
    if name in _providers:
        raise ValueError(f"Provider '{name}' is already registered")
    _providers[name] = provider_class
    log.debug("Registered provider: %s → %s", name, provider_class.__name__)


def get_provider(name: str) -> type[DataProvider]:
    if name not in _providers:
        raise KeyError(f"Provider '{name}' not registered. Available: {list_providers()}")
    return _providers[name]


def list_providers() -> list[str]:
    return sorted(_providers.keys())


from trade_advisor.data.providers.yahoo import YahooProvider  # noqa: E402

register_provider("yahoo", YahooProvider)

try:
    from trade_advisor.data.providers.twelvedata import TwelveDataProvider

    register_provider("twelvedata", TwelveDataProvider)
except ImportError as exc:
    log.warning("TwelveDataProvider not registered: %s", exc)
