"""Unit tests for ExperimentRepository.list_runs() and generate_narrative()."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest_asyncio

from trade_advisor.core.config import DatabaseConfig
from trade_advisor.experiments.tracker import (
    ExperimentRecord,
    ExperimentRepository,
    generate_narrative,
)
from trade_advisor.infra.db import DatabaseManager


def _make_record(
    run_id: str = "run_abc123",
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
        config_hash="hash123",
        strategy=strategy,
        metrics_json=metrics,
        seed=42,
        status=status,
        parent_run_id=parent_run_id,
        git_commit="abc1234",
        data_fingerprint="fp123",
        python_version="3.12",
        package_versions="{}",
        is_dirty=False,
        result_hash="rhash123",
        pre_mortem=pre_mortem,
        created_at=created_at or datetime.now(UTC),
        completed_at=created_at or datetime.now(UTC),
    )


@pytest_asyncio.fixture
async def db():
    config = DatabaseConfig(path=":memory:")
    manager = DatabaseManager(config)
    async with manager:
        yield manager


@pytest_asyncio.fixture
async def db_with_3_runs(db: DatabaseManager):
    now = datetime.now(UTC)
    records = [
        _make_record(
            run_id="run_oldest",
            strategy="SmaCross",
            sharpe=1.0,
            total_return=0.10,
            created_at=now - timedelta(days=2),
            pre_mortem="Expect modest gains",
        ),
        _make_record(
            run_id="run_middle",
            strategy="MeanRevert",
            sharpe=2.0,
            total_return=0.30,
            created_at=now - timedelta(days=1),
            status="failed",
        ),
        _make_record(
            run_id="run_newest",
            strategy="SmaCross",
            sharpe=1.5,
            total_return=0.25,
            created_at=now,
            parent_run_id="run_oldest",
        ),
    ]
    for rec in records:
        await ExperimentRepository.store_run(db, rec)
    return db


class TestListRuns:
    async def test_list_returns_chronological_desc(self, db_with_3_runs):
        runs = await ExperimentRepository.list_runs(
            db_with_3_runs, order_by="created_at", order_dir="desc"
        )
        assert len(runs) == 3
        assert runs[0].run_id == "run_newest"
        assert runs[2].run_id == "run_oldest"

    async def test_list_returns_chronological_asc(self, db_with_3_runs):
        runs = await ExperimentRepository.list_runs(
            db_with_3_runs, order_by="created_at", order_dir="asc"
        )
        assert runs[0].run_id == "run_oldest"

    async def test_list_sort_by_strategy_asc(self, db_with_3_runs):
        runs = await ExperimentRepository.list_runs(
            db_with_3_runs, order_by="strategy", order_dir="asc"
        )
        strategies = [r.strategy for r in runs]
        assert strategies == sorted(strategies)

    async def test_list_sort_by_metric_sharpe(self, db_with_3_runs):
        runs = await ExperimentRepository.list_runs(
            db_with_3_runs, order_by="sharpe", order_dir="desc"
        )
        sharpes = []
        for r in runs:
            if r.metrics_json:
                m = json.loads(r.metrics_json)
                sharpes.append(m.get("sharpe", float("-inf")))
        assert sharpes == sorted(sharpes, reverse=True)

    async def test_list_sort_by_metric_total_return(self, db_with_3_runs):
        runs = await ExperimentRepository.list_runs(
            db_with_3_runs, order_by="total_return", order_dir="desc"
        )
        returns = []
        for r in runs:
            if r.metrics_json:
                m = json.loads(r.metrics_json)
                returns.append(m.get("total_return", float("-inf")))
        assert returns == sorted(returns, reverse=True)

    async def test_list_filter_by_strategy(self, db_with_3_runs):
        runs = await ExperimentRepository.list_runs(
            db_with_3_runs, filters={"strategy": "SmaCross"}
        )
        assert len(runs) == 2
        assert all(r.strategy == "SmaCross" for r in runs)

    async def test_list_filter_by_status(self, db_with_3_runs):
        runs = await ExperimentRepository.list_runs(db_with_3_runs, filters={"status": "failed"})
        assert len(runs) == 1
        assert runs[0].run_id == "run_middle"

    async def test_list_filter_by_date_range(self, db_with_3_runs):
        now = datetime.now(UTC)
        start = now - timedelta(days=1, hours=12)
        end = now + timedelta(hours=1)
        runs = await ExperimentRepository.list_runs(
            db_with_3_runs, filters={"date_range": (start, end)}
        )
        assert len(runs) == 2

    async def test_list_combined_filters(self, db_with_3_runs):
        runs = await ExperimentRepository.list_runs(
            db_with_3_runs, filters={"strategy": "SmaCross", "status": "completed"}
        )
        assert all(r.strategy == "SmaCross" for r in runs)
        assert all(r.status == "completed" for r in runs)

    async def test_list_pagination(self, db_with_3_runs):
        page1 = await ExperimentRepository.list_runs(db_with_3_runs, limit=2, offset=0)
        page2 = await ExperimentRepository.list_runs(db_with_3_runs, limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 1

    async def test_list_empty_db(self, db):
        runs = await ExperimentRepository.list_runs(db)
        assert runs == []

    async def test_list_includes_required_fields(self, db_with_3_runs):
        runs = await ExperimentRepository.list_runs(db_with_3_runs)
        run = runs[0]
        assert run.run_id is not None
        assert run.strategy is not None
        assert run.status in ("completed", "running", "failed")
        assert run.created_at is not None

    async def test_list_default_sort_is_created_at_desc(self, db_with_3_runs):
        runs = await ExperimentRepository.list_runs(db_with_3_runs)
        timestamps = [r.created_at for r in runs]
        assert timestamps == sorted(timestamps, reverse=True)

    async def test_list_invalid_order_by_defaults_to_created_at(self, db_with_3_runs):
        runs = await ExperimentRepository.list_runs(db_with_3_runs, order_by="invalid_column")
        assert len(runs) == 3

    async def test_list_invalid_order_dir_defaults_to_desc(self, db_with_3_runs):
        runs = await ExperimentRepository.list_runs(db_with_3_runs, order_dir="sideways")
        timestamps = [r.created_at for r in runs]
        assert timestamps == sorted(timestamps, reverse=True)

    async def test_list_filter_returns_empty_when_no_match(self, db_with_3_runs):
        runs = await ExperimentRepository.list_runs(
            db_with_3_runs, filters={"strategy": "NonExistent"}
        )
        assert runs == []


class TestGenerateNarrative:
    def test_narrative_completed_run(self):
        record = _make_record(sharpe=1.5, total_return=0.25, max_dd=-0.10)
        narrative = generate_narrative(record)
        assert "SmaCross" in narrative
        assert "+25.0%" in narrative
        assert "1.50" in narrative
        assert "-10.0%" in narrative

    def test_narrative_failed_run(self):
        record = _make_record(status="failed")
        narrative = generate_narrative(record)
        assert "failed" in narrative

    def test_narrative_running_run(self):
        record = _make_record(status="running")
        narrative = generate_narrative(record)
        assert "running" in narrative

    def test_narrative_with_pre_mortem(self):
        record = _make_record(pre_mortem="Expect modest gains")
        narrative = generate_narrative(record)
        assert "Pre-mortem prediction: Expect modest gains" in narrative

    def test_narrative_with_parent_run_id(self):
        record = _make_record(parent_run_id="run_abcdef1234567")
        narrative = generate_narrative(record)
        assert "Forked from run run_abcdef12" in narrative

    def test_narrative_no_metrics(self):
        record = _make_record()
        record.metrics_json = None
        narrative = generate_narrative(record)
        assert "N/A" in narrative

    def test_narrative_is_pure_function(self):
        record = _make_record()
        n1 = generate_narrative(record)
        n2 = generate_narrative(record)
        assert n1 == n2
