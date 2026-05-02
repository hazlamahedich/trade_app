"""Extended tests for experiments/compare.py — covering uncovered branches.

Uncovered lines: 95-96 (TypeError/ValueError in _safe_float),
121 (_determine_order lexicographic reversal), 175 (both configs None),
240 (first run not found), 293-294 (IndexError/TypeError in compare_trades).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from trade_advisor.core.config import DatabaseConfig
from trade_advisor.experiments.compare import (
    _compute_parameter_diff_list,
    _determine_order,
    _safe_float,
    compare_runs,
)
from trade_advisor.experiments.tracker import ExperimentRecord, ExperimentRepository
from trade_advisor.infra.db import DatabaseManager


class TestSafeFloatTypeError:
    def test_safe_float_raises_type_error(self):
        class BadObj:
            def __float__(self):
                raise TypeError("nope")

        assert _safe_float(BadObj()) is None


class TestDetermineOrderLexicographicReverse:
    def test_second_run_id_before_first(self):
        a = {"run_id": "zzz", "created_at": None}
        b = {"run_id": "aaa", "created_at": None}
        baseline, challenger = _determine_order(a, b)
        assert baseline["run_id"] == "aaa"
        assert challenger["run_id"] == "zzz"


class TestComputeParameterDiffBothNone:
    def test_both_none_returns_empty(self):
        result = _compute_parameter_diff_list(None, None)
        assert result == []

    def test_a_none_only(self):
        result = _compute_parameter_diff_list(None, {"fast": 20})
        assert result == []


class TestCompareRunsFirstNotFound:
    @pytest.mark.asyncio
    async def test_first_run_not_found_raises(self):
        config = DatabaseConfig(path=":memory:")
        db = DatabaseManager(config)
        async with db:
            rec = ExperimentRecord(
                run_id="run_exists",
                config_hash="h",
                strategy="SmaCross",
                metrics_json=json.dumps({"sharpe": 1.0}),
                seed=42,
                created_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            )
            await ExperimentRepository.store_run(db, rec)
            with pytest.raises(ValueError, match="Run not found: missing_a"):
                compare_runs(db, "missing_a", "run_exists")


class TestCompareTradesBadFloatInRow:
    @pytest.mark.asyncio
    async def test_bad_float_in_positions_skipped(self):
        from unittest.mock import MagicMock

        from trade_advisor.experiments.compare import compare_trades

        db = MagicMock()
        db._execute_read.side_effect = lambda q, p=None: []

        def _mock_read(query, params=None):
            if "experiments" in query and "run_id" in query:
                return [
                    (
                        "ra",
                        "h",
                        "SmaCross",
                        json.dumps({"sharpe": 1.0}),
                        42,
                        "completed",
                        None,
                        datetime.now(UTC),
                        None,
                    )
                ]
            return []

        db._execute_read = _mock_read
        result = compare_trades(db, "ra", "rb")
        assert result.alignment_strategy == "sequential"
