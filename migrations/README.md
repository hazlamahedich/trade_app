# Schema Migrations

This directory contains database schema migration assets for the trade_advisor
DuckDB database.

## Migration Strategy: C+A Hybrid

- **Additive (auto):** Generated at runtime from Pydantic schema models
  registered in ``SCHEMA_MODELS`` (in ``src/trade_advisor/infra/migrate.py``).
  These handle ``CREATE TABLE IF NOT EXISTS`` and ``ALTER TABLE ADD COLUMN``.
  No files are stored in this directory for additive migrations.

- **Destructive (manual):** Numbered SQL scripts placed in ``manual/``.
  These handle column renames, type changes, table drops, and other
  non-additive schema changes.

## Manual Migration Naming Convention

Files in ``manual/`` must follow the pattern ``NNN_description.sql``:

- ``NNN`` — zero-padded version number (e.g., ``002``, ``003``)
- ``description`` — brief lowercase description with underscores
- Version 1 is reserved for the initial bootstrap schema (applied by
  ``_SCHEMA_SQL`` in ``db.py``)

Example: ``002_add_strategy_config_table.sql``

## Version Numbering

- Versions are a single ascending integer sequence shared by both additive and
  destructive migrations.
- Migrations apply in strict ascending order. Gap detection is enforced.
- SHA-256 checksums are stored and verified on startup.

## Adding a New Manual Migration

1. Create ``manual/NNN_description.sql`` with the next available version number.
2. Include rollback instructions as SQL comments at the top of the file.
3. Commit the file to git — it will be applied on next application startup.

## Adding a New Table (Additive)

1. Define a Pydantic model with ``__table_name__`` class variable.
2. Register it in ``SCHEMA_MODELS`` in ``src/trade_advisor/infra/migrate.py``.
3. The table will be auto-created on next startup.
