"""Auto-migration engine: additive migrations from Pydantic schema models.

Generates ALTER TABLE ADD COLUMN statements from registered Pydantic models
to keep the database schema in sync with code definitions.
"""

from __future__ import annotations

from trade_advisor.infra.migrate import MigrationRunner


def run_auto_migrations(db_path: str = ":memory:") -> list[str]:
    """Run additive (non-destructive) migrations from Pydantic models.

    Parameters
    ----------
    db_path : str
        Path to DuckDB database (or ``:memory:``).

    Returns
    -------
    list[str]
        List of applied migration descriptions.
    """
    import asyncio

    async def _run() -> list[str]:
        from trade_advisor.core.config import DatabaseConfig
        from trade_advisor.infra.db import DatabaseManager

        config = DatabaseConfig(path=db_path)
        db = DatabaseManager(config)
        async with db:
            runner = MigrationRunner(db)
            applied = await runner.run_pending()
            return [m.description for m in applied]

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, _run()).result()
    else:
        return asyncio.run(_run())
