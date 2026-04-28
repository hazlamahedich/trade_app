"""Composition root — single wiring point for application dependencies.

``bootstrap()`` returns a frozen ``AppContainer`` dataclass that holds
all resolved dependencies.  Override via ``dataclasses.replace()`` for
testing or alternative configurations.

Design decisions
----------------
- **Sync factory** — ``bootstrap()`` is synchronous.  ``DatabaseManager``
  is created but not entered; callers manage its async lifecycle.
- **No DI framework** — explicit wiring, no magic.
- **Protocol-typed fields** — consumers depend on abstractions, not
  concrete classes.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from trade_advisor.core.config import AppConfig
from trade_advisor.data.providers.base import DataProvider
from trade_advisor.data.providers.yahoo import YahooProvider
from trade_advisor.infra.db import DatabaseManager
from trade_advisor.strategies.sma_cross import SmaCross


@dataclass(frozen=True)
class AppContainer:
    """Immutable application dependency container."""

    config: AppConfig
    data_provider: DataProvider
    strategy_registry: MappingProxyType  # type: ignore[type-arg]
    db: DatabaseManager

    def __post_init__(self) -> None:
        if not isinstance(self.strategy_registry, MappingProxyType):
            raise TypeError(
                f"strategy_registry must be MappingProxyType, got {type(self.strategy_registry).__name__}"
            )


def bootstrap(config: AppConfig | None = None) -> AppContainer:
    """Wire up the application and return a frozen container.

    Parameters
    ----------
    config : AppConfig | None
        Application configuration.  Defaults to a fresh ``AppConfig()``
        which reads from environment / ``.env``.

    Returns
    -------
    AppContainer
        Frozen dataclass with all resolved dependencies.
    """
    cfg = config or AppConfig()  # type: ignore[call-arg]
    data_provider = YahooProvider(config=cfg.data)
    db = DatabaseManager(config=cfg.database)
    registry: dict[str, type] = {
        "sma_cross": SmaCross,
    }
    for name, cls in registry.items():
        if not isinstance(cls, type):
            raise TypeError(f"strategy_registry[{name!r}] must be a type, got {type(cls)}")
    strategy_registry = MappingProxyType(registry)
    return AppContainer(
        config=cfg,
        data_provider=data_provider,
        strategy_registry=strategy_registry,
        db=db,
    )
