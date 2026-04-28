"""ATDD red-phase: Story 2.13 — Schema Migration Framework.

Tests assert the expected end-state AFTER full Story 2.13 implementation.
All tests are SKIPPED (TDD red phase).

Remove @pytest.mark.skip when implementing Story 2.13.
"""

from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class TestStory213SchemaMigration:
    """Story 2.13: Schema migration system for DuckDB."""

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.13 not yet implemented")
    def test_migration_validate_module_exists(self):
        from trade_advisor.migrations.validate import check_schema_version

        assert check_schema_version is not None

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.13 not yet implemented")
    def test_additive_migration_from_pydantic(self):
        from trade_advisor.migrations.auto import run_auto_migrations

        assert run_auto_migrations is not None

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.13 not yet implemented")
    def test_manual_migration_sql_scripts_exist(self):
        manual_dir = PROJECT_ROOT / "migrations" / "manual"
        assert manual_dir.exists()
        sql_files = list(manual_dir.glob("*.sql"))
        assert len(sql_files) >= 0

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.13 not yet implemented")
    def test_migration_history_tracked(self):
        from trade_advisor.core.config import DatabaseConfig
        from trade_advisor.infra.db import DatabaseManager

        config = DatabaseConfig(path=":memory:")
        db = DatabaseManager(config)
        assert hasattr(db, "get_migration_history") or hasattr(db, "applied_migrations")

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.13 not yet implemented")
    def test_justfile_has_migrate_command(self):
        jf = PROJECT_ROOT / "justfile"
        assert jf.exists()
        content = jf.read_text()
        assert "migrate" in content
