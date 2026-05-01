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

def _json_safe(obj: Any) -> Any:
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    return obj


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

    @staticmethod
    async def store_full_result(db: Any, stored: Any) -> bool:
        comparison = stored.comparison
        strat = comparison.strategy_result
        baseline = comparison.buy_and_hold_result

        for source, result in [("strategy", strat), ("baseline", baseline)]:
            for stype, series in [
                ("equity", result.equity),
                ("returns", result.returns),
                ("positions", result.positions),
            ]:
                rows = [
                    (stored.run_id, source, stype, ts, float(val))
                    for ts, val in series.items()
                    if np.isfinite(float(val))
                ]
                if rows:
                    await db.write(
                        "INSERT INTO result_series (run_id, source, series_type, ts, value) VALUES (?, ?, ?, ?, ?)",
                        rows,
                    )

            trade_records = []
            for _, t in result.trades.iterrows():
                trade_records.append((
                    stored.run_id, source,
                    t["entry_ts"], t["exit_ts"],
                    int(t["side"]), float(t["entry_price"]),
                    float(t["exit_price"]), float(t["return"]),
                    float(t["weight"]),
                ))
            if trade_records:
                await db.write(
                    "INSERT INTO result_trades (run_id, source, entry_ts, exit_ts, side, entry_price, exit_price, return_val, weight) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    trade_records,
                )

        integrity_data = {
            "is_valid": comparison.integrity.is_valid,
            "errors": comparison.integrity.errors,
            "warnings": comparison.integrity.warnings,
            "should_halt_display": comparison.integrity.should_halt_display,
        }
        regime_data = None
        if comparison.regime is not None:
            regime_data = {k: series.tolist() for k, series in comparison.regime.labels.items()}

        ta = stored.trade_analysis
        trade_analysis_data = {
            "avg_holding_period": ta.avg_holding_period,
            "avg_mfe": str(ta.avg_mfe),
            "avg_mae": str(ta.avg_mae),
        }

        baseline_metrics_data = {
            k: getattr(comparison.buy_and_hold_metrics, k)
            for k in [
                "total_return", "cagr", "sharpe", "sortino", "calmar",
                "max_drawdown", "alpha", "beta", "information_ratio",
            ]
        }

        await db.write(
            """UPDATE experiments SET
                config_json = ?, engine_mode = ?, source_run_id = ?,
                trade_analysis_json = ?, baseline_metrics_json = ?,
                integrity_json = ?, regime_json = ?,
                is_label = ?, sample_type = ?, status = 'completed',
                completed_at = ?
            WHERE run_id = ?""",
            (
                json.dumps(stored.config_dict, default=str),
                stored.engine_mode,
                stored.source_run_id,
                json.dumps(trade_analysis_data),
                json.dumps(baseline_metrics_data, default=_json_safe),
                json.dumps(integrity_data),
                json.dumps(regime_data, default=_json_safe) if regime_data else None,
                comparison.is_label,
                comparison.sample_type,
                datetime.now(UTC),
                stored.run_id,
            ),
        )
        log.info("ta:experiment:full_result_stored run_id=%s", stored.run_id)
        return True

    @staticmethod
    async def load_full_result(db: Any, run_id: str) -> Any | None:
        from trade_advisor.backtest.baseline import BaselineComparison
        from trade_advisor.backtest.engine import BacktestResult
        from trade_advisor.backtest.integrity import IntegrityResult
        from trade_advisor.backtest.metrics.trade_analysis import TradeAnalysis
        from trade_advisor.web.services.result_store import StoredResult

        record = await ExperimentRepository.get_run(db, run_id)
        if record is None:
            return None

        rows = await db.read(
            "SELECT source, series_type, ts, value FROM result_series WHERE run_id = ? ORDER BY source, series_type, ts",
            (run_id,),
        )
        if not rows:
            return None

        series_map: dict[tuple[str, str], list[tuple[Any, ...]]] = {}
        for source, stype, ts, val in rows:
            key = (source, stype)
            series_map.setdefault(key, []).append((ts, val))

        def _to_series(key: tuple[str, str]) -> pd.Series:
            data = series_map.get(key, [])
            if not data:
                return pd.Series(dtype=float)
            idx = pd.DatetimeIndex([ts for ts, _ in data])
            vals = [val for _, val in data]
            return pd.Series(vals, index=idx, dtype=float)

        async def _build_result(source: str) -> BacktestResult:
            equity = _to_series((source, "equity"))
            returns = _to_series((source, "returns"))
            positions = _to_series((source, "positions"))

            trade_rows = await db.read(
                "SELECT entry_ts, exit_ts, side, entry_price, exit_price, return_val, weight FROM result_trades WHERE run_id = ? AND source = ?",
                (run_id, source),
            )
            if trade_rows:
                trades = pd.DataFrame(
                    trade_rows,
                    columns=["entry_ts", "exit_ts", "side", "entry_price", "exit_price", "return", "weight"],
                )
            else:
                trades = pd.DataFrame(
                    columns=["entry_ts", "exit_ts", "side", "entry_price", "exit_price", "return", "weight"],
                )

            return BacktestResult(
                equity=equity,
                returns=returns,
                positions=positions,
                trades=trades,
                config=record,  # type: ignore[arg-type]
                meta={},
            )

        strat_result = await _build_result("strategy")
        baseline_result = await _build_result("baseline")

        from trade_advisor.backtest.metrics.performance import compute_performance_metrics
        strategy_metrics = compute_performance_metrics(strat_result)
        buy_hold_metrics = compute_performance_metrics(baseline_result)

        integrity_data: dict[str, Any] = {}
        integrity_rows = await db.read(
            "SELECT integrity_json FROM experiments WHERE run_id = ?",
            (run_id,),
        )
        if integrity_rows and integrity_rows[0][0]:
            integrity_data = json.loads(integrity_rows[0][0])

        integrity = IntegrityResult(
            is_valid=integrity_data.get("is_valid", True),
            errors=integrity_data.get("errors", []),
            warnings=integrity_data.get("warnings", []),
            should_halt_display=integrity_data.get("should_halt_display", False),
        )

        meta_rows = await db.read(
            "SELECT config_json, engine_mode, source_run_id, is_label, sample_type, pre_mortem, trade_analysis_json FROM experiments WHERE run_id = ?",
            (run_id,),
        )
        config_dict: dict[str, Any] = {}
        engine_mode = "vectorized"
        source_run_id = None
        is_label = "In-Sample Only — not validated for live trading"
        sample_type = "in_sample"
        pre_mortem = None
        ta_data: dict[str, Any] = {}

        if meta_rows:
            row = meta_rows[0]
            if row[0]:
                config_dict = json.loads(row[0])
            engine_mode = row[1] or "vectorized"
            source_run_id = row[2]
            is_label = row[3] or is_label
            sample_type = row[4] or sample_type
            pre_mortem = row[5]
            if row[6]:
                ta_data = json.loads(row[6])

        trade_analysis = TradeAnalysis(
            avg_holding_period=ta_data.get("avg_holding_period", 0.0),
            avg_mfe=Decimal(ta_data.get("avg_mfe", "0")),
            avg_mae=Decimal(ta_data.get("avg_mae", "0")),
            entry_return_dist=pd.Series(dtype=float),
            exit_return_dist=pd.Series(dtype=float),
        )

        comparison = BaselineComparison(
            strategy_result=strat_result,
            buy_and_hold_result=baseline_result,
            strategy_metrics=strategy_metrics,
            buy_and_hold_metrics=buy_hold_metrics,
            integrity=integrity,
            is_label=is_label,
            sample_type=sample_type,
        )

        created_at = record.created_at or datetime.now(UTC)

        return StoredResult(
            comparison=comparison,
            trade_analysis=trade_analysis,
            config_dict=config_dict,
            run_id=run_id,
            created_at=created_at,
            engine_mode=engine_mode,
            source_run_id=source_run_id,
            pre_mortem=pre_mortem,
        )
