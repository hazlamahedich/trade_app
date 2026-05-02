"""Extended tests for experiments/tracker.py — covering store_full_result,
load_full_result, _normalize_value branches, _json_safe, generate_narrative_from_stored,
and error paths in get_run / run_exists / list_runs.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import numpy as np
import pandas as pd
import pytest
import pytest_asyncio

from trade_advisor.core.config import DatabaseConfig
from trade_advisor.experiments.tracker import (
    ExperimentRecord,
    ExperimentRepository,
    _json_safe,
    _normalize_config,
    _normalize_value,
    compute_data_fingerprint,
    compute_result_hash,
    generate_narrative,
    generate_narrative_from_stored,
)
from trade_advisor.infra.db import DatabaseManager


def _now():
    return datetime.now(UTC)


def _rec(run_id="run_ext", strategy="SmaCross", **kw):
    defaults = {
        "config_hash": "hash_ext",
        "strategy": strategy,
        "metrics_json": json.dumps({"sharpe": 1.5}),
        "seed": 42,
        "status": "completed",
        "created_at": _now(),
        "completed_at": _now(),
    }
    defaults.update(kw)
    return ExperimentRecord(run_id=run_id, **defaults)


@pytest_asyncio.fixture
async def db():
    config = DatabaseConfig(path=":memory:")
    manager = DatabaseManager(config)
    async with manager:
        yield manager


class TestNormalizeValueBranches:
    @pytest.mark.test_id("3.1-UNIT-001")
    @pytest.mark.p2
    def test_bool_converts(self):
        assert _normalize_value(np.bool_(True)) is True
        assert _normalize_value(np.bool_(False)) is False

    @pytest.mark.test_id("3.1-UNIT-002")
    @pytest.mark.p2
    def test_dict_value_recurses(self):
        result = _normalize_value({"nested": {"deep": 1}})
        assert result == {"nested": {"deep": 1}}

    @pytest.mark.test_id("3.1-UNIT-003")
    @pytest.mark.p2
    def test_list_value_maps(self):
        result = _normalize_value([1, 2, 3])
        assert result == [1, 2, 3]

    @pytest.mark.test_id("3.1-UNIT-004")
    @pytest.mark.p2
    def test_float_rounds_to_15(self):
        result = _normalize_value(0.1234567890123456789)
        assert result == round(0.1234567890123456789, 15)

    @pytest.mark.test_id("3.1-UNIT-005")
    @pytest.mark.p2
    def test_float_whole_becomes_int(self):
        assert _normalize_value(5.0) == 5
        assert isinstance(_normalize_value(5.0), int)

    @pytest.mark.test_id("3.1-UNIT-006")
    @pytest.mark.p2
    def test_string_passthrough(self):
        assert _normalize_value("hello") == "hello"

    @pytest.mark.test_id("3.1-UNIT-007")
    @pytest.mark.p2
    def test_none_passthrough(self):
        assert _normalize_value(None) is None


class TestNormalizeConfigListBranch:
    @pytest.mark.test_id("3.1-UNIT-008")
    @pytest.mark.p2
    def test_config_with_list_values(self):
        config = {"lookback": [10, 20, 30], "name": "test"}
        result = _normalize_config(config)
        assert result["lookback"] == [10, 20, 30]
        assert result["name"] == "test"


class TestJsonSafe:
    @pytest.mark.test_id("3.1-UNIT-009")
    @pytest.mark.p2
    def test_nan_returns_none(self):
        assert _json_safe(float("nan")) is None

    @pytest.mark.test_id("3.1-UNIT-010")
    @pytest.mark.p2
    def test_inf_returns_none(self):
        assert _json_safe(float("inf")) is None

    @pytest.mark.test_id("3.1-UNIT-011")
    @pytest.mark.p2
    def test_negative_inf_returns_none(self):
        assert _json_safe(float("-inf")) is None

    @pytest.mark.test_id("3.1-UNIT-012")
    @pytest.mark.p2
    def test_decimal_converts(self):
        assert _json_safe(Decimal("100.5")) == 100.5

    @pytest.mark.test_id("3.1-UNIT-013")
    @pytest.mark.p2
    def test_np_integer_converts(self):
        assert _json_safe(np.int64(42)) == 42

    @pytest.mark.test_id("3.1-UNIT-014")
    @pytest.mark.p2
    def test_np_floating_converts(self):
        assert _json_safe(np.float64(3.14)) == 3.14

    @pytest.mark.test_id("3.1-UNIT-015")
    @pytest.mark.p2
    def test_regular_int_passthrough(self):
        assert _json_safe(42) == 42

    @pytest.mark.test_id("3.1-UNIT-016")
    @pytest.mark.p2
    def test_regular_string_passthrough(self):
        assert _json_safe("test") == "test"


class TestGenerateNarrativeFromStored:
    @pytest.mark.test_id("3.1-UNIT-017")
    @pytest.mark.p2
    def test_basic_narrative(self):
        mock_stored = type(
            "S",
            (),
            {
                "config_dict": {"strategy_type": "sma"},
                "engine_mode": "vectorized",
                "pre_mortem": None,
                "source_run_id": None,
                "run_id": "run_test",
            },
        )()
        result = generate_narrative_from_stored(mock_stored)
        assert "sma" in result
        assert "vectorized" in result

    @pytest.mark.test_id("3.1-UNIT-018")
    @pytest.mark.p2
    def test_with_pre_mortem(self):
        mock_stored = type(
            "S",
            (),
            {
                "config_dict": {"strategy_type": "sma"},
                "engine_mode": "vectorized",
                "pre_mortem": "Expect good results",
                "source_run_id": None,
                "run_id": "run_test",
            },
        )()
        result = generate_narrative_from_stored(mock_stored)
        assert "Pre-mortem" in result
        assert "Expect good results" in result

    @pytest.mark.test_id("3.1-UNIT-019")
    @pytest.mark.p2
    def test_with_source_run_id(self):
        mock_stored = type(
            "S",
            (),
            {
                "config_dict": {"strategy_type": "sma"},
                "engine_mode": "vectorized",
                "pre_mortem": None,
                "source_run_id": "run_abcdef123456",
                "run_id": "run_test",
            },
        )()
        result = generate_narrative_from_stored(mock_stored)
        assert "Reproduced from run" in result
        assert "run_abcdef12" in result

    @pytest.mark.test_id("3.1-UNIT-020")
    @pytest.mark.p2
    def test_empty_config_dict(self):
        mock_stored = type(
            "S",
            (),
            {
                "config_dict": {},
                "engine_mode": "vectorized",
                "pre_mortem": None,
                "source_run_id": None,
                "run_id": "run_test",
            },
        )()
        result = generate_narrative_from_stored(mock_stored)
        assert "unknown" in result

    @pytest.mark.test_id("3.1-UNIT-021")
    @pytest.mark.p2
    def test_none_config_dict(self):
        mock_stored = type(
            "S",
            (),
            {
                "config_dict": None,
                "engine_mode": "event_driven",
                "pre_mortem": None,
                "source_run_id": None,
                "run_id": "run_test",
            },
        )()
        result = generate_narrative_from_stored(mock_stored)
        assert "unknown" in result
        assert "event_driven" in result


class TestGetRunErrorPaths:
    @pytest.mark.asyncio
    @pytest.mark.test_id("3.1-UNIT-022")
    @pytest.mark.p2
    async def test_get_run_db_exception_returns_none(self):
        db = AsyncMock()
        db.read.side_effect = Exception("DB broken")
        result = await ExperimentRepository.get_run(db, "run_x")
        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.test_id("3.1-UNIT-023")
    @pytest.mark.p2
    async def test_get_run_success(self, db):
        await ExperimentRepository.store_run(db, _rec("run_get_test"))
        result = await ExperimentRepository.get_run(db, "run_get_test")
        assert result is not None
        assert result.run_id == "run_get_test"

    @pytest.mark.asyncio
    @pytest.mark.test_id("3.1-UNIT-024")
    @pytest.mark.p2
    async def test_get_run_not_found(self, db):
        result = await ExperimentRepository.get_run(db, "nonexistent")
        assert result is None


class TestRunExistsErrorPath:
    @pytest.mark.asyncio
    @pytest.mark.test_id("3.1-UNIT-025")
    @pytest.mark.p2
    async def test_run_exists_db_exception(self):
        db = AsyncMock()
        db.read.side_effect = Exception("DB error")
        result = await ExperimentRepository.run_exists(db, "any_run")
        assert result is False


class TestListRunsErrorPath:
    @pytest.mark.asyncio
    @pytest.mark.test_id("3.1-UNIT-026")
    @pytest.mark.p2
    async def test_list_runs_db_exception(self):
        db = AsyncMock()
        db.read.side_effect = Exception("DB error")
        result = await ExperimentRepository.list_runs(db)
        assert result == []


class TestStoreRunDuplicate:
    @pytest.mark.asyncio
    @pytest.mark.test_id("3.1-UNIT-027")
    @pytest.mark.p2
    async def test_store_duplicate_returns_true(self, db):
        rec = _rec("run_dup")
        r1 = await ExperimentRepository.store_run(db, rec)
        assert r1 is True
        duplicate_db = AsyncMock()
        exc = Exception("UNIQUE constraint violated")
        duplicate_db.write.side_effect = exc
        r2 = await ExperimentRepository.store_run(duplicate_db, rec)
        assert r2 is True


class TestComputeDataFingerprintNoOhlcv:
    @pytest.mark.test_id("3.1-UNIT-028")
    @pytest.mark.p2
    def test_no_ohlcv_columns(self):
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        assert compute_data_fingerprint(df) == "no_ohlcv_columns"


class TestComputeResultHashVarious:
    @pytest.mark.test_id("3.1-UNIT-029")
    @pytest.mark.p2
    def test_with_non_numeric_trades(self):
        equity = pd.Series([100.0, 101.0])
        trades = pd.DataFrame({"side": ["long"], "return": [0.01], "pnl": [1.0]})
        h = compute_result_hash(equity, trades)
        assert len(h) == 64

    @pytest.mark.test_id("3.1-UNIT-030")
    @pytest.mark.p2
    def test_with_many_trades(self):
        equity = pd.Series([100.0 + i for i in range(50)])
        trades = pd.DataFrame(
            {
                "return": [0.01] * 50,
                "pnl": [1.0] * 50,
                "mfe": [0.02] * 50,
            }
        )
        h = compute_result_hash(equity, trades)
        assert len(h) == 64


class TestGenerateNarrativeMalformedJson:
    @pytest.mark.test_id("3.1-UNIT-031")
    @pytest.mark.p2
    def test_malformed_metrics_json_falls_back(self):
        record = _rec(run_id="run_mj", metrics_json="not json at all")
        narrative = generate_narrative(record)
        assert "SmaCross" in narrative
        assert "N/A" in narrative

    @pytest.mark.test_id("3.1-UNIT-032")
    @pytest.mark.p2
    def test_none_created_at_with_status_completed(self):
        record = ExperimentRecord(
            run_id="run_no_date",
            config_hash="h",
            strategy="SmaCross",
            status="completed",
            metrics_json=json.dumps({"sharpe": 1.0, "total_return": 0.1, "max_drawdown": -0.05}),
            created_at=None,
            completed_at=None,
        )
        narrative = generate_narrative(record)
        assert "unknown date" in narrative
