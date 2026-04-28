"""Schema migration framework for DuckDB — C+A hybrid approach.

Additive migrations are auto-generated from registered Pydantic schema models
(``SCHEMA_MODELS``). Destructive migrations come from numbered SQL scripts in
``migrations/manual/``. The framework validates schema shape on startup, detects
drift, and auto-fixes additive discrepancies.

Version contract
----------------
- Version 1 is the initial bootstrap applied by ``_SCHEMA_SQL`` in ``db.py``.
- ``schema_version`` stores ``(version, applied_at, description, checksum)``.
- Migrations apply in strict ascending order; gaps raise ``IntegrityError``.
- SHA-256 checksums are verified on startup — tampered scripts raise
  ``IntegrityError``.
- Manual migrations own their declared version (from filename). Additive
  migrations are assigned contiguous versions starting from ``current + 1``.
  If a manual migration claims a version that an additive migration would
  receive, ``_check_collisions`` raises a ``ConfigurationError``.

Lock-free startup
-----------------
``MigrationRunner`` does NOT acquire the DatabaseManager write lock. It is safe
because ``__aenter__`` is single-threaded and no concurrent access is possible
until the database reaches the OPEN state.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import logging
import re
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol, Union, get_args, get_origin

import duckdb
from pydantic import BaseModel
from pydantic_core import PydanticUndefined

from trade_advisor.core.errors import ConfigurationError, IntegrityError

log = logging.getLogger("trade_advisor.infra.migrate")

_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"
_MANUAL_DIR = _MIGRATIONS_DIR / "manual"

_VALID_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

SCHEMA_MODELS: list[type[BaseModel]] = []


class MigrationRecord(BaseModel):
    version: int
    applied_at: datetime
    description: str
    checksum: str


class MigrationResult(BaseModel):
    applied: list[MigrationRecord] = []
    current_version: int = 0
    warnings: list[str] = []


class MigrationProtocol(Protocol):
    version: int
    description: str

    def apply(self, conn: duckdb.DuckDBPyConnection) -> None: ...


class AdditiveMigration:
    def __init__(self, version: int, description: str, sql: str) -> None:
        self.version = version
        self.description = description
        self._sql = sql

    def apply(self, conn: duckdb.DuckDBPyConnection) -> None:
        conn.execute(self._sql)

    @property
    def sql(self) -> str:
        return self._sql


class DestructiveMigration:
    def __init__(self, version: int, description: str, sql: str) -> None:
        if version < 1:
            raise ConfigurationError(f"Migration version must be >= 1, got {version}")
        if not sql.strip():
            raise ConfigurationError(f"Destructive migration v{version} has empty SQL")
        self.version = version
        self.description = description
        self._sql = sql

    def apply(self, conn: duckdb.DuckDBPyConnection) -> None:
        conn.execute(self._sql)

    @property
    def sql(self) -> str:
        return self._sql


_TYPE_MAP: dict[type, str] = {
    str: "TEXT",
    int: "INTEGER",
    float: "DOUBLE",
    Decimal: "DOUBLE",
    bool: "BOOLEAN",
}

_TIMEDELTA_TYPE = "BIGINT"


def _validate_identifier(name: str, kind: str) -> None:
    if not _VALID_IDENTIFIER_RE.match(name):
        raise ConfigurationError(f"Invalid SQL identifier for {kind}: {name!r}")


def _escape_default_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _resolve_optional(annotation: Any) -> tuple[Any, bool]:

    origin = get_origin(annotation)

    if origin is Union:
        args = [a for a in get_args(annotation) if a is not type(None)]
        if len(args) == 1 and type(None) in get_args(annotation):
            inner = args[0]
            inner_origin = get_origin(inner)
            if inner_origin is Union:
                return _resolve_optional(inner)
            return inner, True
        return annotation, False

    if isinstance(annotation, type) and annotation is not type(None):
        return annotation, False

    if hasattr(annotation, "__args__"):
        args = [a for a in annotation.__args__ if a is not type(None)]
        none_args = [a for a in annotation.__args__ if a is type(None)]
        if len(args) == 1 and none_args:
            inner = args[0]
            inner_origin = get_origin(inner)
            if inner_origin is Union:
                return _resolve_optional(inner)
            return inner, True

    return annotation, False


def _pydantic_field_to_sql(field_info: Any) -> str:
    from datetime import timedelta as _td

    from pydantic import AwareDatetime

    annotation = field_info.annotation
    actual_type, is_optional = _resolve_optional(annotation)

    if actual_type in (datetime, AwareDatetime):
        sql_type = "TIMESTAMPTZ"
    elif actual_type is _td:
        sql_type = _TIMEDELTA_TYPE
    elif actual_type in _TYPE_MAP:
        sql_type = _TYPE_MAP[actual_type]
    elif isinstance(actual_type, type) and issubclass(actual_type, datetime):
        sql_type = "TIMESTAMPTZ"
    else:
        raise ConfigurationError(f"Unsupported Pydantic field type: {actual_type}")

    if is_optional:
        sql_type += " NULL"
    elif not is_optional:
        sql_type += " NOT NULL"

    default = getattr(field_info, "default", None)
    if default is not None and default is not PydanticUndefined and default is not ...:
        if isinstance(default, bool):
            sql_type += f" DEFAULT {'TRUE' if default else 'FALSE'}"
        elif isinstance(default, str):
            sql_type += f" DEFAULT {_escape_default_string(default)}"
        elif isinstance(default, (int, float, Decimal)):
            sql_type += f" DEFAULT {default}"
        elif isinstance(default, _td):
            sql_type += f" DEFAULT {int(default.total_seconds() * 1_000_000)}"
        else:
            sql_type += f" DEFAULT {_escape_default_string(str(default))}"

    return sql_type


def _column_exists(conn: duckdb.DuckDBPyConnection, table_name: str, column_name: str) -> bool:
    result = conn.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = ? AND column_name = ?",
        [table_name, column_name],
    ).fetchall()
    return len(result) > 0


def _table_exists(conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    result = conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_name = ?",
        [table_name],
    ).fetchall()
    return len(result) > 0


def _pydantic_to_create_table(model: type[BaseModel]) -> str:
    table_name = getattr(model, "__table_name__", None)
    if not table_name:
        raise ConfigurationError(f"Schema model {model.__name__} missing __table_name__")
    _validate_identifier(table_name, "table")

    columns: list[str] = []
    for field_name, field_info in model.model_fields.items():
        _validate_identifier(field_name, "column")
        sql_type = _pydantic_field_to_sql(field_info)
        columns.append(f"    {field_name} {sql_type}")

    if not columns:
        raise ConfigurationError(
            f"Schema model {model.__name__} has no fields — cannot generate CREATE TABLE"
        )

    cols_sql = ",\n".join(columns)
    return f"CREATE TABLE IF NOT EXISTS {table_name} (\n{cols_sql}\n)"


def _pydantic_to_alter_table(model: type[BaseModel], conn: duckdb.DuckDBPyConnection) -> list[str]:
    table_name = getattr(model, "__table_name__", None)
    if not table_name:
        raise ConfigurationError(f"Schema model {model.__name__} missing __table_name__")
    _validate_identifier(table_name, "table")

    statements: list[str] = []
    for field_name, field_info in model.model_fields.items():
        if not _column_exists(conn, table_name, field_name):
            _validate_identifier(field_name, "column")
            sql_type = _pydantic_field_to_sql(field_info)
            sql_type = sql_type.replace(" NOT NULL", "").replace(" NULL", "")
            statements.append(f"ALTER TABLE {table_name} ADD COLUMN {field_name} {sql_type}")

    type_mismatches = _detect_type_mismatches(model, conn)
    if type_mismatches:
        details = "; ".join(type_mismatches)
        raise ConfigurationError(
            f"Schema type mismatch for {table_name} — manual migration required: {details}. "
            f"Create a numbered SQL script in migrations/manual/ to resolve."
        )

    return statements


def _detect_type_mismatches(model: type[BaseModel], conn: duckdb.DuckDBPyConnection) -> list[str]:
    table_name = getattr(model, "__table_name__", "")
    if not table_name or not _table_exists(conn, table_name):
        return []
    type_map = {
        "INTEGER": {"INTEGER", "BIGINT", "SMALLINT", "TINYINT"},
        "DOUBLE": {"DOUBLE", "FLOAT", "REAL"},
        "TEXT": {"TEXT", "VARCHAR"},
        "BOOLEAN": {"BOOLEAN", "BOOL"},
        "TIMESTAMPTZ": {"TIMESTAMPTZ", "TIMESTAMP", "TIMESTAMP WITH TIME ZONE"},
        "BIGINT": {"BIGINT", "INTEGER"},
    }
    mismatches: list[str] = []
    rows = conn.execute(
        "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = ?",
        [table_name],
    ).fetchall()
    db_types = {r[0]: r[1] for r in rows}
    for field_name, field_info in model.model_fields.items():
        if field_name not in db_types:
            continue
        expected_sql = _pydantic_field_to_sql(field_info).split()[0]
        actual_db_type = db_types[field_name]
        compatible = type_map.get(expected_sql, {expected_sql})
        if actual_db_type not in compatible:
            mismatches.append(f"{field_name}: model={expected_sql}, db={actual_db_type}")
    return mismatches


def _compute_checksum(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


class MigrationRunner:
    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn
        self._manual_dir = _MANUAL_DIR

    def _get_current_version(self) -> int:
        if not _table_exists(self._conn, "schema_version"):
            return 0
        rows = self._conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version").fetchall()
        return rows[0][0] if rows else 0

    def _get_pending_migrations(self) -> list[MigrationProtocol]:
        current = self._get_current_version()

        manual_migrations = self._load_manual_scripts() if self._manual_dir.exists() else []
        manual_versions = {m.version for m in manual_migrations}

        additive_migrations: list[MigrationProtocol] = []
        for model in SCHEMA_MODELS:
            table_name = getattr(model, "__table_name__", "")
            if not table_name:
                continue
            if _table_exists(self._conn, table_name):
                alter_stmts = _pydantic_to_alter_table(model, self._conn)
                if alter_stmts:
                    sql = ";\n".join(alter_stmts)
                    additive_migrations.append(
                        AdditiveMigration(
                            version=0,
                            description=f"add columns to {table_name}",
                            sql=sql,
                        )
                    )
            else:
                sql = _pydantic_to_create_table(model)
                additive_migrations.append(
                    AdditiveMigration(
                        version=0,
                        description=f"create table {table_name}",
                        sql=sql,
                    )
                )

        additive_versions = self._assign_additive_versions(
            current, manual_versions, len(additive_migrations)
        )
        for i, migration in enumerate(additive_migrations):
            migration.version = additive_versions[i]

        all_migrations: list[MigrationProtocol] = additive_migrations + manual_migrations
        all_migrations.sort(key=lambda m: m.version)

        self._check_collisions(all_migrations)
        pending = [m for m in all_migrations if m.version > current]
        self._check_contiguous(pending, current)

        return pending

    @staticmethod
    def _assign_additive_versions(current: int, manual_versions: set[int], count: int) -> list[int]:
        if count == 0:
            return []
        return [current + 1 + i for i in range(count)]

    @staticmethod
    def _check_collisions(migrations: list[MigrationProtocol]) -> None:
        seen: dict[int, str] = {}
        for m in migrations:
            if m.version in seen:
                raise ConfigurationError(
                    f"Migration version collision at version {m.version}: "
                    f"'{seen[m.version]}' and '{m.description}' both claim v{m.version}. "
                    f"Rename the manual migration or adjust SCHEMA_MODELS.",
                    details={"version": m.version},
                )
            seen[m.version] = m.description

    @staticmethod
    def _check_contiguous(migrations: list[MigrationProtocol], current: int = 0) -> None:
        if not migrations:
            return
        versions = sorted(m.version for m in migrations)
        if versions[0] != current + 1:
            raise ConfigurationError(
                f"First pending migration v{versions[0]} does not follow current v{current}. "
                f"Expected v{current + 1}. Rename or renumber the manual migration."
            )
        for i in range(len(versions) - 1):
            if versions[i + 1] != versions[i] + 1:
                raise ConfigurationError(
                    f"Non-contiguous migration versions: {versions[i]} → {versions[i + 1]}. "
                    f"Migrations must form a contiguous sequence starting from current+1. "
                    f"Rename the manual migration to version {versions[i] + 1}."
                )

    def _load_manual_scripts(self) -> list[MigrationProtocol]:
        migrations: list[MigrationProtocol] = []
        pattern = re.compile(r"^(\d+)_.+\.sql$")
        if not self._manual_dir.exists():
            return migrations
        for path in sorted(self._manual_dir.iterdir()):
            if not path.is_file():
                continue
            match = pattern.match(path.name)
            if not match:
                continue
            version = int(match.group(1))
            sql = path.read_text(encoding="utf-8")
            parts = path.stem.split("_", 1)
            desc = parts[1] if len(parts) > 1 and parts[1] else f"migration_{version}"
            migrations.append(DestructiveMigration(version=version, description=desc, sql=sql))
            _validate_manual_sql(sql, path.name)
        return migrations

    def _apply_migration(self, migration: MigrationProtocol) -> MigrationRecord:
        version = migration.version
        desc = migration.description
        sql_content = migration.sql if hasattr(migration, "sql") else ""
        checksum = _compute_checksum(sql_content) if sql_content else ""
        applied_at = datetime.now(UTC)

        try:
            self._conn.execute("BEGIN TRANSACTION")
            migration.apply(self._conn)
            self._conn.execute(
                "INSERT INTO schema_version (version, applied_at, description, checksum) "
                "VALUES (?, ?, ?, ?)",
                [version, applied_at, desc, checksum],
            )
            self._conn.execute("COMMIT")
        except Exception as exc:
            with contextlib.suppress(duckdb.Error):
                self._conn.execute("ROLLBACK")
            raise ConfigurationError(
                f"Migration v{version} ({desc}) failed: {exc}",
                details={"version": version, "description": desc},
            ) from exc

        return MigrationRecord(
            version=version,
            applied_at=applied_at,
            description=desc,
            checksum=checksum,
        )

    def _verify_checksums(self) -> None:
        if not _table_exists(self._conn, "schema_version"):
            return
        try:
            rows = self._conn.execute(
                "SELECT version, checksum, description FROM schema_version ORDER BY version"
            ).fetchall()
        except duckdb.Error:
            return

        manual_migrations = self._load_manual_scripts() if self._manual_dir.exists() else []
        manual_by_version = {m.version: m for m in manual_migrations}

        for version, stored_checksum, desc in rows:
            if version == 1:
                continue
            if not stored_checksum:
                continue

            if version in manual_by_version:
                migration = manual_by_version[version]
                sql_content = migration.sql if hasattr(migration, "sql") else ""
                actual_checksum = _compute_checksum(sql_content) if sql_content else ""
                if actual_checksum and stored_checksum != actual_checksum:
                    raise IntegrityError(
                        f"Checksum mismatch for migration v{version} ({desc}): "
                        f"stored={stored_checksum}, actual={actual_checksum}",
                        details={"version": version},
                    )

    def _detect_gaps(self) -> None:
        if not _table_exists(self._conn, "schema_version"):
            return
        rows = self._conn.execute("SELECT version FROM schema_version ORDER BY version").fetchall()
        if not rows:
            return
        versions = [r[0] for r in rows]
        for i in range(len(versions) - 1):
            if versions[i + 1] != versions[i] + 1:
                raise IntegrityError(
                    f"Version gap detected: {versions[i]} → {versions[i + 1]}",
                    details={"versions": versions},
                )

    def _validate_schema(self) -> list[str]:
        warnings: list[str] = []
        for model in SCHEMA_MODELS:
            table_name = getattr(model, "__table_name__", "")
            if not table_name:
                continue
            if not _table_exists(self._conn, table_name):
                warnings.append(f"Missing table detected: {table_name}")
                continue
            for field_name, _field_info in model.model_fields.items():
                if not _column_exists(self._conn, table_name, field_name):
                    warnings.append(f"Missing column detected: {table_name}.{field_name}")
        return warnings

    def run(self) -> MigrationResult:
        result = MigrationResult()

        self._detect_gaps()
        self._verify_checksums()

        for _pass in range(3):
            pending = self._get_pending_migrations()
            if not pending:
                break

            for migration in pending:
                record = self._apply_migration(migration)
                result.applied.append(record)

            result.warnings.clear()
            result.warnings.extend(self._validate_schema())

        result.current_version = self._get_current_version()
        return result


def _validate_manual_sql(sql: str, filename: str) -> None:
    if re.search(r"\bBEGIN\b", sql, re.IGNORECASE) or re.search(r"\bCOMMIT\b", sql, re.IGNORECASE):
        raise ConfigurationError(
            f"Manual migration {filename} contains BEGIN/COMMIT — "
            f"the migration runner wraps all scripts in a transaction. "
            f"Remove BEGIN/COMMIT from the script."
        )


def run_migrations_sync(conn: duckdb.DuckDBPyConnection) -> MigrationResult:
    if conn is None:
        raise ConfigurationError("Cannot run migrations on a None connection")
    runner = MigrationRunner(conn)
    return runner.run()


async def main() -> None:
    from trade_advisor.core.config import DatabaseConfig
    from trade_advisor.infra.db import DatabaseManager

    config = DatabaseConfig()
    async with DatabaseManager(config) as db:
        if db._conn is None:
            raise ConfigurationError("Database connection not available")
        rows = db._conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version").fetchall()
        current_version = rows[0][0] if rows else 0
        applied_rows = db._conn.execute(
            "SELECT version, description FROM schema_version ORDER BY version"
        ).fetchall()

    print(f"Current version: {current_version}")
    print(f"Total migrations: {len(applied_rows)}")
    for version, desc in applied_rows:
        print(f"  v{version}: {desc}")
    if len(applied_rows) == 1:
        print("No pending migrations.")


if __name__ == "__main__":
    asyncio.run(main())
