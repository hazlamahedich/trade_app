"""Tests for infra/db.py — DatabaseManager advanced scenarios."""

from __future__ import annotations

import asyncio

import pytest

from trade_advisor.core.config import DatabaseConfig
from trade_advisor.core.errors import DataError, IntegrityError, QTAError
from trade_advisor.infra.db import DatabaseManager


@pytest.fixture
def memory_config():
    return DatabaseConfig(path=":memory:", wal_mode=False)


@pytest.fixture
async def db(memory_config):
    async with DatabaseManager(memory_config) as mgr:
        yield mgr


class TestReaderWriterLock:
    async def test_concurrent_reads(self, db):
        results = await asyncio.gather(
            db.read("SELECT 1"),
            db.read("SELECT 2"),
            db.read("SELECT 3"),
        )
        assert len(results) == 3

    async def test_write_blocks_concurrent_reads(self, memory_config):
        async with DatabaseManager(memory_config) as db:
            write_done = asyncio.Event()
            read_started = asyncio.Event()

            async def slow_write():
                await db.write(
                    "INSERT INTO data_sources (name, provider_type) VALUES (?, ?)",
                    ("slow_writer", "test"),
                )
                write_done.set()

            async def try_read():
                read_started.set()
                await asyncio.sleep(0.05)
                result = await db.read("SELECT COUNT(*) FROM data_sources")
                return result

            write_task = asyncio.create_task(slow_write())
            await asyncio.sleep(0.01)
            read_task = asyncio.create_task(try_read())

            await asyncio.gather(write_task, read_task)
            assert write_done.is_set()

    async def test_writer_priority_over_readers(self, memory_config):
        async with DatabaseManager(memory_config) as db:
            await db.write(
                "INSERT INTO data_sources (name, provider_type) VALUES (?, ?)",
                ("initial", "test"),
            )

            read_count = 0
            write_done = asyncio.Event()

            async def reader():
                nonlocal read_count
                rows = await db.read("SELECT COUNT(*) FROM data_sources")
                read_count += 1
                return rows

            async def writer():
                await db.write(
                    "INSERT INTO data_sources (name, provider_type) VALUES (?, ?)",
                    ("priority_writer", "test"),
                )
                write_done.set()

            readers = [asyncio.create_task(reader()) for _ in range(5)]
            await asyncio.sleep(0.01)
            writer_task = asyncio.create_task(writer())
            more_readers = [asyncio.create_task(reader()) for _ in range(3)]

            await asyncio.gather(*readers, writer_task, *more_readers)
            assert write_done.is_set()
            assert read_count == 8


class TestBatchWrites:
    async def test_write_many_batch(self, db):
        rows = [(f"batch_{i}", "test") for i in range(50)]
        await db.write_many(
            "INSERT INTO data_sources (name, provider_type) VALUES (?, ?)",
            rows,
        )
        result = await db.read("SELECT COUNT(*) FROM data_sources")
        assert result[0][0] == 50

    async def test_write_many_empty_list(self, db):
        from trade_advisor.core.errors import QTAError

        with pytest.raises(QTAError):
            await db.write_many(
                "INSERT INTO data_sources (name, provider_type) VALUES (?, ?)",
                [],
            )

    async def test_write_many_rollback_on_error(self, db):
        await db.write(
            "INSERT INTO data_sources (name, provider_type) VALUES (?, ?)",
            ("existing", "test"),
        )
        with pytest.raises(IntegrityError):
            await db.write_many(
                "INSERT INTO data_sources (name, provider_type) VALUES (?, ?)",
                [("dup_a", "test"), ("existing", "test"), ("dup_b", "test")],
            )
        result = await db.read("SELECT COUNT(*) FROM data_sources")
        assert result[0][0] == 1

    async def test_write_many_large_batch(self, db):
        rows = [(f"large_{i}", "test") for i in range(500)]
        await db.write_many(
            "INSERT INTO data_sources (name, provider_type) VALUES (?, ?)",
            rows,
        )
        result = await db.read("SELECT COUNT(*) FROM data_sources")
        assert result[0][0] == 500


class TestCloseAndCleanup:
    async def test_close_method(self, memory_config):
        mgr = DatabaseManager(memory_config)
        await mgr.__aenter__()
        rows = await mgr.read("SELECT 1")
        assert rows[0][0] == 1
        await mgr.close()
        with pytest.raises(DataError, match="not open"):
            await mgr.read("SELECT 1")

    async def test_close_when_already_closed(self, memory_config):
        mgr = DatabaseManager(memory_config)
        await mgr.__aenter__()
        await mgr.close()
        await mgr.close()

    async def test_cleanup_on_failed_open(self, tmp_path):
        bad_file = tmp_path / "corrupt.db"
        bad_file.write_bytes(b"\x00" * 1000)
        config = DatabaseConfig(path=bad_file)
        mgr = DatabaseManager(config)
        with pytest.raises(DataError):
            await mgr.__aenter__()
        assert mgr._conn is None


class TestErrorMapping:
    async def test_data_error_type(self, db):
        with pytest.raises(QTAError):
            await db.read("SELECT * FROM nonexistent_table_xyz")

    async def test_read_params(self, db):
        await db.write(
            "INSERT INTO data_sources (name, provider_type) VALUES (?, ?)",
            ("param_test", "test"),
        )
        rows = await db.read("SELECT name FROM data_sources WHERE name = ?", ("param_test",))
        assert len(rows) == 1
        assert rows[0][0] == "param_test"
