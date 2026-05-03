from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime

from trade_advisor.backtest.baseline import BaselineComparison
from trade_advisor.backtest.metrics.trade_analysis import TradeAnalysis
from trade_advisor.infra.protocols import DatabaseReader

log = logging.getLogger(__name__)


@dataclass
class StoredResult:
    comparison: BaselineComparison
    trade_analysis: TradeAnalysis
    config_dict: dict[str, object]
    run_id: str
    created_at: datetime
    engine_mode: str
    source_run_id: str | None = None
    persist_warning: bool = False
    dirty_tree_warning: bool = False
    pre_mortem: str | None = None
    is_duplicate: bool = False
    n_trials: int | None = None
    sr_variance: float | None = None
    diagnostics_json: str | None = None


class InMemoryResultStore:
    MAX_ENTRIES = 100

    def __init__(self) -> None:
        self._store: dict[str, StoredResult] = {}
        self._lock = asyncio.Lock()
        self._db: DatabaseReader | None = None

    def set_db(self, db: DatabaseReader) -> None:
        self._db = db

    def generate_run_id(self) -> str:
        return uuid.uuid4().hex[:12]

    async def store(self, result: StoredResult) -> None:
        async with self._lock:
            if len(self._store) >= self.MAX_ENTRIES:
                oldest_key = min(self._store, key=lambda k: self._store[k].created_at)
                del self._store[oldest_key]
            self._store[result.run_id] = result

        if self._db is not None:
            try:
                from trade_advisor.experiments.tracker import ExperimentRepository

                await ExperimentRepository.store_full_result(self._db, result)
            except Exception as exc:
                log.warning("ta:store:duckdb_persist_failed run_id=%s: %s", result.run_id, exc)
                result.persist_warning = True

    async def get(self, run_id: str) -> StoredResult | None:
        async with self._lock:
            cached = self._store.get(run_id)
            if cached is not None:
                return cached

        if self._db is not None:
            try:
                from trade_advisor.experiments.tracker import ExperimentRepository

                result: StoredResult | None = await ExperimentRepository.load_full_result(
                    self._db, run_id
                )
                if result is not None:
                    async with self._lock:
                        self._store[run_id] = result
                    return result
            except Exception as exc:
                log.warning("ta:store:duckdb_load_failed run_id=%s: %s", run_id, exc)

        return None

    async def delete(self, run_id: str) -> bool:
        async with self._lock:
            if run_id in self._store:
                del self._store[run_id]
                return True
        return False


_store = InMemoryResultStore()


def get_result_store() -> InMemoryResultStore:
    return _store
