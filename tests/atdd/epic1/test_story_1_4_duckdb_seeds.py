"""ATDD red-phase: Story 1.4 — DuckDB Infrastructure & Seed Hierarchy.

All tests are SKIPPED (TDD red phase). Remove when implementing Story 1.4.
"""
from __future__ import annotations

import asyncio

import pytest


class TestStory14DuckDB:
    """Story 1.4: DuckDB lifecycle, WAL mode, write serialization, seeds."""

    @pytest.mark.skip(reason="ATDD red phase — Story 1.4 not implemented")
    def test_duckdb_wal_mode(self):
        from trade_advisor.infra.db import get_connection

        conn = get_connection()
        result = conn.execute("PRAGMA journal_mode").fetchone()
        assert result[0].lower() == "wal"

    @pytest.mark.skip(reason="ATDD red phase — Story 1.4 not implemented")
    def test_duckdb_core_tables_created(self):
        from trade_advisor.infra.db import get_connection

        conn = get_connection()
        tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
        assert "ohlcv_cache" in tables
        assert "experiments" in tables
        assert "data_sources" in tables

    @pytest.mark.skip(reason="ATDD red phase — Story 1.4 not implemented")
    def test_duckdb_write_serialization_with_lock(self):
        from trade_advisor.infra.db import get_connection

        conn = get_connection()
        write_lock = asyncio.Lock()
        assert write_lock is not None

    @pytest.mark.skip(reason="ATDD red phase — Story 1.4 not implemented")
    def test_duckdb_shutdown_cleanup(self):
        from trade_advisor.infra.db import shutdown

        shutdown()

    @pytest.mark.skip(reason="ATDD red phase — Story 1.4 not implemented")
    def test_seed_manager_hierarchy(self):
        from trade_advisor.infra.seed import SeedManager

        sm = SeedManager(global_seed=42)
        child1 = sm.experiment_seed("exp_001")
        child2 = sm.experiment_seed("exp_002")
        assert child1 != child2

    @pytest.mark.skip(reason="ATDD red phase — Story 1.4 not implemented")
    def test_seed_determinism_bitwise_identical(self):
        """Same global seed => same child seeds => bitwise identical."""
        from trade_advisor.infra.seed import SeedManager

        sm1 = SeedManager(global_seed=42)
        sm2 = SeedManager(global_seed=42)

        assert sm1.experiment_seed("exp_001") == sm2.experiment_seed("exp_001")
        assert sm1.cv_fold_seed(0) == sm2.cv_fold_seed(0)
        assert sm1.augmentation_seed(0) == sm2.augmentation_seed(0)

    @pytest.mark.skip(reason="ATDD red phase — Story 1.4 not implemented")
    def test_seed_hierarchy_levels(self):
        from trade_advisor.infra.seed import SeedManager

        sm = SeedManager(global_seed=42)
        global_s = sm.global_seed
        exp_s = sm.experiment_seed("exp_001")
        cv_s = sm.cv_fold_seed(0)
        aug_s = sm.augmentation_seed(0)
        assert len({global_s, exp_s, cv_s, aug_s}) == 4

    @pytest.mark.skip(reason="ATDD red phase — Story 1.4 not implemented")
    def test_task_runner_protocol(self):
        from trade_advisor.infra.tasks import TaskRunner

        assert TaskRunner is not None

    @pytest.mark.skip(reason="ATDD red phase — Story 1.4 not implemented")
    def test_experiments_table_schema(self):
        from trade_advisor.infra.db import get_connection

        conn = get_connection()
        cols = {
            row[0]
            for row in conn.execute("DESCRIBE experiments").fetchall()
        }
        assert "run_id" in cols
        assert "config_hash" in cols
        assert "strategy" in cols
        assert "metrics_json" in cols

    @pytest.mark.skip(reason="ATDD red phase — Story 1.4 not implemented")
    def test_ohlcv_cache_table_schema(self):
        from trade_advisor.infra.db import get_connection

        conn = get_connection()
        cols = {
            row[0]
            for row in conn.execute("DESCRIBE ohlcv_cache").fetchall()
        }
        for required in ("symbol", "interval", "timestamp", "open", "high", "low", "close", "volume"):
            assert required in cols, f"ohlcv_cache missing column: {required}"
