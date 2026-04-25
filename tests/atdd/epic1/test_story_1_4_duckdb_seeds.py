"""ATDD red-phase: Story 1.4 — DuckDB Infrastructure & Seed Hierarchy.

All tests are SKIPPED (TDD red phase). Remove when implementing Story 1.4.
"""

from __future__ import annotations

import pytest


class TestStory14DuckDB:
    """Story 1.4: DuckDB lifecycle, WAL mode, write serialization, seeds."""

    @pytest.mark.skip(reason="ATDD red phase — Story 1.4 not implemented")
    async def test_duckdb_wal_mode(self, tmp_path):
        from trade_advisor.core.config import DatabaseConfig
        from trade_advisor.infra.db import DatabaseManager

        config = DatabaseConfig(path=tmp_path / "test.db", wal_mode=True)
        async with DatabaseManager(config) as db:
            import os

            wal_path = str(config.path) + ".wal"
            await db.write(
                "INSERT INTO data_sources (name, provider_type) VALUES (?, ?)",
                ("_probe", "test"),
            )
            assert os.path.exists(wal_path)

    @pytest.mark.skip(reason="ATDD red phase — Story 1.4 not implemented")
    async def test_duckdb_core_tables_created(self):
        from trade_advisor.core.config import DatabaseConfig
        from trade_advisor.infra.db import DatabaseManager

        config = DatabaseConfig(path=":memory:", wal_mode=False)
        async with DatabaseManager(config) as db:
            rows = await db.read("SELECT table_name FROM information_schema.tables")
            tables = {r[0] for r in rows}
            assert "ohlcv_cache" in tables
            assert "experiments" in tables
            assert "data_sources" in tables

    @pytest.mark.skip(reason="ATDD red phase — Story 1.4 not implemented")
    async def test_duckdb_write_serialization_with_lock(self):
        from trade_advisor.core.config import DatabaseConfig
        from trade_advisor.infra.db import DatabaseManager, _ReaderWriterLock

        config = DatabaseConfig(path=":memory:", wal_mode=False)
        async with DatabaseManager(config) as db:
            assert isinstance(db._rw_lock, _ReaderWriterLock)

    @pytest.mark.skip(reason="ATDD red phase — Story 1.4 not implemented")
    async def test_duckdb_shutdown_cleanup(self):
        from trade_advisor.core.config import DatabaseConfig
        from trade_advisor.infra.db import DatabaseManager

        config = DatabaseConfig(path=":memory:", wal_mode=False)
        mgr = DatabaseManager(config)
        async with mgr:
            await mgr.read("SELECT 1")
        await mgr.close()

    @pytest.mark.skip(reason="ATDD red phase — Story 1.4 not implemented")
    def test_seed_manager_hierarchy(self):
        from trade_advisor.infra.seed import SeedManager

        sm = SeedManager(global_seed=42)
        child1 = sm.derive_experiment_seed("exp_001")
        child2 = sm.derive_experiment_seed("exp_002")
        assert child1 != child2

    @pytest.mark.skip(reason="ATDD red phase — Story 1.4 not implemented")
    def test_seed_determinism_bitwise_identical(self):
        """Same global seed => same child seeds => bitwise identical."""
        from trade_advisor.infra.seed import SeedManager

        sm1 = SeedManager(global_seed=42)
        sm2 = SeedManager(global_seed=42)

        assert sm1.derive_experiment_seed("exp_001") == sm2.derive_experiment_seed("exp_001")
        assert sm1.derive_cv_fold_seed("exp_001", 0) == sm2.derive_cv_fold_seed("exp_001", 0)
        assert (
            sm1.derive_augmentation_seed("exp_001", 0, 0)
            == sm2.derive_augmentation_seed("exp_001", 0, 0)
        )

    @pytest.mark.skip(reason="ATDD red phase — Story 1.4 not implemented")
    def test_seed_hierarchy_levels(self):
        from trade_advisor.infra.seed import SeedManager

        sm = SeedManager(global_seed=42)
        global_s = sm.global_seed
        exp_s = sm.derive_experiment_seed("exp_001")
        cv_s = sm.derive_cv_fold_seed("exp_001", 0)
        aug_s = sm.derive_augmentation_seed("exp_001", 0, 0)
        assert len({global_s, exp_s, cv_s, aug_s}) == 4

    @pytest.mark.skip(reason="ATDD red phase — Story 1.4 not implemented")
    def test_task_runner_protocol(self):
        from trade_advisor.infra.tasks import TaskRunner

        assert TaskRunner is not None

    @pytest.mark.skip(reason="ATDD red phase — Story 1.4 not implemented")
    async def test_experiments_table_schema(self):
        from trade_advisor.core.config import DatabaseConfig
        from trade_advisor.infra.db import DatabaseManager

        config = DatabaseConfig(path=":memory:", wal_mode=False)
        async with DatabaseManager(config) as db:
            rows = await db.read(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'experiments'"
            )
            cols = {r[0] for r in rows}
            assert "run_id" in cols
            assert "config_hash" in cols
            assert "strategy" in cols
            assert "metrics_json" in cols

    @pytest.mark.skip(reason="ATDD red phase — Story 1.4 not implemented")
    async def test_ohlcv_cache_table_schema(self):
        from trade_advisor.core.config import DatabaseConfig
        from trade_advisor.infra.db import DatabaseManager

        config = DatabaseConfig(path=":memory:", wal_mode=False)
        async with DatabaseManager(config) as db:
            rows = await db.read(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'ohlcv_cache'"
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
                "volume",
            ):
                assert required in cols, f"ohlcv_cache missing column: {required}"
