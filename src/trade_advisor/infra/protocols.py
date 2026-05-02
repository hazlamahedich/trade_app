"""Structural protocols for database dependencies.

These ``Protocol`` definitions replace ``db: Any`` annotations across the
experiment layer (compare, reproduction, lineage, tracker) so that mypy can
verify correct usage at call sites without coupling to ``DatabaseManager``.
"""

from __future__ import annotations

from typing import Any, Protocol


class DatabaseReader(Protocol):
    """Minimal interface that experiment modules require from the database layer.

    Provides async ``read`` / ``write`` / ``write_many`` for the public API and
    synchronous ``_execute_read`` for modules that operate inside thread-pool
    contexts (compare, reproduction helpers).

    ``DatabaseManager`` satisfies this protocol structurally — no inheritance
    needed.
    """

    def _execute_read(
        self, query: str, params: tuple[Any, ...] | None
    ) -> list[tuple[Any, ...]]: ...

    async def read(
        self, query: str, params: tuple[Any, ...] | None = None
    ) -> list[tuple[Any, ...]]: ...

    async def write(self, query: str, params: tuple[Any, ...]) -> None: ...

    async def write_many(self, query: str, params_list: list[tuple[Any, ...]]) -> None: ...
