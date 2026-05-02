"""Extended tests for experiments/reproduction.py — covering uncovered branches.

Uncovered lines: 103 (seed missing), 110 (data_fingerprint missing).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
import pytest_asyncio

from trade_advisor.core.config import DatabaseConfig
from trade_advisor.experiments.reproduction import (
    ReproductionError,
    load_run_for_reproduction,
)
from trade_advisor.infra.db import DatabaseManager


def _now():
    return datetime.now(UTC)


@pytest_asyncio.fixture
async def db():
    config = DatabaseConfig(path=":memory:")
    manager = DatabaseManager(config)
    async with manager:
        yield manager


class TestLoadRunMissingSeed:
    def test_seed_missing_raises(self):
        from unittest.mock import MagicMock

        db = MagicMock()
        db._execute_read.return_value = [
            (
                "run_no_seed",
                "h",
                "SmaCross",
                None,
                None,
                "fp",
                json.dumps({"a": 1}),
                "vectorized",
                "{}",
                "abc",
            )
        ]
        with pytest.raises(ReproductionError, match="seed is missing"):
            load_run_for_reproduction(db, "run_no_seed")


class TestLoadRunMissingDataFingerprint:
    def test_data_fingerprint_missing_raises(self, db):
        cfg = json.dumps({"strategy_type": "sma"})
        db._execute(
            "INSERT INTO experiments "
            "(run_id, config_hash, strategy, seed, status, created_at, completed_at, "
            "config_json, data_fingerprint, git_commit, package_versions) "
            "VALUES (?, ?, ?, 42, 'completed', ?, ?, ?, NULL, 'abc', '{}')",
            ("run_no_fp", "h", "SmaCross", _now(), _now(), cfg),
        )
        with pytest.raises(ReproductionError, match="data_fingerprint is missing"):
            load_run_for_reproduction(db, "run_no_fp")
