from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pandas as pd
import pytest

from tests.helpers import _synthetic_ohlcv
from trade_advisor.web.services.result_store import (
    InMemoryResultStore,
    StoredResult,
    get_result_store,
)


def _make_stored(run_id=None, source_run_id=None, created_at=None, **kw):
    from trade_advisor.backtest.baseline import BaselineComparison
    from trade_advisor.backtest.metrics.trade_analysis import TradeAnalysis

    comparison = kw.get("comparison")
    if comparison is None:
        metrics_type = type(
            "M",
            (),
            {
                "total_return": 0.1,
                "cagr": 0.05,
                "sharpe": 1.0,
                "max_drawdown": -0.05,
                "alpha": 0.02,
                "beta": 0.9,
            },
        )
        integrity = type(
            "I", (), {"is_valid": True, "warnings": [], "errors": [], "should_halt_display": False}
        )
        str_result = type(
            "R", (), {"trades": _synthetic_ohlcv(n=0), "equity": _synthetic_ohlcv(n=5)["close"]}
        )
        comparison = BaselineComparison(
            strategy_metrics=metrics_type(),
            buy_and_hold_metrics=metrics_type(),
            strategy_result=str_result(),
            buy_and_hold_result=str_result(),
            integrity=integrity(),
            is_label="IS",
            sample_type="is",
        )

    trade_analysis = kw.get("trade_analysis") or TradeAnalysis(
        avg_holding_period=5.0,
        avg_mfe=Decimal("0.02"),
        avg_mae=Decimal("0.01"),
        entry_return_dist=pd.Series([], dtype="float64"),
        exit_return_dist=pd.Series([], dtype="float64"),
    )

    return StoredResult(
        comparison=comparison,
        trade_analysis=trade_analysis,
        config_dict=kw.get("config_dict", {}),
        run_id=run_id or uuid.uuid4().hex[:12],
        created_at=created_at or datetime.now(UTC),
        engine_mode=kw.get("engine_mode", "vectorized"),
        source_run_id=source_run_id,
        persist_warning=kw.get("persist_warning", False),
        dirty_tree_warning=kw.get("dirty_tree_warning", False),
        pre_mortem=kw.get("pre_mortem"),
        is_duplicate=kw.get("is_duplicate", False),
    )


class TestGenerateRunId:
    def test_format_12_hex_chars(self):
        store = InMemoryResultStore()
        rid = store.generate_run_id()
        assert len(rid) == 12
        assert all(c in "0123456789abcdef" for c in rid)

    def test_unique_across_calls(self):
        store = InMemoryResultStore()
        ids = {store.generate_run_id() for _ in range(100)}
        assert len(ids) == 100


class TestGetResultStoreSingleton:
    def test_returns_same_instance(self):
        a = get_result_store()
        b = get_result_store()
        assert a is b


class TestStoreAndGet:
    @pytest.mark.asyncio
    async def test_store_and_retrieve(self):
        store = InMemoryResultStore()
        result = _make_stored()
        await store.store(result)
        got = await store.get(result.run_id)
        assert got is result

    @pytest.mark.asyncio
    async def test_missing_returns_none(self):
        store = InMemoryResultStore()
        assert await store.get("nonexistent") is None

    @pytest.mark.asyncio
    async def test_overwrite_existing_run_id(self):
        store = InMemoryResultStore()
        r1 = _make_stored(run_id="abc123")
        r2 = _make_stored(run_id="abc123")
        await store.store(r1)
        await store.store(r2)
        got = await store.get("abc123")
        assert got is r2


class TestEviction:
    @pytest.mark.asyncio
    async def test_evicts_oldest_at_max(self):
        store = InMemoryResultStore()
        store.MAX_ENTRIES = 3
        results = []
        for i in range(4):
            r = _make_stored(run_id=f"r{i}", created_at=datetime(2026, 1, i + 1, tzinfo=UTC))
            results.append(r)
            await store.store(r)
        assert await store.get("r0") is None
        assert await store.get("r3") is not None

    @pytest.mark.asyncio
    async def test_no_eviction_below_max(self):
        store = InMemoryResultStore()
        store.MAX_ENTRIES = 5
        for i in range(5):
            await store.store(_make_stored(run_id=f"r{i}"))
        for i in range(5):
            assert await store.get(f"r{i}") is not None


class TestStoredResultDefaults:
    def test_default_optional_fields(self):
        r = _make_stored()
        assert r.source_run_id is None
        assert r.persist_warning is False
        assert r.dirty_tree_warning is False
        assert r.pre_mortem is None
        assert r.is_duplicate is False
