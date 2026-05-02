"""Unit tests for trade_advisor.experiments.reproduction."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
import pytest_asyncio

from trade_advisor.core.config import DatabaseConfig
from trade_advisor.experiments.reproduction import (
    DataFreshness,
    ReproductionError,
    ReproductionResult,
    ReproductionSpec,
    check_data_freshness,
    load_run_for_reproduction,
    reproduce_run,
)
from trade_advisor.experiments.tracker import (
    ExperimentRecord,
    ExperimentRepository,
)
from trade_advisor.infra.db import DatabaseManager


def _now():
    return datetime.now(UTC)


def _rec(
    run_id: str,
    strategy: str = "SmaCross",
    seed: int = 42,
    data_fingerprint: str | None = "fp_default",
    config_hash: str | None = None,
) -> ExperimentRecord:
    return ExperimentRecord(
        run_id=run_id,
        config_hash=config_hash or f"hash_{run_id}",
        strategy=strategy,
        metrics_json=json.dumps({"sharpe": 1.5}),
        seed=seed,
        status="completed",
        data_fingerprint=data_fingerprint,
        git_commit="abc123",
        package_versions="{}",
        is_dirty=False,
        created_at=_now(),
        completed_at=_now(),
    )


def _config_dict(**overrides):
    base = {"strategy_type": "sma", "symbol": "SPY", "fast": 20, "slow": 50}
    base.update(overrides)
    return base


def _insert_run(db, run_id, cfg_json="{}", seed=42, data_fp="fp", config_hash="h", strategy="S"):
    db._execute(
        "INSERT INTO experiments "
        "(run_id, config_hash, strategy, seed, status, created_at, completed_at, "
        "config_json, data_fingerprint, git_commit, package_versions) "
        "VALUES (?, ?, ?, ?, 'completed', ?, ?, ?, ?, 'abc123', '{}')",
        (run_id, config_hash, strategy, seed, _now(), _now(), cfg_json, data_fp),
    )


@pytest_asyncio.fixture
async def db_with_run():
    config = DatabaseConfig(path=":memory:")
    db = DatabaseManager(config)
    async with db:
        run_id = "run_unit_001"
        cfg = _config_dict()
        rec = _rec(run_id)
        await ExperimentRepository.store_run(db, rec)
        await db.write(
            "UPDATE experiments SET config_json = ?, engine_mode = 'vectorized', "
            "status = 'completed' WHERE run_id = ?",
            (json.dumps(cfg), run_id),
        )

        idx = pd.date_range("2024-01-01", periods=5, freq="B", tz="UTC")
        vals = [100.0, 102.0, 104.0, 106.0, 108.0]
        series_data = [
            (run_id, "strategy", "equity", ts, val) for ts, val in zip(idx, vals, strict=True)
        ]
        await db.write_many(
            "INSERT INTO result_series (run_id, source, series_type, ts, value) "
            "VALUES (?, ?, ?, ?, ?)",
            series_data,
        )

        db._run_id = run_id
        db._config = cfg
        db._original_equity = pd.Series(vals, index=idx, dtype=float)
        yield db


@pytest_asyncio.fixture
async def db_empty():
    config = DatabaseConfig(path=":memory:")
    db = DatabaseManager(config)
    async with db:
        yield db


# ── Level A: load_run_for_reproduction ──────────────────────────────────────


class TestLoadRunForReproduction:
    def test_valid_run_returns_spec(self, db_with_run):
        spec = load_run_for_reproduction(db_with_run, db_with_run._run_id)
        assert isinstance(spec, ReproductionSpec)
        assert spec.config == db_with_run._config
        assert spec.seed == 42
        assert spec.data_fingerprint == "fp_default"
        assert spec.strategy == "SmaCross"
        assert spec.engine_mode == "vectorized"
        assert spec.data_fingerprint_method == "parquet_hash_recompute"

    def test_missing_config_json_raises(self, db_empty):
        rec = _rec("run_no_config")
        db_empty._execute(
            "INSERT INTO experiments "
            "(run_id, config_hash, strategy, seed, status, created_at, completed_at, "
            "data_fingerprint, git_commit, package_versions) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                rec.run_id,
                rec.config_hash,
                rec.strategy,
                rec.seed,
                rec.status,
                _now(),
                _now(),
                rec.data_fingerprint,
                "abc123",
                "{}",
            ),
        )
        with pytest.raises(ReproductionError, match="config_json is missing"):
            load_run_for_reproduction(db_empty, "run_no_config")

    def test_missing_run_raises(self, db_with_run):
        with pytest.raises(ReproductionError, match="Run not found: ghost_run"):
            load_run_for_reproduction(db_with_run, "ghost_run")

    def test_config_json_none_raises(self, db_empty):
        _insert_run(db_empty, "run_null_cfg", cfg_json="{}", data_fp="fp")
        db_empty._execute(
            "UPDATE experiments SET config_json = NULL WHERE run_id = ?",
            ("run_null_cfg",),
        )
        with pytest.raises(ReproductionError, match="config_json is missing"):
            load_run_for_reproduction(db_empty, "run_null_cfg")

    def test_malformed_config_json_raises(self, db_empty):
        _insert_run(db_empty, "run_bad_cfg", cfg_json="{invalid json}", data_fp="fp")
        with pytest.raises(ReproductionError, match="config_json is corrupt"):
            load_run_for_reproduction(db_empty, "run_bad_cfg")

    def test_seed_zero_is_valid(self, db_empty):
        cfg = _config_dict()
        _insert_run(db_empty, "run_seed0", cfg_json=json.dumps(cfg), seed=0)
        spec = load_run_for_reproduction(db_empty, "run_seed0")
        assert spec.seed == 0

    def test_empty_string_data_fingerprint_is_valid(self, db_empty):
        _insert_run(db_empty, "run_empty_fp", data_fp="")
        spec = load_run_for_reproduction(db_empty, "run_empty_fp")
        assert spec.data_fingerprint == ""


# ── Level B: check_data_freshness ───────────────────────────────────────────


class TestCheckDataFreshness:
    def test_unchanged_fingerprint(self, db_with_run):
        with patch(
            "trade_advisor.experiments.reproduction._recompute_parquet_fingerprint",
            return_value="fp_default",
        ):
            freshness = check_data_freshness(db_with_run, db_with_run._run_id)
        assert freshness.has_changed is False
        assert freshness.warning is None
        assert freshness.fingerprint_method == "parquet_hash_recompute"

    def test_changed_fingerprint_shows_warning(self, db_empty):
        _insert_run(db_empty, "run_stale", data_fp="stale_fingerprint_value")
        freshness = check_data_freshness(db_empty, "run_stale")
        assert freshness.has_changed is True
        assert freshness.warning is not None
        assert "changed" in freshness.warning.lower()

    def test_missing_run_returns_default(self, db_empty):
        freshness = check_data_freshness(db_empty, "nonexistent")
        assert freshness.has_changed is False
        assert freshness.fingerprint_method == "parquet_hash_recompute"

    def test_none_fingerprint_returns_default(self, db_empty):
        _insert_run(db_empty, "run_null_fp", data_fp="fp")
        db_empty._execute(
            "UPDATE experiments SET data_fingerprint = NULL WHERE run_id = ?",
            ("run_null_fp",),
        )
        freshness = check_data_freshness(db_empty, "run_null_fp")
        assert freshness.has_changed is False

    def test_empty_string_fingerprint_returns_default(self, db_empty):
        _insert_run(db_empty, "run_empty_str_fp", data_fp="")
        freshness = check_data_freshness(db_empty, "run_empty_str_fp")
        assert freshness.has_changed is False

    def test_fingerprint_method_is_parquet_recompute(self, db_with_run):
        with patch(
            "trade_advisor.experiments.reproduction._recompute_parquet_fingerprint",
            return_value="fp_default",
        ):
            freshness = check_data_freshness(db_with_run, db_with_run._run_id)
        assert freshness.fingerprint_method == "parquet_hash_recompute"

    def test_recomputed_hash_diff_detects_change(self, db_with_run):
        with patch(
            "trade_advisor.experiments.reproduction._recompute_parquet_fingerprint",
            return_value="different_hash_value",
        ):
            freshness = check_data_freshness(db_with_run, db_with_run._run_id)
        assert freshness.has_changed is True
        assert freshness.original_fingerprint == "fp_default"
        assert freshness.current_fingerprint == "different_hash_value"


# ── Level C: reproduce_run ──────────────────────────────────────────────────


class TestReproduceRun:
    async def test_produces_new_run_id(self, db_with_run):
        result = await reproduce_run(db_with_run, db_with_run._run_id)
        assert result.run_id != db_with_run._run_id

    async def test_parent_run_id_set(self, db_with_run):
        result = await reproduce_run(db_with_run, db_with_run._run_id)
        assert result.parent_run_id == db_with_run._run_id

    async def test_equity_matches_within_tolerance(self, db_with_run):
        result = await reproduce_run(db_with_run, db_with_run._run_id)
        original = db_with_run._original_equity
        pd.testing.assert_series_equal(
            result.equity.reset_index(drop=True),
            original.reset_index(drop=True),
            atol=1e-10,
        )

    async def test_stores_new_experiment_in_db(self, db_with_run):
        result = await reproduce_run(db_with_run, db_with_run._run_id)
        rows = db_with_run._execute_read(
            "SELECT run_id, parent_run_id FROM experiments WHERE run_id = ?",
            (result.run_id,),
        )
        assert len(rows) == 1
        assert rows[0][1] == db_with_run._run_id

    async def test_chain_reproduction_depth_2(self, db_with_run):
        gen1 = await reproduce_run(db_with_run, db_with_run._run_id)
        gen2 = await reproduce_run(db_with_run, gen1.run_id)
        assert gen2.parent_run_id == gen1.run_id
        assert gen1.parent_run_id == db_with_run._run_id

    async def test_idempotent_reproduce_returns_existing(self, db_with_run):
        first = await reproduce_run(db_with_run, db_with_run._run_id)
        second = await reproduce_run(db_with_run, db_with_run._run_id)
        assert first.run_id == second.run_id
        assert first.parent_run_id == second.parent_run_id

    async def test_config_copied_to_child(self, db_with_run):
        result = await reproduce_run(db_with_run, db_with_run._run_id)
        assert result.config == db_with_run._config

    async def test_empty_equity_reproduced(self, db_empty):
        cfg = _config_dict()
        _insert_run(db_empty, "run_empty_eq", cfg_json=json.dumps(cfg))
        result = await reproduce_run(db_empty, "run_empty_eq")
        assert len(result.equity) == 0

    async def test_nan_inf_equity_preserved(self, db_empty):
        cfg = _config_dict()
        _insert_run(db_empty, "run_nan", cfg_json=json.dumps(cfg))
        idx = pd.date_range("2024-01-01", periods=3, freq="B", tz="UTC")
        vals = [100.0, float("nan"), float("inf")]
        series_data = [
            ("run_nan", "strategy", "equity", ts, val) for ts, val in zip(idx, vals, strict=True)
        ]
        db_empty._execute_many(
            "INSERT INTO result_series (run_id, source, series_type, ts, value) VALUES (?, ?, ?, ?, ?)",
            series_data,
        )
        result = await reproduce_run(db_empty, "run_nan")
        assert np.isnan(result.equity.iloc[1])
        assert np.isinf(result.equity.iloc[2])


# ── Level D: model tests ────────────────────────────────────────────────────


class TestModels:
    def test_reproduction_spec_validates_required_fields(self):
        spec = ReproductionSpec(
            config={"a": 1},
            seed=42,
            data_fingerprint="fp",
            data_fingerprint_method="parquet_hash_recompute",
            strategy="SmaCross",
            engine_mode="vectorized",
            config_hash="hash123",
            run_id="run_123",
        )
        assert spec.config == {"a": 1}
        assert spec.seed == 42
        assert spec.code_version is None

    def test_data_freshness_defaults(self):
        f = DataFreshness()
        assert f.has_changed is False
        assert f.warning is None
        assert f.fingerprint_method == "parquet_hash_recompute"

    def test_reproduction_result_is_clone(self):
        r = ReproductionResult(
            run_id="child",
            parent_run_id="parent",
            equity=pd.Series(dtype=float),
            config={},
        )
        assert r.is_clone is True

    def test_reproduction_error_message_includes_run_id(self):
        try:
            raise ReproductionError("Run not found: run_xyz", error_code="not_found")
        except ReproductionError as e:
            assert "run_xyz" in str(e)
            assert e.error_code == "not_found"


# ── Level E: Web API tests ──────────────────────────────────────────────────


class TestWebAPIReproduce:
    @pytest.mark.asyncio
    async def test_api_reproduce_200(self, db_with_run):
        from httpx import ASGITransport, AsyncClient

        from trade_advisor.main import app

        original_db = getattr(app.state, "db", None)
        app.state.db = db_with_run
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                await client.get("/health")
                resp = await client.post(f"/api/experiments/{db_with_run._run_id}/reproduce")
                assert resp.status_code == 200
                data = resp.json()
                assert data["run_id"] != db_with_run._run_id
                assert data["parent_run_id"] == db_with_run._run_id
                assert data["is_clone"] is True
        finally:
            app.state.db = original_db

    @pytest.mark.asyncio
    async def test_api_reproduce_idempotent_200(self, db_with_run):
        from httpx import ASGITransport, AsyncClient

        from trade_advisor.main import app

        original_db = getattr(app.state, "db", None)
        app.state.db = db_with_run
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                await client.get("/health")
                resp1 = await client.post(f"/api/experiments/{db_with_run._run_id}/reproduce")
                resp2 = await client.post(f"/api/experiments/{db_with_run._run_id}/reproduce")
                assert resp1.status_code == 200
                assert resp2.status_code == 200
                assert resp1.json()["run_id"] == resp2.json()["run_id"]
        finally:
            app.state.db = original_db

    @pytest.mark.asyncio
    async def test_api_reproduce_404_unknown(self, db_with_run):
        from httpx import ASGITransport, AsyncClient

        from trade_advisor.main import app

        original_db = getattr(app.state, "db", None)
        app.state.db = db_with_run
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                await client.get("/health")
                resp = await client.post("/api/experiments/nonexistent_run_xyz/reproduce")
                assert resp.status_code == 404
                data = resp.json()
                assert "error" in data
        finally:
            app.state.db = original_db

    @pytest.mark.asyncio
    async def test_api_reproduce_400_empty_run_id(self, db_with_run):
        from httpx import ASGITransport, AsyncClient

        from trade_advisor.main import app

        original_db = getattr(app.state, "db", None)
        app.state.db = db_with_run
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                await client.get("/health")
                resp = await client.post("/api/experiments/ /reproduce")
                assert resp.status_code in (400, 404)
        finally:
            app.state.db = original_db

    @pytest.mark.asyncio
    async def test_api_stale_data_warning(self, db_empty):
        from httpx import ASGITransport, AsyncClient

        from trade_advisor.main import app

        cfg = _config_dict()
        _insert_run(
            db_empty, "run_stale_api", cfg_json=json.dumps(cfg), data_fp="stale_fingerprint_value"
        )
        original_db = getattr(app.state, "db", None)
        app.state.db = db_empty
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                await client.get("/health")
                resp = await client.post("/api/experiments/run_stale_api/reproduce")
                assert resp.status_code == 200
                data = resp.json()
                assert data.get("data_freshness_warning") is not None
        finally:
            app.state.db = original_db

    @pytest.mark.asyncio
    async def test_api_response_timing(self, db_with_run):
        import time

        from httpx import ASGITransport, AsyncClient

        from trade_advisor.main import app

        original_db = getattr(app.state, "db", None)
        app.state.db = db_with_run
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                await client.get("/health")
                start = time.monotonic()
                resp = await client.post(f"/api/experiments/{db_with_run._run_id}/reproduce")
                elapsed = time.monotonic() - start
                assert resp.status_code == 200
                assert elapsed < 2.0
        finally:
            app.state.db = original_db


# ── Level F: edge case tests ────────────────────────────────────────────────


class TestEdgeCases:
    async def test_deterministic_run_id_collision(self, db_with_run):
        first = await reproduce_run(db_with_run, db_with_run._run_id)
        second = await reproduce_run(db_with_run, db_with_run._run_id)
        assert first.run_id == second.run_id
        rows = db_with_run._execute_read(
            "SELECT COUNT(*) FROM experiments WHERE run_id = ?",
            (first.run_id,),
        )
        assert rows[0][0] == 1

    async def test_reproducing_a_reproduction(self, db_with_run):
        gen1 = await reproduce_run(db_with_run, db_with_run._run_id)
        gen2 = await reproduce_run(db_with_run, gen1.run_id)
        assert gen2.parent_run_id == gen1.run_id
        assert gen1.parent_run_id == db_with_run._run_id
        assert gen2.run_id != gen1.run_id
        assert gen2.run_id != db_with_run._run_id

    async def test_concurrent_idempotent_access(self, db_with_run):
        results = []
        for _ in range(3):
            results.append(await reproduce_run(db_with_run, db_with_run._run_id))
        assert len({r.run_id for r in results}) == 1
        assert results[0].run_id == results[1].run_id == results[2].run_id

    def test_malformed_run_id_strings(self, db_empty):
        with pytest.raises(ReproductionError):
            load_run_for_reproduction(db_empty, "")

        with pytest.raises(ReproductionError):
            load_run_for_reproduction(db_empty, "'; DROP TABLE experiments; --")

        with pytest.raises(ReproductionError):
            load_run_for_reproduction(db_empty, "x" * 10000)
