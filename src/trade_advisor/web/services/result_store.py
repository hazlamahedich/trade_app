from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime

from trade_advisor.backtest.baseline import BaselineComparison
from trade_advisor.backtest.metrics.trade_analysis import TradeAnalysis


@dataclass
class StoredResult:
    comparison: BaselineComparison
    trade_analysis: TradeAnalysis
    config_dict: dict
    run_id: str
    created_at: datetime
    engine_mode: str
    source_run_id: str | None = None


class InMemoryResultStore:
    MAX_ENTRIES = 100

    def __init__(self) -> None:
        self._store: dict[str, StoredResult] = {}
        self._lock = asyncio.Lock()

    def generate_run_id(self) -> str:
        return uuid.uuid4().hex[:12]

    async def store(self, result: StoredResult) -> None:
        async with self._lock:
            if len(self._store) >= self.MAX_ENTRIES:
                oldest_key = min(self._store, key=lambda k: self._store[k].created_at)
                del self._store[oldest_key]
            self._store[result.run_id] = result

    async def get(self, run_id: str) -> StoredResult | None:
        async with self._lock:
            return self._store.get(run_id)


_store = InMemoryResultStore()


def get_result_store() -> InMemoryResultStore:
    return _store
