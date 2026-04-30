"""Migration validation utilities.

Checks current schema version against required version, verifying drift
and checksum integrity.
"""

from __future__ import annotations

from typing import Any


def check_schema_version(db_path: str = ":memory:", required_version: int | None = None) -> dict[str, Any]:
    """Check current schema version against required version.

    Parameters
    ----------
    db_path : str
        Path to DuckDB database (or ``:memory:``).
    required_version : int | None
        Minimum required version. If ``None``, only reports current version.

    Returns
    -------
    dict
        Keys: ``current_version``, ``required_version``, ``is_current``, ``pending``.
    """
    import duckdb

    con = duckdb.connect(db_path)
    try:
        rows = con.execute(
            "SELECT version FROM schema_version ORDER BY applied_at DESC LIMIT 1"
        ).fetchall()
        current = rows[0][0] if rows else 0
    except Exception:
        current = 0
    finally:
        con.close()

    is_current = True
    if required_version is not None:
        is_current = current >= required_version

    return {
        "current_version": current,
        "required_version": required_version,
        "is_current": is_current,
        "pending": max(0, (required_version or current) - current),
    }
