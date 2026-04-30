from __future__ import annotations

import functools
import hashlib
import json
import logging
import math
import subprocess
import sys
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel

log = logging.getLogger(__name__)

_EXPERIMENT_COLUMNS = (
    "run_id, config_hash, strategy, metrics_json, seed, status, "
    "parent_run_id, git_commit, data_fingerprint, "
    "python_version, package_versions, is_dirty, result_hash, "
    "pre_mortem, created_at, completed_at"
)
_EXPERIMENT_COL_NAMES = [c.strip() for c in _EXPERIMENT_COLUMNS.split(",")]


class HashedRunInputs(BaseModel):
    config: dict[str, Any]
    data_fingerprint: str = ""
    code_version: str = ""
    package_versions: str = ""
    is_dirty: bool = False
    parent_context: str = ""


class RunAnnotations(BaseModel):
    pre_mortem: str | None = None


class ExperimentRecord(BaseModel):
    run_id: str
    config_hash: str
    strategy: str
    metrics_json: str | None = None
    seed: int = 0
    status: str = "running"
    parent_run_id: str | None = None
    git_commit: str | None = None
    data_fingerprint: str | None = None
    python_version: str | None = None
    package_versions: str | None = None
    is_dirty: bool | None = False
    result_hash: str | None = None
    pre_mortem: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None


def _normalize_value(v: Any) -> Any:
    if isinstance(v, Decimal):
        v = float(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        v = float(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, dict):
        return _normalize_config(v)
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            raise ValueError(f"NaN/Infinity not allowed in config hash: {v}")
        if v == int(v):
            return int(v)
        return round(v, 15)
    return v


def _normalize_config(config: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for k, v in config.items():
        if isinstance(v, dict):
            normalized[k] = _normalize_config(v)
        elif isinstance(v, list):
            normalized[k] = [_normalize_value(item) for item in v]
        else:
            normalized[k] = _normalize_value(v)
    return normalized


def compute_config_hash(config: dict[str, Any]) -> str:
    normalized = _normalize_config(config)
    canonical = json.dumps(normalized, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def generate_run_id(inputs: HashedRunInputs) -> str:
    normalized_config = _normalize_config(inputs.config)
    payload = {
        "config": normalized_config,
        "data_fingerprint": inputs.data_fingerprint,
        "code_version": inputs.code_version,
        "package_versions": inputs.package_versions,
        "is_dirty": inputs.is_dirty,
        "parent_context": inputs.parent_context,
    }
    canonical = json.dumps(payload, sort_keys=True)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"run_{digest[:16]}"


def compute_data_fingerprint(ohlcv: pd.DataFrame) -> str:
    if ohlcv.empty:
        return "empty"

    ohlcv_cols = ["open", "high", "low", "close", "volume"]
    available = [c for c in ohlcv_cols if c in ohlcv.columns]
    if not available:
        return "no_ohlcv_columns"
    cols = ohlcv[available].astype("float64")

    material = json.dumps(
        {
            "columns": sorted(cols.columns.tolist()),
            "expected": sorted(ohlcv_cols),
            "first_ts": str(ohlcv.index[0]),
            "last_ts": str(ohlcv.index[-1]),
            "rows": len(ohlcv),
            "ohlcv_hash": hashlib.sha256(np.asarray(cols.values).tobytes()).hexdigest(),
        },
        sort_keys=True,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


@functools.lru_cache(maxsize=1)
def get_code_version() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return "unknown"


@functools.lru_cache(maxsize=1)
def is_dirty_tree() -> bool:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return bool(result.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return True


def get_package_versions() -> str:
    versions = {
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "python": sys.version.split()[0],
    }
    return json.dumps(versions, sort_keys=True)


def compute_result_hash(equity: pd.Series, trades: pd.DataFrame) -> str:
    eq_bytes = np.asarray(equity.astype("float64").values).tobytes()
    all_cols_hash = hashlib.sha256(json.dumps(sorted(trades.columns.tolist())).encode()).hexdigest()
    if trades.empty:
        return hashlib.sha256(eq_bytes + all_cols_hash.encode()).hexdigest()
    numeric_cols = trades.select_dtypes(include=["number"]).astype("float64")
    numeric_cols = numeric_cols[sorted(numeric_cols.columns)]
    tr_bytes = np.asarray(numeric_cols.values).tobytes()
    return hashlib.sha256(eq_bytes + tr_bytes + all_cols_hash.encode()).hexdigest()


class ExperimentRepository:
    @staticmethod
    async def store_run(db: Any, record: ExperimentRecord) -> bool:
        try:
            now = datetime.now(UTC)
            await db.write(
                """
                INSERT INTO experiments (
                    run_id, config_hash, strategy, metrics_json, seed, status,
                    parent_run_id, git_commit, data_fingerprint,
                    python_version, package_versions, is_dirty, result_hash,
                    pre_mortem, created_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.run_id,
                    record.config_hash,
                    record.strategy,
                    record.metrics_json,
                    record.seed,
                    record.status,
                    record.parent_run_id,
                    record.git_commit,
                    record.data_fingerprint,
                    record.python_version,
                    record.package_versions,
                    record.is_dirty,
                    record.result_hash,
                    record.pre_mortem,
                    record.created_at or now,
                    record.completed_at or now,
                ),
            )
            log.info("ta:experiment:stored run_id=%s", record.run_id)
            return True
        except Exception as exc:
            exc_name = type(exc).__name__
            if "Constraint" in exc_name or "UNIQUE" in str(exc) or "PRIMARY" in str(exc):
                log.info("ta:experiment:duplicate run_id=%s", record.run_id)
                return True
            log.warning("ta:experiment:store_failed run_id=%s: %s", record.run_id, exc)
            return False

    @staticmethod
    async def get_run(db: Any, run_id: str) -> ExperimentRecord | None:
        try:
            rows = await db.read(
                f"SELECT {_EXPERIMENT_COLUMNS} FROM experiments WHERE run_id = ?",
                (run_id,),
            )
            if not rows:
                return None
            row = rows[0]
            mapped = dict(zip(_EXPERIMENT_COL_NAMES, row, strict=True))
            return ExperimentRecord(**mapped)
        except Exception as exc:
            log.warning("ta:experiment:get_failed run_id=%s: %s", run_id, exc)
            return None

    @staticmethod
    async def run_exists(db: Any, run_id: str) -> bool:
        try:
            rows = await db.read(
                "SELECT 1 FROM experiments WHERE run_id = ? LIMIT 1",
                (run_id,),
            )
            return len(rows) > 0
        except Exception:
            return False
