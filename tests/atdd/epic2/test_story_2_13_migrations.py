"""ATDD tests: Story 2.13 — Schema Migration Framework.

Tests assert the expected end-state for Story 2.13 implementation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class TestStory213SchemaMigration:
    """Story 2.13: Schema migration system for DuckDB."""

    @pytest.mark.test_id("2.13-ATDD-001")
    @pytest.mark.p2
    def test_migration_validate_module_exists(self):
        from trade_advisor.migrations.validate import check_schema_version

        assert check_schema_version is not None

    @pytest.mark.test_id("2.13-ATDD-002")
    @pytest.mark.p2
    def test_additive_migration_from_pydantic(self):
        from trade_advisor.migrations.auto import run_auto_migrations

        assert run_auto_migrations is not None

    @pytest.mark.test_id("2.13-ATDD-003")
    @pytest.mark.p2
    def test_manual_migration_sql_scripts_exist(self):
        manual_dir = PROJECT_ROOT / "migrations" / "manual"
        assert manual_dir.exists()
        sql_files = list(manual_dir.glob("*.sql"))
        assert len(sql_files) >= 1

    @pytest.mark.test_id("2.13-ATDD-004")
    @pytest.mark.p2
    def test_migration_history_tracked(self):
        from trade_advisor.infra.migrate import MigrationRunner

        assert hasattr(MigrationRunner, "run") or hasattr(MigrationRunner, "run_pending")

    @pytest.mark.test_id("2.13-ATDD-005")
    @pytest.mark.p2
    def test_justfile_has_migrate_command(self):
        jf = PROJECT_ROOT / "justfile"
        assert jf.exists()
        content = jf.read_text()
        assert "migrate" in content
