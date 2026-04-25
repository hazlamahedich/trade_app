"""DuckDB lifecycle manager with async write serialization.

Architecture
------------
DuckDB is synchronous. All DuckDB calls go through ``asyncio.to_thread`` so
that the FastAPI async event loop is never blocked.

**Write serialization** — an ``asyncio.Lock`` serializes all writes.  The lock
is acquired in the async context *before* dispatching to
``asyncio.to_thread``; ``asyncio.Lock`` does not work across OS threads.

**Reads** are concurrent — DuckDB WAL mode supports concurrent reads without
the write lock.

Decimal / float boundary
~~~~~~~~~~~~~~~~~~~~~~~~
Prices enter as ``Decimal`` from the caller, get converted to ``float`` for
DuckDB storage (DOUBLE columns), and come back as ``float``.  The caller
(repository / DAO layer, future stories) is responsible for Decimal conversion.
``DatabaseManager`` works with raw Python types.

NULL adj_close semantics
~~~~~~~~~~~~~~~~~~~~~~~~
``ohlcv_cache.adj_close`` is nullable.  ``NULL`` means "corporate actions not
yet applied" — the bar is raw / unadjusted.  ``split_factor`` and
``div_factor`` default to ``1.0`` (no adjustment).  Downstream consumers MUST
handle ``NULL adj_close`` explicitly (impute from close, skip, or flag).

Multi-process write limitation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
DuckDB WAL mode allows concurrent readers but only **one writer** across all
processes.  If both the CLI and Streamlit / FastAPI try to write to the same
DuckDB file, the second writer gets ``duckdb.IOException``.  The application
must use a single-server pattern for writes.

backup_path
~~~~~~~~~~~
``DatabaseConfig.backup_path`` is reserved for future use (Story 2.x).  It is
accepted in the constructor but not consumed.
"""

from __future__ import annotations

import asyncio
import contextlib
import enum
import logging
from typing import Any

import duckdb

from trade_advisor.core.config import DatabaseConfig
from trade_advisor.core.errors import DataError, IntegrityError, QTAError

log = logging.getLogger("trade_advisor.infra.db")

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

CREATE TABLE IF NOT EXISTS ohlcv_cache (
    symbol       TEXT NOT NULL,
    interval     TEXT NOT NULL DEFAULT '1d',
    timestamp    TIMESTAMPTZ NOT NULL,
    open         DOUBLE NOT NULL,
    high         DOUBLE NOT NULL,
    low          DOUBLE NOT NULL,
    close        DOUBLE NOT NULL,
    adj_close    DOUBLE,
    volume       BIGINT NOT NULL,
    source       TEXT NOT NULL DEFAULT 'yahoo',
    session_type TEXT DEFAULT 'regular',
    split_factor DOUBLE DEFAULT 1.0,
    div_factor   DOUBLE DEFAULT 1.0,
    adj_date     TIMESTAMPTZ,
    created_at   TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, interval, timestamp)
);

CREATE TABLE IF NOT EXISTS experiments (
    run_id              TEXT PRIMARY KEY,
    config_hash         TEXT NOT NULL,
    strategy            TEXT NOT NULL,
    metrics_json        TEXT,
    seed                INTEGER NOT NULL,
    status              TEXT NOT NULL DEFAULT 'running',
    parent_run_id       TEXT,
    git_commit          TEXT,
    data_fingerprint    TEXT,
    python_version      TEXT,
    package_versions    TEXT,
    model_artifact_path TEXT,
    created_at          TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    completed_at        TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS data_sources (
    name                TEXT PRIMARY KEY,
    provider_type       TEXT NOT NULL,
    is_active           BOOLEAN DEFAULT TRUE,
    last_fetch          TIMESTAMPTZ,
    config_json         TEXT,
    rate_limit          INTEGER,
    supported_intervals TEXT DEFAULT '1d,1h,5m',
    created_at          TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
"""

_SEED_VERSION_SQL = "INSERT INTO schema_version (version, description) VALUES (1, 'initial schema')"


class _State(enum.Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"


class _ReaderWriterLock:
    """Async reader-writer lock using an asyncio.Condition.

    Readers share concurrent access. Writers get exclusive access.
    Writers are given priority: once a writer is waiting, new readers
    block until the writer completes (write-preferring RW lock).
    """

    def __init__(self) -> None:
        self._cond = asyncio.Condition()
        self._readers = 0
        self._writer = False
        self._waiting_writers = 0

    @contextlib.asynccontextmanager
    async def read(self):
        async with self._cond:
            while self._writer or self._waiting_writers > 0:
                await self._cond.wait()
            self._readers += 1
        try:
            yield
        finally:
            async with self._cond:
                self._readers -= 1
                if self._readers == 0:
                    self._cond.notify_all()

    @contextlib.asynccontextmanager
    async def write(self):
        async with self._cond:
            self._waiting_writers += 1
            while self._writer or self._readers > 0:
                await self._cond.wait()
            self._waiting_writers -= 1
            self._writer = True
        try:
            yield
        finally:
            async with self._cond:
                self._writer = False
                self._cond.notify_all()


class DatabaseManager:
    """Async DuckDB lifecycle manager with write-serialized access.

    State machine::

        CLOSED ──▶ OPEN ──▶ CLOSED
                 ▲          │
                 └──────────┘  (re-entry)

    Usage::

        async with DatabaseManager(config) as db:
            await db.write("INSERT INTO …", params)
            rows = await db.read("SELECT …")
    """

    def __init__(self, config: DatabaseConfig) -> None:
        self._config = config
        self._conn: duckdb.DuckDBPyConnection | None = None
        self._state = _State.CLOSED
        self._rw_lock = _ReaderWriterLock()

    # ── async context manager ────────────────────────────────────────

    async def __aenter__(self) -> DatabaseManager:
        if self._state is _State.OPEN:
            return self
        try:
            self._conn = await asyncio.to_thread(self._open_connection)
            await asyncio.to_thread(self._init_pragmas)
            await asyncio.to_thread(self._init_schema)
            self._state = _State.OPEN
        except duckdb.Error as exc:
            self._cleanup()
            raise DataError(
                f"Failed to open DuckDB at {self._config.path}: {exc}",
                details={"path": str(self._config.path)},
            ) from exc
        except Exception:
            self._cleanup()
            raise
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[override]
        async with self._rw_lock.write():
            try:
                if self._conn is not None:
                    await asyncio.to_thread(self._checkpoint_and_close)
            finally:
                self._state = _State.CLOSED
                self._conn = None

    # ── public API ───────────────────────────────────────────────────

    async def write(self, query: str, params: tuple[Any, ...] | None = None) -> None:
        """Execute a write statement with exclusive access.

        Acquires a write lock that blocks until all active readers finish
        and prevents new readers from starting.
        """
        self._require_open()
        async with self._rw_lock.write():
            await asyncio.to_thread(self._execute, query, params)

    async def read(
        self, query: str, params: tuple[Any, ...] | None = None
    ) -> list[tuple[Any, ...]]:
        """Execute a read query with reader-writer concurrency control.

        Multiple readers can proceed concurrently. A writer blocks until
        all active readers finish, then runs exclusively.
        """
        self._require_open()
        async with self._rw_lock.read():
            return await asyncio.to_thread(self._execute_read, query, params)

    async def close(self) -> None:
        """Checkpoint WAL and close the connection."""
        async with self._rw_lock.write():
            if self._state is _State.OPEN and self._conn is not None:
                try:
                    await asyncio.to_thread(self._checkpoint_and_close)
                finally:
                    self._state = _State.CLOSED
                    self._conn = None

    # ── internal: connection ─────────────────────────────────────────

    def _open_connection(self) -> duckdb.DuckDBPyConnection:
        path = str(self._config.path)
        conn = duckdb.connect(path)
        return conn

    def _init_pragmas(self) -> None:
        assert self._conn is not None
        path = str(self._config.path)
        if path != ":memory:":
            if self._config.wal_mode:
                with contextlib.suppress(duckdb.Error):
                    self._conn.execute("SET enable_external_access=false")
            with contextlib.suppress(duckdb.Error):
                self._conn.execute("SET wal_autocheckpoint='16MB'")
        with contextlib.suppress(duckdb.Error):
            self._conn.execute("SET threads=4")

    def _init_schema(self) -> None:
        assert self._conn is not None
        self._conn.execute(_SCHEMA_SQL)
        with contextlib.suppress(duckdb.IntegrityError):
            self._conn.execute(_SEED_VERSION_SQL)

    # ── internal: execution helpers ──────────────────────────────────

    def _execute(self, query: str, params: tuple[Any, ...] | None) -> None:
        assert self._conn is not None
        try:
            if params:
                self._conn.execute(query, params)
            else:
                self._conn.execute(query)
        except duckdb.Error as exc:
            raise self._map_duckdb_error(exc) from exc

    def _execute_read(self, query: str, params: tuple[Any, ...] | None) -> list[tuple[Any, ...]]:
        assert self._conn is not None
        try:
            result = self._conn.execute(query, params) if params else self._conn.execute(query)
            return result.fetchall()
        except duckdb.Error as exc:
            raise self._map_duckdb_error(exc) from exc

    def _checkpoint_and_close(self) -> None:
        if self._conn is None:
            return
        try:
            self._conn.execute("FORCE CHECKPOINT")
        except duckdb.Error:
            log.warning("WAL checkpoint failed during shutdown", exc_info=True)
        try:
            self._conn.close()
        except duckdb.Error:
            log.warning("DuckDB close failed during shutdown", exc_info=True)

    def _cleanup(self) -> None:
        if self._conn is not None:
            with contextlib.suppress(Exception):
                self._conn.close()
            self._conn = None
        self._state = _State.CLOSED

    # ── internal: state guards ───────────────────────────────────────

    def _require_open(self) -> None:
        if self._state is not _State.OPEN or self._conn is None:
            raise DataError("DatabaseManager is not open")

    # ── internal: error mapping ──────────────────────────────────────

    @staticmethod
    def _map_duckdb_error(exc: duckdb.Error) -> QTAError:
        if isinstance(exc, duckdb.OperationalError):
            return DataError(str(exc), details={"duckdb_type": "OperationalError"})
        if isinstance(exc, duckdb.IntegrityError):
            return IntegrityError(str(exc), details={"duckdb_type": "IntegrityError"})
        if isinstance(exc, duckdb.DataError):
            return DataError(str(exc), details={"duckdb_type": "DataError"})
        if isinstance(exc, duckdb.InternalError):
            return DataError(str(exc), details={"duckdb_type": "InternalError"})
        return QTAError(str(exc), details={"duckdb_type": "Error"})
