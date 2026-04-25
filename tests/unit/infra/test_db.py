"""Tests for infra/db.py — DuckDB lifecycle manager."""

from __future__ import annotations

import asyncio

import pytest

from trade_advisor.core.config import DatabaseConfig
from trade_advisor.core.errors import DataError, IntegrityError, QTAError
from trade_advisor.infra.db import DatabaseManager


@pytest.fixture
def db_config(tmp_path):
    return DatabaseConfig(path=tmp_path / "test.db", wal_mode=True)


@pytest.fixture
def memory_config():
    return DatabaseConfig(path=":memory:", wal_mode=False)


@pytest.fixture
async def db(memory_config):
    async with DatabaseManager(memory_config) as mgr:
        yield mgr


class TestSchemaCreation:
    async def test_db_manager_creates_schema(self, db):
        rows = await db.read("SELECT table_name FROM information_schema.tables")
        tables = {r[0] for r in rows}
        for expected in ("schema_version", "ohlcv_cache", "experiments", "data_sources"):
            assert expected in tables, f"Missing table: {expected}"

    async def test_db_manager_schema_version_inserted(self, db):
        rows = await db.read("SELECT version, description FROM schema_version")
        assert len(rows) == 1
        assert rows[0][0] == 1
        assert rows[0][1] == "initial schema"

    async def test_db_manager_idempotent_schema(self, memory_config):
        async with DatabaseManager(memory_config) as db:
            pass
        async with DatabaseManager(memory_config) as db:
            rows = await db.read("SELECT COUNT(*) FROM schema_version")
            assert rows[0][0] == 1

    async def test_schema_ohlcv_all_columns(self, db):
        rows = await db.read(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'ohlcv_cache'"
        )
        cols = {r[0] for r in rows}
        for required in (
            "symbol",
            "interval",
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "adj_close",
            "volume",
            "source",
            "session_type",
            "split_factor",
            "div_factor",
            "adj_date",
            "created_at",
        ):
            assert required in cols, f"ohlcv_cache missing column: {required}"

    async def test_schema_experiments_all_columns(self, db):
        rows = await db.read(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'experiments'"
        )
        cols = {r[0] for r in rows}
        for required in (
            "run_id",
            "config_hash",
            "strategy",
            "metrics_json",
            "seed",
            "status",
            "parent_run_id",
            "git_commit",
            "data_fingerprint",
            "python_version",
            "package_versions",
            "model_artifact_path",
            "created_at",
            "completed_at",
        ):
            assert required in cols, f"experiments missing column: {required}"

    async def test_schema_data_sources_all_columns(self, db):
        rows = await db.read(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'data_sources'"
        )
        cols = {r[0] for r in rows}
        for required in (
            "name",
            "provider_type",
            "is_active",
            "last_fetch",
            "config_json",
            "rate_limit",
            "supported_intervals",
            "created_at",
        ):
            assert required in cols, f"data_sources missing column: {required}"


class TestWALMode:
    async def test_db_manager_wal_mode(self, tmp_path):
        config = DatabaseConfig(path=tmp_path / "wal_test.db", wal_mode=True)
        async with DatabaseManager(config) as db:
            await db.write(
                "INSERT INTO data_sources (name, provider_type) VALUES (?, ?)",
                ("_wal_probe", "test"),
            )
            await db.read("SELECT name FROM data_sources")
            import os

            wal_path = str(config.path) + ".wal"
            assert os.path.exists(wal_path)

    async def test_db_manager_wal_autocheckpoint(self, tmp_path):
        config = DatabaseConfig(path=tmp_path / "ac_test.db", wal_mode=True)
        async with DatabaseManager(config) as db:
            rows = await db.read("SELECT current_setting('wal_autocheckpoint')")
            assert rows[0][0] is not None


class TestLifecycle:
    async def test_db_manager_in_memory(self, memory_config):
        async with DatabaseManager(memory_config) as db:
            rows = await db.read("SELECT 1")
            assert rows[0][0] == 1

    async def test_db_manager_context_lifecycle(self, memory_config):
        mgr = DatabaseManager(memory_config)
        async with mgr:
            rows = await mgr.read("SELECT 1")
            assert rows[0][0] == 1

    async def test_db_manager_reentry_after_close(self, memory_config):
        mgr = DatabaseManager(memory_config)
        async with mgr:
            await mgr.read("SELECT 1")
        async with mgr:
            rows = await mgr.read("SELECT 1")
            assert rows[0][0] == 1

    async def test_db_manager_double_entry(self, memory_config):
        mgr = DatabaseManager(memory_config)
        async with mgr:
            result = await mgr.__aenter__()
            assert result is mgr

    async def test_db_manager_exit_propagates_exception(self, memory_config):
        mgr = DatabaseManager(memory_config)
        with pytest.raises(ValueError, match="test error"):
            async with mgr:
                raise ValueError("test error")

    async def test_db_manager_close_checkpoint(self, db_config):
        mgr = DatabaseManager(db_config)
        async with mgr:
            await mgr.write(
                "INSERT INTO data_sources (name, provider_type) VALUES (?, ?)",
                ("test_provider", "yahoo"),
            )
        async with DatabaseManager(db_config) as db:
            rows = await db.read("SELECT name FROM data_sources WHERE name = ?", ("test_provider",))
            assert len(rows) == 1


class TestWriteSerialization:
    async def test_db_manager_write_serialization(self, db):
        async def insert_val(val: int):
            await db.write(
                "INSERT INTO data_sources (name, provider_type) VALUES (?, ?)",
                (f"src_{val}", "test"),
            )

        await asyncio.gather(*[insert_val(i) for i in range(10)])
        rows = await db.read("SELECT COUNT(*) FROM data_sources")
        assert rows[0][0] == 10

    async def test_db_manager_read_during_write(self, db):
        await db.write(
            "INSERT INTO data_sources (name, provider_type) VALUES (?, ?)",
            ("initial", "test"),
        )
        read_result = await db.read("SELECT COUNT(*) FROM data_sources")
        assert read_result[0][0] == 1


class TestErrorMapping:
    async def test_db_manager_error_mapping_operational(self, db):
        with pytest.raises(QTAError):
            await db.write("INSERT INTO nonexistent_table_xyz VALUES (1)")

    async def test_db_manager_error_mapping_integrity(self, db):
        await db.write(
            "INSERT INTO data_sources (name, provider_type) VALUES (?, ?)",
            ("dup", "test"),
        )
        with pytest.raises(IntegrityError):
            await db.write(
                "INSERT INTO data_sources (name, provider_type) VALUES (?, ?)",
                ("dup", "test"),
            )

    async def test_db_manager_corrupt_file_raises_data_error(self, tmp_path):
        bad_file = tmp_path / "corrupt.db"
        bad_file.write_bytes(b"\x00\x01\x02\x03not_a_duckdb" * 100)
        config = DatabaseConfig(path=bad_file)
        with pytest.raises(DataError):
            async with DatabaseManager(config):
                pass


class TestNullAdjClose:
    async def test_db_manager_null_adj_close_stored_and_retrieved(self, db):
        await db.write(
            "INSERT INTO ohlcv_cache (symbol, interval, timestamp, open, high, low, close, volume) "
            "VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?)",
            ("SPY", "1d", 100.0, 101.0, 99.0, 100.5, 1000000),
        )
        rows = await db.read("SELECT adj_close FROM ohlcv_cache WHERE symbol = ?", ("SPY",))
        assert rows[0][0] is None


class TestConfigIntegration:
    async def test_db_manager_uses_database_config(self):
        config = DatabaseConfig(path=":memory:", wal_mode=False, backup_path=None)
        async with DatabaseManager(config) as db:
            rows = await db.read("SELECT 1")
            assert rows[0][0] == 1

    async def test_db_read_when_closed_raises(self, memory_config):
        mgr = DatabaseManager(memory_config)
        with pytest.raises(DataError, match="not open"):
            await mgr.read("SELECT 1")

    async def test_db_write_when_closed_raises(self, memory_config):
        mgr = DatabaseManager(memory_config)
        with pytest.raises(DataError, match="not open"):
            await mgr.write("SELECT 1")
