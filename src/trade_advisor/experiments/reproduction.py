"""Run reproduction — clone stored experiment results under a lineage-linked run_id.

This module implements MVP reproduction (result cloning), not re-execution.
Stored equity curve and trades are re-materialized under a new deterministic
run_id linked to the original via ``parent_run_id``.

The ``is_clone=True`` field in ``ReproductionResult`` distinguishes copied
results from re-executed results (future Epic 4+).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict

from trade_advisor.experiments.tracker import HashedRunInputs, generate_run_id
from trade_advisor.infra.protocols import DatabaseReader

log = logging.getLogger(__name__)

_REPRODUCTION_COLS = (
    "run_id, config_hash, strategy, seed, parent_run_id, "
    "data_fingerprint, config_json, engine_mode, "
    "package_versions, git_commit"
)
_REPRODUCTION_COL_NAMES = [c.strip() for c in _REPRODUCTION_COLS.split(",")]


class ReproductionError(Exception):
    """Custom exception for all reproduction failures."""

    def __init__(self, message: str, *, error_code: str = "unknown") -> None:
        super().__init__(message)
        self.error_code = error_code


class ReproductionSpec(BaseModel):
    config: dict[str, Any]
    seed: int
    data_fingerprint: str
    data_fingerprint_method: str
    strategy: str
    engine_mode: str
    config_hash: str
    run_id: str
    code_version: str | None = None
    package_versions: str | None = None


class DataFreshness(BaseModel):
    has_changed: bool = False
    warning: str | None = None
    original_fingerprint: str | None = None
    current_fingerprint: str | None = None
    fingerprint_method: str = "parquet_hash_recompute"


class ReproductionResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    run_id: str
    parent_run_id: str
    equity: pd.Series
    config: dict[str, Any]
    is_clone: bool = True


def _get_reproduction_row(db: DatabaseReader, run_id: str) -> dict[str, Any] | None:
    rows = db._execute_read(
        "SELECT " + _REPRODUCTION_COLS + " FROM experiments WHERE run_id = ?",
        (run_id,),
    )
    if not rows:
        return None
    return dict(zip(_REPRODUCTION_COL_NAMES, rows[0], strict=True))


def load_run_for_reproduction(db: DatabaseReader, run_id: str) -> ReproductionSpec:
    row = _get_reproduction_row(db, run_id)
    if row is None:
        raise ReproductionError(f"Run not found: {run_id}", error_code="not_found")

    config_json_raw = row.get("config_json")
    if config_json_raw is None:
        raise ReproductionError(
            f"Cannot reproduce run {run_id}: config_json is missing",
            error_code="config_missing",
        )
    try:
        config = json.loads(config_json_raw)
    except (json.JSONDecodeError, TypeError):
        raise ReproductionError(
            f"Cannot reproduce run {run_id}: config_json is corrupt",
            error_code="config_corrupt",
        ) from None

    seed = row.get("seed")
    if seed is None:
        raise ReproductionError(
            f"Cannot reproduce run {run_id}: seed is missing",
            error_code="seed_missing",
        )

    data_fp = row.get("data_fingerprint")
    if data_fp is None:
        raise ReproductionError(
            f"Cannot reproduce run {run_id}: data_fingerprint is missing",
            error_code="fingerprint_missing",
        )

    return ReproductionSpec(
        config=config,
        seed=int(seed),
        data_fingerprint=str(data_fp),
        data_fingerprint_method="parquet_hash_recompute",
        strategy=str(row.get("strategy") or ""),
        engine_mode=str(row.get("engine_mode") or "vectorized"),
        config_hash=str(row.get("config_hash") or ""),
        run_id=str(run_id),
        code_version=row.get("git_commit"),
        package_versions=row.get("package_versions"),
    )


def check_data_freshness(db: DatabaseReader, run_id: str) -> DataFreshness:
    rows = db._execute_read(
        "SELECT data_fingerprint, config_json FROM experiments WHERE run_id = ?",
        (run_id,),
    )
    if not rows:
        return DataFreshness(fingerprint_method="parquet_hash_recompute")

    stored_fp, config_json_raw = rows[0]
    if stored_fp is None:
        return DataFreshness(fingerprint_method="parquet_hash_recompute")

    current_fp = _recompute_parquet_fingerprint(config_json_raw)

    if current_fp is not None and current_fp != str(stored_fp):
        return DataFreshness(
            has_changed=True,
            warning="Data snapshot has changed since original run. Results may differ.",
            original_fingerprint=str(stored_fp),
            current_fingerprint=current_fp,
            fingerprint_method="parquet_hash_recompute",
        )

    return DataFreshness(
        has_changed=False,
        original_fingerprint=str(stored_fp),
        current_fingerprint=current_fp or str(stored_fp),
        fingerprint_method="parquet_hash_recompute",
    )


def _recompute_parquet_fingerprint(config_json_raw: str | None) -> str | None:
    if config_json_raw is None:
        return None
    try:
        config = json.loads(config_json_raw)
    except (json.JSONDecodeError, TypeError):
        return None

    symbol = config.get("symbol")
    interval = config.get("interval", "1d")
    if not symbol:
        return None

    try:
        from trade_advisor.data.cache import load_cached
        from trade_advisor.experiments.tracker import compute_data_fingerprint

        ohlcv = load_cached(str(symbol), str(interval))
        if ohlcv is None:
            return None
        return compute_data_fingerprint(ohlcv)
    except Exception:
        log.warning("ta:freshness:recompute_failed symbol=%s", symbol, exc_info=True)
        return None


def _load_equity_from_series(db: DatabaseReader, run_id: str) -> pd.Series:
    rows = db._execute_read(
        "SELECT ts, value FROM result_series "
        "WHERE run_id = ? AND source = 'strategy' AND series_type = 'equity' "
        "ORDER BY ts",
        (run_id,),
    )
    if not rows:
        return pd.Series(dtype=float)
    idx = pd.DatetimeIndex([r[0] for r in rows])
    vals = [r[1] for r in rows]
    return pd.Series(vals, index=idx, dtype=float)


async def reproduce_run(db: DatabaseReader, run_id: str) -> ReproductionResult:
    spec = load_run_for_reproduction(db, run_id)

    child_id = generate_run_id(
        HashedRunInputs(
            config=spec.config,
            data_fingerprint=spec.data_fingerprint,
            code_version=spec.code_version or "",
            package_versions=spec.package_versions or "",
            parent_context=run_id,
        )
    )

    existing = db._execute_read(
        "SELECT run_id FROM experiments WHERE run_id = ? AND parent_run_id = ? LIMIT 1",
        (child_id, run_id),
    )
    if existing:
        existing_equity = _load_equity_from_series(db, child_id)
        return ReproductionResult(
            run_id=child_id,
            parent_run_id=run_id,
            equity=existing_equity,
            config=spec.config,
            is_clone=True,
        )

    original_equity = _load_equity_from_series(db, run_id)

    now = datetime.now(UTC)

    await db.write(
        """INSERT INTO experiments (
            run_id, config_hash, strategy, metrics_json, seed, status,
            parent_run_id, git_commit, data_fingerprint,
            python_version, package_versions, is_dirty, result_hash,
            pre_mortem, narrative, created_at, completed_at,
            config_json, engine_mode
        ) VALUES (?, ?, ?, NULL, ?, 'completed', ?, ?, ?, NULL, ?, FALSE, NULL, NULL, NULL, ?, ?, ?, ?)""",
        (
            child_id,
            spec.config_hash,
            spec.strategy,
            spec.seed,
            run_id,
            spec.code_version,
            spec.data_fingerprint,
            spec.package_versions,
            now,
            now,
            json.dumps(spec.config, default=str),
            spec.engine_mode,
        ),
    )

    if len(original_equity) > 0:
        series_data = [
            (child_id, "strategy", "equity", ts, float(val)) for ts, val in original_equity.items()
        ]
        await db.write_many(
            "INSERT INTO result_series "
            "(run_id, source, series_type, ts, value) VALUES (?, ?, ?, ?, ?)",
            series_data,
        )

    return ReproductionResult(
        run_id=child_id,
        parent_run_id=run_id,
        equity=original_equity,
        config=spec.config,
        is_clone=True,
    )
