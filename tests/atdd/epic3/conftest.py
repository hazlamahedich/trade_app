"""Shared ATDD fixtures for Epic 3 tests."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from trade_advisor.core.config import DatabaseConfig
from trade_advisor.experiments.tracker import (
    ExperimentRecord,
    ExperimentRepository,
)
from trade_advisor.infra.db import DatabaseManager


def _make_record(
    run_id: str,
    strategy: str = "SmaCross",
    status: str = "completed",
    sharpe: float = 1.5,
    total_return: float = 0.25,
    max_dd: float = -0.10,
    created_at: datetime | None = None,
    pre_mortem: str | None = None,
    parent_run_id: str | None = None,
) -> ExperimentRecord:
    metrics = json.dumps({"sharpe": sharpe, "total_return": total_return, "max_drawdown": max_dd})
    return ExperimentRecord(
        run_id=run_id,
        config_hash="hash_" + run_id,
        strategy=strategy,
        metrics_json=metrics,
        seed=42,
        status=status,
        parent_run_id=parent_run_id,
        git_commit="abc1234",
        data_fingerprint="fp_" + run_id,
        python_version="3.12",
        package_versions="{}",
        is_dirty=False,
        result_hash="rhash_" + run_id,
        pre_mortem=pre_mortem,
        created_at=created_at or datetime.now(UTC),
        completed_at=created_at or datetime.now(UTC),
    )


@pytest_asyncio.fixture
async def db_with_experiments():
    config = DatabaseConfig(path=":memory:")
    db = DatabaseManager(config)
    now = datetime.now(UTC)
    async with db:
        records = [
            _make_record(
                run_id="run_atdd_001",
                strategy="SmaCross",
                sharpe=1.5,
                total_return=0.25,
                created_at=now - timedelta(days=2),
                pre_mortem="Expect good returns",
            ),
            _make_record(
                run_id="run_atdd_002",
                strategy="MeanRevert",
                sharpe=0.8,
                total_return=0.05,
                created_at=now - timedelta(days=1),
                status="failed",
            ),
            _make_record(
                run_id="run_atdd_003",
                strategy="SmaCross",
                sharpe=2.0,
                total_return=0.40,
                created_at=now,
            ),
        ]
        for rec in records:
            await ExperimentRepository.store_run(db, rec)

        import numpy as np
        import pandas as pd

        first_run_id = records[0].run_id
        equity_idx = pd.date_range("2024-01-01", periods=10, freq="B", tz="UTC")
        equity_vals = pd.Series(np.linspace(100, 120, 10), index=equity_idx, dtype=float)
        returns_vals = equity_vals.pct_change().fillna(0)
        positions_vals = pd.Series(
            [1.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0], index=equity_idx, dtype=float
        )

        for source in ("strategy", "baseline"):
            eq_vals = equity_vals if source == "strategy" else equity_vals * 0.95
            ret_vals = returns_vals if source == "strategy" else returns_vals * 0.9

            series_data = [
                (first_run_id, source, "equity", ts, float(val))
                for ts, val in zip(equity_idx, eq_vals, strict=True)
            ]
            await db.write_many(
                "INSERT INTO result_series (run_id, source, series_type, ts, value) VALUES (?, ?, ?, ?, ?)",
                series_data,
            )
            returns_data = [
                (first_run_id, source, "returns", ts, float(val))
                for ts, val in zip(equity_idx, ret_vals, strict=True)
            ]
            await db.write_many(
                "INSERT INTO result_series (run_id, source, series_type, ts, value) VALUES (?, ?, ?, ?, ?)",
                returns_data,
            )
            positions_data = [
                (first_run_id, source, "positions", ts, float(val))
                for ts, val in zip(equity_idx, positions_vals, strict=True)
            ]
            await db.write_many(
                "INSERT INTO result_series (run_id, source, series_type, ts, value) VALUES (?, ?, ?, ?, ?)",
                positions_data,
            )

        from trade_advisor.backtest.integrity import IntegrityResult

        integrity = IntegrityResult(
            is_valid=True, errors=[], warnings=[], should_halt_display=False
        )
        await db.write(
            "UPDATE experiments SET config_json = ?, engine_mode = 'vectorized', source_run_id = NULL, integrity_json = ?, is_label = 'In-Sample Only', sample_type = 'in_sample', status = 'completed', completed_at = ? WHERE run_id = ?",
            (
                json.dumps({"strategy_type": "sma", "symbol": "SPY", "fast": 20, "slow": 50}),
                json.dumps(asdict(integrity)),
                datetime.now(UTC),
                first_run_id,
            ),
        )

        db._known_run_ids = ["run_atdd_001", "run_atdd_002", "run_atdd_003"]
        yield db


@pytest_asyncio.fixture
async def app_client(db_with_experiments):
    from trade_advisor.main import app

    original_db = getattr(app.state, "db", None)
    app.state.db = db_with_experiments
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.get("/health")
            yield client
    finally:
        app.state.db = original_db


@pytest.fixture(autouse=True)
def _reset_result_store():
    from trade_advisor.web.services.result_store import get_result_store

    get_result_store()._store.clear()
    yield
    get_result_store()._store.clear()
