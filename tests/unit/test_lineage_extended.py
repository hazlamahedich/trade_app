"""Extended tests for experiments/lineage.py — covering uncovered branches.

Uncovered lines: 56 (non-dict metrics JSON), 62-63 (TypeError/ValueError
in float conversion), 144 (truncation warning log).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import pytest

from trade_advisor.experiments.lineage import _MAX_DEPTH, _extract_key_metric


class TestExtractKeyMetricNonDict:
    def test_metrics_json_is_list(self):
        assert _extract_key_metric(json.dumps([1, 2, 3])) is None

    def test_metrics_json_is_string_scalar(self):
        assert _extract_key_metric(json.dumps("hello")) is None

    def test_metrics_json_is_number(self):
        assert _extract_key_metric(json.dumps(42)) is None

    def test_metrics_json_is_bool(self):
        assert _extract_key_metric(json.dumps(True)) is None


class TestExtractKeyMetricFloatConversionError:
    def test_sharpe_is_unconvertible_object_string(self):
        data = json.dumps({"sharpe": {"nested": "not a number"}})
        assert _extract_key_metric(data) is None

    def test_sharpe_is_list(self):
        assert _extract_key_metric(json.dumps({"sharpe": [1, 2]})) is None

    def test_total_return_is_unconvertible_after_bad_sharpe(self):
        data = json.dumps({"sharpe": {"bad": True}, "total_return": 0.5})
        result = _extract_key_metric(data)
        assert result == 0.5


class TestLineageTruncation:
    @pytest.mark.asyncio
    async def test_truncation_at_max_depth(self, caplog):
        from trade_advisor.core.config import DatabaseConfig
        from trade_advisor.experiments.tracker import ExperimentRecord, ExperimentRepository
        from trade_advisor.infra.db import DatabaseManager

        config = DatabaseConfig(path=":memory:")
        db = DatabaseManager(config)
        now = datetime.now(UTC)
        db = await db.__aenter__()

        records = []
        for i in range(_MAX_DEPTH + 2):
            rid = f"run_{i:03d}"
            parent = f"run_{i - 1:03d}" if i > 0 else None
            records.append(
                ExperimentRecord(
                    run_id=rid,
                    config_hash="h",
                    strategy="SmaCross",
                    metrics_json=json.dumps({"sharpe": float(i)}),
                    seed=42,
                    parent_run_id=parent,
                    created_at=now,
                    completed_at=now,
                )
            )

        for rec in records:
            await ExperimentRepository.store_run(db, rec)

        from trade_advisor.experiments.lineage import get_lineage

        with caplog.at_level(logging.WARNING, logger="trade_advisor.experiments.lineage"):
            result = await get_lineage(db, f"run_{_MAX_DEPTH + 1:03d}")

        assert result.truncated is True
        assert len(result.nodes) == _MAX_DEPTH
        assert any("truncated" in r.message.lower() for r in caplog.records)
