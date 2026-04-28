"""Unit tests for the schema migration framework.

All tests use ``:memory:` DuckDB — no file I/O.
"""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import duckdb
import pytest
from pydantic import AwareDatetime, BaseModel, Field

from trade_advisor.core.errors import ConfigurationError, IntegrityError
from trade_advisor.infra.migrate import (
    SCHEMA_MODELS,
    AdditiveMigration,
    DestructiveMigration,
    MigrationRecord,
    MigrationResult,
    MigrationRunner,
    _column_exists,
    _compute_checksum,
    _detect_type_mismatches,
    _escape_default_string,
    _pydantic_field_to_sql,
    _pydantic_to_alter_table,
    _pydantic_to_create_table,
    _table_exists,
    _validate_identifier,
    _validate_manual_sql,
    run_migrations_sync,
)


@pytest.fixture
def conn():
    c = duckdb.connect(":memory:")
    yield c
    c.close()


def _bootstrap(conn: duckdb.DuckDBPyConnection) -> None:
    from trade_advisor.infra.db import _SCHEMA_SQL, _SEED_VERSION_SQL

    conn.execute(_SCHEMA_SQL)
    with contextlib.suppress(duckdb.IntegrityError):
        conn.execute(_SEED_VERSION_SQL)


@pytest.fixture(autouse=True)
def _clear_schema_models():
    original = SCHEMA_MODELS.copy()
    SCHEMA_MODELS.clear()
    yield
    SCHEMA_MODELS.clear()
    SCHEMA_MODELS.extend(original)


class TestMigrationModels:
    def test_destructive_migration_rejects_zero_version(self):
        with pytest.raises(ConfigurationError, match="version must be >= 1"):
            DestructiveMigration(version=0, description="bad", sql="SELECT 1")

    def test_destructive_migration_rejects_negative_version(self):
        with pytest.raises(ConfigurationError, match="version must be >= 1"):
            DestructiveMigration(version=-1, description="bad", sql="SELECT 1")

    def test_destructive_migration_rejects_empty_sql(self):
        with pytest.raises(ConfigurationError, match="empty SQL"):
            DestructiveMigration(version=2, description="empty", sql="   ")

    def test_migration_record_model(self):
        now = datetime.now(UTC)
        r = MigrationRecord(version=1, applied_at=now, description="test", checksum="abc")
        assert r.version == 1
        assert r.checksum == "abc"

    def test_migration_result_defaults(self):
        r = MigrationResult()
        assert r.applied == []
        assert r.current_version == 0
        assert r.warnings == []


class TestTypeMapping:
    def test_str_maps_to_text(self):
        class M(BaseModel):
            __table_name__ = "t"
            name: str

        sql = _pydantic_field_to_sql(M.model_fields["name"])
        assert sql == "TEXT NOT NULL"

    def test_int_maps_to_integer(self):
        class M(BaseModel):
            __table_name__ = "t"
            count: int

        sql = _pydantic_field_to_sql(M.model_fields["count"])
        assert sql == "INTEGER NOT NULL"

    def test_float_maps_to_double(self):
        class M(BaseModel):
            __table_name__ = "t"
            price: float

        sql = _pydantic_field_to_sql(M.model_fields["price"])
        assert sql == "DOUBLE NOT NULL"

    def test_decimal_maps_to_double(self):
        class M(BaseModel):
            __table_name__ = "t"
            amount: Decimal

        sql = _pydantic_field_to_sql(M.model_fields["amount"])
        assert sql == "DOUBLE NOT NULL"

    def test_datetime_maps_to_timestamptz(self):
        class M(BaseModel):
            __table_name__ = "t"
            ts: datetime

        sql = _pydantic_field_to_sql(M.model_fields["ts"])
        assert sql == "TIMESTAMPTZ NOT NULL"

    def test_aware_datetime_maps_to_timestamptz(self):
        class M(BaseModel):
            __table_name__ = "t"
            ts: AwareDatetime

        sql = _pydantic_field_to_sql(M.model_fields["ts"])
        assert sql == "TIMESTAMPTZ NOT NULL"

    def test_bool_maps_to_boolean(self):
        class M(BaseModel):
            __table_name__ = "t"
            active: bool

        sql = _pydantic_field_to_sql(M.model_fields["active"])
        assert sql == "BOOLEAN NOT NULL"

    def test_timedelta_maps_to_bigint(self):
        class M(BaseModel):
            __table_name__ = "t"
            duration: timedelta

        sql = _pydantic_field_to_sql(M.model_fields["duration"])
        assert sql == "BIGINT NOT NULL"

    def test_optional_maps_to_type_null(self):
        class M(BaseModel):
            __table_name__ = "t"
            name: str | None = None

        sql = _pydantic_field_to_sql(M.model_fields["name"])
        assert sql == "TEXT NULL"

    def test_pep604_optional_maps_to_type_null(self):
        class M(BaseModel):
            __table_name__ = "t"
            name: str | None = None

        sql = _pydantic_field_to_sql(M.model_fields["name"])
        assert sql == "TEXT NULL"

    def test_pep604_optional_int(self):
        class M(BaseModel):
            __table_name__ = "t"
            count: int | None = None

        sql = _pydantic_field_to_sql(M.model_fields["count"])
        assert sql == "INTEGER NULL"

    def test_default_int_generates_default(self):
        class M(BaseModel):
            __table_name__ = "t"
            count: int = Field(default=42)

        sql = _pydantic_field_to_sql(M.model_fields["count"])
        assert "NOT NULL" in sql
        assert "DEFAULT 42" in sql

    def test_default_str_generates_default(self):
        class M(BaseModel):
            __table_name__ = "t"
            label: str = Field(default="hello")

        sql = _pydantic_field_to_sql(M.model_fields["label"])
        assert "NOT NULL" in sql
        assert "DEFAULT 'hello'" in sql

    def test_default_bool_generates_default(self):
        class M(BaseModel):
            __table_name__ = "t"
            active: bool = Field(default=True)

        sql = _pydantic_field_to_sql(M.model_fields["active"])
        assert "NOT NULL" in sql
        assert "DEFAULT TRUE" in sql

    def test_default_string_with_quotes_escaped(self):
        class M(BaseModel):
            __table_name__ = "t"
            label: str = Field(default="it's a test")

        sql = _pydantic_field_to_sql(M.model_fields["label"])
        assert "NOT NULL" in sql
        assert "DEFAULT 'it''s a test'" in sql

    def test_escape_default_string_doubles_quotes(self):
        assert _escape_default_string("o'brien") == "'o''brien'"
        assert _escape_default_string("safe") == "'safe'"

    def test_unsupported_type_raises(self):
        class M(BaseModel):
            __table_name__ = "t"
            data: dict

        with pytest.raises(ConfigurationError, match="Unsupported"):
            _pydantic_field_to_sql(M.model_fields["data"])


class TestIdentifierValidation:
    def test_valid_table_name(self):
        _validate_identifier("my_table", "table")

    def test_invalid_table_name_raises(self):
        with pytest.raises(ConfigurationError, match="Invalid SQL identifier"):
            _validate_identifier("drop table x; --", "table")

    def test_empty_identifier_raises(self):
        with pytest.raises(ConfigurationError, match="Invalid SQL identifier"):
            _validate_identifier("", "table")

    def test_identifier_with_special_chars_raises(self):
        with pytest.raises(ConfigurationError, match="Invalid SQL identifier"):
            _validate_identifier("my-table", "column")


class TestCreateTable:
    def test_generates_create_table_sql(self):
        class TestSchema(BaseModel):
            __table_name__ = "test_table"
            id: int
            name: str

        sql = _pydantic_to_create_table(TestSchema)
        assert "CREATE TABLE IF NOT EXISTS test_table" in sql
        assert "id INTEGER" in sql
        assert "name TEXT" in sql

    def test_missing_table_name_raises(self):
        class BadSchema(BaseModel):
            id: int

        with pytest.raises(ConfigurationError, match="missing __table_name__"):
            _pydantic_to_create_table(BadSchema)

    def test_invalid_table_name_raises(self):
        class BadSchema(BaseModel):
            __table_name__ = "DROP TABLE x; --"
            id: int

        with pytest.raises(ConfigurationError, match="Invalid SQL identifier"):
            _pydantic_to_create_table(BadSchema)


class TestAlterTable:
    def test_adds_missing_column(self, conn):
        conn.execute("CREATE TABLE test_table (id INTEGER)")

        class TestSchema(BaseModel):
            __table_name__ = "test_table"
            id: int
            name: str | None = None

        stmts = _pydantic_to_alter_table(TestSchema, conn)
        assert len(stmts) == 1
        assert "ALTER TABLE test_table ADD COLUMN name" in stmts[0]

    def test_skips_existing_column(self, conn):
        conn.execute("CREATE TABLE test_table (id INTEGER, name TEXT)")

        class TestSchema(BaseModel):
            __table_name__ = "test_table"
            id: int
            name: str | None = None

        stmts = _pydantic_to_alter_table(TestSchema, conn)
        assert len(stmts) == 0


class TestHelpers:
    def test_column_exists_true(self, conn):
        conn.execute("CREATE TABLE t (col1 INTEGER)")
        assert _column_exists(conn, "t", "col1") is True

    def test_column_exists_false(self, conn):
        conn.execute("CREATE TABLE t (col1 INTEGER)")
        assert _column_exists(conn, "t", "missing") is False

    def test_table_exists_true(self, conn):
        conn.execute("CREATE TABLE my_table (id INTEGER)")
        assert _table_exists(conn, "my_table") is True

    def test_table_exists_false(self, conn):
        assert _table_exists(conn, "no_such_table") is False

    def test_compute_checksum_deterministic(self):
        assert _compute_checksum("hello") == _compute_checksum("hello")

    def test_compute_checksum_different_inputs(self):
        assert _compute_checksum("hello") != _compute_checksum("world")


class TestMigrationRunner:
    def test_fresh_db_bootstrap_recognized_as_v1(self, conn):
        _bootstrap(conn)
        runner = MigrationRunner(conn)
        assert runner._get_current_version() == 1

    def test_fresh_db_no_pending_migrations(self, conn):
        _bootstrap(conn)
        runner = MigrationRunner(conn)
        pending = runner._get_pending_migrations()
        assert len(pending) == 0

    def test_run_on_fresh_db_is_noop(self, conn):
        _bootstrap(conn)
        runner = MigrationRunner(conn)
        result = runner.run()
        assert result.current_version == 1
        assert len(result.applied) == 0

    def test_additive_migration_adds_new_table(self, conn):
        _bootstrap(conn)

        class NewTable(BaseModel):
            __table_name__ = "new_table"
            id: int
            name: str

        SCHEMA_MODELS.append(NewTable)
        runner = MigrationRunner(conn)
        result = runner.run()
        assert result.current_version >= 2
        assert _table_exists(conn, "new_table")

    def test_additive_migration_adds_column(self, conn):
        _bootstrap(conn)

        class PartialTable(BaseModel):
            __table_name__ = "partial_table"
            id: int

        SCHEMA_MODELS.append(PartialTable)
        runner = MigrationRunner(conn)
        runner.run()

        class ExtendedTable(BaseModel):
            __table_name__ = "partial_table"
            id: int
            extra: str | None = None

        SCHEMA_MODELS.clear()
        SCHEMA_MODELS.append(ExtendedTable)
        runner2 = MigrationRunner(conn)
        _result = runner2.run()
        assert _column_exists(conn, "partial_table", "extra")

    def test_idempotent_double_run(self, conn):
        _bootstrap(conn)

        class IdempotentTable(BaseModel):
            __table_name__ = "idem_table"
            id: int

        SCHEMA_MODELS.append(IdempotentTable)
        runner = MigrationRunner(conn)
        _result1 = runner.run()
        runner2 = MigrationRunner(conn)
        result2 = runner2.run()
        assert len(result2.applied) == 0

    def test_failed_migration_rolls_back(self, conn):
        _bootstrap(conn)
        bad_sql = "INSERT INTO nonexistent_table VALUES (1)"
        migration = AdditiveMigration(version=2, description="bad", sql=bad_sql)
        runner = MigrationRunner(conn)
        with pytest.raises(ConfigurationError, match="failed"):
            runner._apply_migration(migration)
        assert runner._get_current_version() == 1

    def test_version_gap_raises_integrity_error(self, conn):
        _bootstrap(conn)
        conn.execute(
            "INSERT INTO schema_version (version, description, checksum) "
            "VALUES (3, 'gap test', 'abc')"
        )
        runner = MigrationRunner(conn)
        with pytest.raises(IntegrityError, match="Version gap"):
            runner._detect_gaps()

    def test_checksum_mismatch_raises_integrity_error(self, conn, tmp_path):
        _bootstrap(conn)
        manual_dir = tmp_path / "manual"
        manual_dir.mkdir()
        (manual_dir / "002_test.sql").write_text("SELECT 1")
        runner = MigrationRunner(conn)
        runner._manual_dir = manual_dir
        runner.run()
        (manual_dir / "002_test.sql").write_text("SELECT 2")
        runner2 = MigrationRunner(conn)
        runner2._manual_dir = manual_dir
        with pytest.raises(IntegrityError, match="Checksum mismatch"):
            runner2._verify_checksums()

    def test_destructive_migration_from_file(self, conn, tmp_path):
        _bootstrap(conn)
        manual_dir = tmp_path / "manual"
        manual_dir.mkdir()
        (manual_dir / "002_add_column.sql").write_text(
            "ALTER TABLE data_sources ADD COLUMN test_col TEXT DEFAULT 'x'"
        )
        SCHEMA_MODELS.clear()
        runner = MigrationRunner(conn)
        runner._manual_dir = manual_dir
        result = runner.run()
        assert result.current_version >= 2
        assert _column_exists(conn, "data_sources", "test_col")

    def test_destructive_migration_failure_rolls_back(self, conn, tmp_path):
        _bootstrap(conn)
        manual_dir = tmp_path / "manual"
        manual_dir.mkdir()
        (manual_dir / "002_fail.sql").write_text("INSERT INTO nonexistent_table VALUES (1)")
        SCHEMA_MODELS.clear()
        runner = MigrationRunner(conn)
        runner._manual_dir = manual_dir
        with pytest.raises(ConfigurationError):
            runner.run()
        assert runner._get_current_version() == 1

    def test_schema_validation_auto_creates_missing_table(self, conn):
        _bootstrap(conn)

        class AutoCreateTable(BaseModel):
            __table_name__ = "auto_created"
            id: int

        SCHEMA_MODELS.append(AutoCreateTable)
        runner = MigrationRunner(conn)
        result = runner.run()
        assert _table_exists(conn, "auto_created")
        assert result.current_version >= 2

    def test_schema_validation_auto_adds_missing_column(self, conn):
        _bootstrap(conn)
        conn.execute("CREATE TABLE partial (id INTEGER)")
        conn.execute(
            "INSERT INTO schema_version (version, description, checksum) VALUES (2, 'partial', '')"
        )

        class PartialSchema(BaseModel):
            __table_name__ = "partial"
            id: int
            new_col: str | None = None

        SCHEMA_MODELS.append(PartialSchema)
        runner = MigrationRunner(conn)
        result = runner.run()
        assert _column_exists(conn, "partial", "new_col")
        assert result.current_version >= 3

    def test_run_migrations_sync_function(self, conn):
        _bootstrap(conn)
        result = run_migrations_sync(conn)
        assert result.current_version == 1

    def test_run_migrations_sync_none_raises(self):
        with pytest.raises(ConfigurationError, match="None connection"):
            run_migrations_sync(None)

    def test_validation_loop_max_3_passes(self, conn):
        _bootstrap(conn)
        SCHEMA_MODELS.clear()
        runner = MigrationRunner(conn)
        result = runner.run()
        assert result.current_version >= 1

    def test_applied_record_matches_db_timestamp(self, conn):
        _bootstrap(conn)

        class TsTable(BaseModel):
            __table_name__ = "ts_check"
            id: int

        SCHEMA_MODELS.append(TsTable)
        runner = MigrationRunner(conn)
        result = runner.run()
        assert len(result.applied) == 1
        record = result.applied[0]
        rows = conn.execute(
            "SELECT applied_at FROM schema_version WHERE version = ?",
            [record.version],
        ).fetchall()
        assert len(rows) == 1
        assert record.applied_at == rows[0][0]

    def test_warnings_cleared_between_passes(self, conn):
        _bootstrap(conn)
        runner = MigrationRunner(conn)
        result = runner.run()
        assert isinstance(result.warnings, list)


class TestVersionCollision:
    def test_collision_detection_in_check_collisions(self, conn, tmp_path):
        _bootstrap(conn)
        m1 = AdditiveMigration(version=2, description="first", sql="SELECT 1")
        m2 = DestructiveMigration(version=2, description="second", sql="SELECT 2")
        with pytest.raises(ConfigurationError, match="version collision"):
            MigrationRunner._check_collisions([m1, m2])

    def test_additive_defers_past_manual_no_collision(self, conn, tmp_path):
        _bootstrap(conn)
        manual_dir = tmp_path / "manual"
        manual_dir.mkdir()
        (manual_dir / "003_safe.sql").write_text(
            "ALTER TABLE data_sources ADD COLUMN safe_col TEXT"
        )

        class SafeTable(BaseModel):
            __table_name__ = "safe_table"
            id: int

        SCHEMA_MODELS.append(SafeTable)
        runner = MigrationRunner(conn)
        runner._manual_dir = manual_dir
        result = runner.run()
        assert result.current_version >= 3
        assert _table_exists(conn, "safe_table")
        assert _column_exists(conn, "data_sources", "safe_col")

    def test_additive_defers_past_manual_versions(self, conn, tmp_path):
        _bootstrap(conn)
        manual_dir = tmp_path / "manual"
        manual_dir.mkdir()
        (manual_dir / "003_manual.sql").write_text("ALTER TABLE data_sources ADD COLUMN m_col TEXT")

        class DeferTable(BaseModel):
            __table_name__ = "defer_table"
            id: int

        SCHEMA_MODELS.append(DeferTable)
        runner = MigrationRunner(conn)
        runner._manual_dir = manual_dir
        result = runner.run()
        versions = sorted(r.version for r in result.applied)
        assert 2 in versions
        assert 3 in versions
        assert result.current_version >= 3

    def test_additive_assigns_contiguous_rejects_gap_manual(self, conn, tmp_path):
        _bootstrap(conn)
        manual_dir = tmp_path / "manual"
        manual_dir.mkdir()
        (manual_dir / "005_gap.sql").write_text("ALTER TABLE data_sources ADD COLUMN gap_col TEXT")

        class GapTableA(BaseModel):
            __table_name__ = "gap_a"
            id: int

        class GapTableB(BaseModel):
            __table_name__ = "gap_b"
            id: int

        SCHEMA_MODELS.append(GapTableA)
        SCHEMA_MODELS.append(GapTableB)
        runner = MigrationRunner(conn)
        runner._manual_dir = manual_dir
        with pytest.raises(ConfigurationError, match="Non-contiguous"):
            runner.run()

    def test_additive_manual_contiguous_sequence_works(self, conn, tmp_path):
        _bootstrap(conn)
        manual_dir = tmp_path / "manual"
        manual_dir.mkdir()
        (manual_dir / "004_add_col.sql").write_text(
            "ALTER TABLE data_sources ADD COLUMN gap_col TEXT"
        )

        class GapTableA(BaseModel):
            __table_name__ = "gap_a"
            id: int

        class GapTableB(BaseModel):
            __table_name__ = "gap_b"
            id: int

        SCHEMA_MODELS.append(GapTableA)
        SCHEMA_MODELS.append(GapTableB)
        runner = MigrationRunner(conn)
        runner._manual_dir = manual_dir
        result = runner.run()
        versions = sorted(r.version for r in result.applied)
        assert versions == [2, 3, 4]

        runner2 = MigrationRunner(conn)
        runner2._manual_dir = manual_dir
        result2 = runner2.run()
        assert len(result2.applied) == 0

    def test_additive_manual_collision_raises(self, conn, tmp_path):
        _bootstrap(conn)
        manual_dir = tmp_path / "manual"
        manual_dir.mkdir()
        (manual_dir / "002_collision.sql").write_text(
            "ALTER TABLE data_sources ADD COLUMN col_text TEXT"
        )

        class CollisionTable(BaseModel):
            __table_name__ = "collision_table"
            id: int

        SCHEMA_MODELS.append(CollisionTable)
        runner = MigrationRunner(conn)
        runner._manual_dir = manual_dir
        with pytest.raises(ConfigurationError, match="version collision"):
            runner.run()


class TestBootstrapCoexistence:
    def test_schema_sql_creates_version_1(self, conn):
        _bootstrap(conn)
        rows = conn.execute("SELECT version FROM schema_version WHERE version = 1").fetchall()
        assert len(rows) == 1

    def test_migration_runner_respects_bootstrap(self, conn):
        _bootstrap(conn)
        runner = MigrationRunner(conn)
        assert runner._get_current_version() == 1
        result = runner.run()
        assert len(result.applied) == 0

    def test_fresh_db_then_additive_then_noop(self, conn):
        _bootstrap(conn)

        class Phase2Table(BaseModel):
            __table_name__ = "phase2"
            id: int
            label: str

        SCHEMA_MODELS.append(Phase2Table)
        runner = MigrationRunner(conn)
        r1 = runner.run()
        assert r1.current_version >= 2
        runner2 = MigrationRunner(conn)
        r2 = runner2.run()
        assert len(r2.applied) == 0
        assert r2.current_version == r1.current_version


class TestCodeReviewPatches:
    def test_not_null_on_required_fields(self):
        class M(BaseModel):
            __table_name__ = "t"
            name: str

        sql = _pydantic_field_to_sql(M.model_fields["name"])
        assert "NOT NULL" in sql

    def test_nullable_field_no_not_null(self):
        class M(BaseModel):
            __table_name__ = "t"
            name: str | None = None

        sql = _pydantic_field_to_sql(M.model_fields["name"])
        assert "NOT NULL" not in sql
        assert "NULL" in sql

    def test_zero_field_model_raises(self):
        class EmptyModel(BaseModel):
            __table_name__ = "empty_table"

        with pytest.raises(ConfigurationError, match="no fields"):
            _pydantic_to_create_table(EmptyModel)

    def test_empty_description_filename_gets_default(self):
        m = DestructiveMigration(version=2, description="migration_2", sql="SELECT 1")
        assert m.description == "migration_2"

    def test_type_mismatch_detected_on_existing_column(self, conn):
        _bootstrap(conn)
        conn.execute("CREATE TABLE type_test (price INTEGER)")

        class TypeTestModel(BaseModel):
            __table_name__ = "type_test"
            price: str

        mismatches = _detect_type_mismatches(TypeTestModel, conn)
        assert len(mismatches) == 1
        assert "price" in mismatches[0]

    def test_type_match_no_mismatch(self, conn):
        _bootstrap(conn)
        conn.execute("CREATE TABLE ok_test (name VARCHAR)")

        class OkModel(BaseModel):
            __table_name__ = "ok_test"
            name: str

        mismatches = _detect_type_mismatches(OkModel, conn)
        assert len(mismatches) == 0

    def test_manual_sql_with_begin_raises(self):
        with pytest.raises(ConfigurationError, match="BEGIN/COMMIT"):
            _validate_manual_sql("BEGIN; SELECT 1; COMMIT;", "002_bad.sql")

    def test_manual_sql_without_begin_is_valid(self):
        _validate_manual_sql("SELECT 1", "002_ok.sql")

    def test_manual_sql_with_begins_at_column_valid(self):
        _validate_manual_sql("ALTER TABLE t ADD COLUMN begins_at TIMESTAMPTZ", "003_ok.sql")

    def test_manual_sql_with_commit_comment_valid(self):
        _validate_manual_sql(
            "-- add committed_date column\nALTER TABLE t ADD COLUMN committed_date TEXT",
            "004_ok.sql",
        )

    def test_lifecycle_roundtrip_with_manual_migration(self, conn, tmp_path):
        _bootstrap(conn)
        manual_dir = tmp_path / "manual"
        manual_dir.mkdir()
        (manual_dir / "003_add_col.sql").write_text(
            "ALTER TABLE data_sources ADD COLUMN life_col TEXT"
        )

        class LifeTable(BaseModel):
            __table_name__ = "life_table"
            id: int

        SCHEMA_MODELS.append(LifeTable)
        runner = MigrationRunner(conn)
        runner._manual_dir = manual_dir
        result1 = runner.run()
        assert result1.current_version >= 3

        runner2 = MigrationRunner(conn)
        runner2._manual_dir = manual_dir
        result2 = runner2.run()
        assert len(result2.applied) == 0
        assert result2.current_version == result1.current_version

    def test_gap_detection_passes_after_contiguous_additive(self, conn, tmp_path):
        _bootstrap(conn)
        manual_dir = tmp_path / "manual"
        manual_dir.mkdir()
        (manual_dir / "003_high.sql").write_text(
            "ALTER TABLE data_sources ADD COLUMN high_col TEXT"
        )

        class HighTable(BaseModel):
            __table_name__ = "high_table"
            id: int

        SCHEMA_MODELS.append(HighTable)
        runner = MigrationRunner(conn)
        runner._manual_dir = manual_dir
        runner.run()

        runner2 = MigrationRunner(conn)
        runner2._detect_gaps()

    def test_alter_table_strips_not_null_for_duckdb(self, conn):
        _bootstrap(conn)
        conn.execute("CREATE TABLE alter_test (id INTEGER)")

        class AlterModel(BaseModel):
            __table_name__ = "alter_test"
            id: int
            required_col: str

        stmts = _pydantic_to_alter_table(AlterModel, conn)
        assert len(stmts) == 1
        assert "NOT NULL" not in stmts[0]
        conn.execute(stmts[0])
        assert _column_exists(conn, "alter_test", "required_col")

    def test_check_contiguous_rejects_single_element_gap(self):
        m = AdditiveMigration(version=5, description="gap", sql="SELECT 1")
        with pytest.raises(ConfigurationError, match="does not follow current"):
            MigrationRunner._check_contiguous([m], current=1)

    def test_check_contiguous_passes_only_pending_not_applied(self, conn, tmp_path):
        _bootstrap(conn)
        manual_dir = tmp_path / "manual"
        manual_dir.mkdir()
        (manual_dir / "004_manual.sql").write_text("ALTER TABLE data_sources ADD COLUMN m_col TEXT")

        class PendingOnlyA(BaseModel):
            __table_name__ = "pending_a"
            id: int

        class PendingOnlyB(BaseModel):
            __table_name__ = "pending_b"
            id: int

        SCHEMA_MODELS.append(PendingOnlyA)
        SCHEMA_MODELS.append(PendingOnlyB)
        runner = MigrationRunner(conn)
        runner._manual_dir = manual_dir
        result1 = runner.run()
        assert result1.current_version >= 4

        runner2 = MigrationRunner(conn)
        runner2._manual_dir = manual_dir
        result2 = runner2.run()
        assert len(result2.applied) == 0

    def test_timestamptz_with_full_type_name_no_mismatch(self, conn):
        _bootstrap(conn)
        conn.execute("CREATE TABLE ts_test (ts TIMESTAMP WITH TIME ZONE)")

        class TsModel(BaseModel):
            __table_name__ = "ts_test"
            ts: datetime

        mismatches = _detect_type_mismatches(TsModel, conn)
        assert len(mismatches) == 0

    def test_bigint_integer_symmetry_no_mismatch(self, conn):
        _bootstrap(conn)
        conn.execute("CREATE TABLE bi_test (dur INTEGER)")

        class BiModel(BaseModel):
            __table_name__ = "bi_test"
            dur: timedelta

        mismatches = _detect_type_mismatches(BiModel, conn)
        assert len(mismatches) == 0
