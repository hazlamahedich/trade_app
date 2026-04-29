from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from trade_advisor.web.services.result_store import InMemoryResultStore, StoredResult


def _make_stored(run_id: str = "abc123", created_at: datetime | None = None) -> StoredResult:
    from decimal import Decimal

    from trade_advisor.backtest.baseline import BaselineComparison
    from trade_advisor.backtest.integrity import IntegrityResult
    from trade_advisor.backtest.metrics.performance import PerformanceMetrics

    dummy_metrics = PerformanceMetrics(
        total_return=Decimal("0.1"),
        cagr=Decimal("0.05"),
        sharpe=1.0,
        sortino=0.8,
        calmar=0.6,
        max_drawdown=Decimal("-0.15"),
        alpha=0.02,
        beta=1.0,
        information_ratio=0.5,
    )
    import pandas as pd

    from trade_advisor.backtest.engine import BacktestResult
    from trade_advisor.config import BacktestConfig

    config = BacktestConfig()
    dummy_result = BacktestResult(
        equity=pd.Series([100000.0, 110000.0], dtype=float),
        returns=pd.Series([0.0, 0.1], dtype=float),
        positions=pd.Series([0.0, 1.0], dtype=float),
        trades=pd.DataFrame(
            columns=["entry_ts", "exit_ts", "side", "entry_price", "exit_price", "return", "weight"]
        ),
        config=config,
    )
    comparison = BaselineComparison(
        strategy_result=dummy_result,
        buy_and_hold_result=dummy_result,
        strategy_metrics=dummy_metrics,
        buy_and_hold_metrics=dummy_metrics,
        integrity=IntegrityResult(is_valid=True),
        is_label="In-Sample Only — not validated for live trading",
        sample_type="in_sample",
    )
    from trade_advisor.backtest.metrics.trade_analysis import TradeAnalysis

    trade_analysis = TradeAnalysis(
        avg_holding_period=5.0,
        avg_mfe=Decimal("0.02"),
        avg_mae=Decimal("0.01"),
        entry_return_dist=pd.Series(dtype=float),
        exit_return_dist=pd.Series(dtype=float),
    )
    return StoredResult(
        comparison=comparison,
        trade_analysis=trade_analysis,
        config_dict={"fast": 20, "slow": 50},
        run_id=run_id,
        created_at=created_at or datetime.now(UTC),
        engine_mode="vectorized",
    )


@pytest.mark.asyncio
async def test_store_and_retrieve():
    store = InMemoryResultStore()
    result = _make_stored(run_id="test123")
    await store.store(result)
    retrieved = await store.get("test123")
    assert retrieved is not None
    assert retrieved.run_id == "test123"
    assert retrieved.engine_mode == "vectorized"


@pytest.mark.asyncio
async def test_retrieve_missing_returns_none():
    store = InMemoryResultStore()
    retrieved = await store.get("nonexistent")
    assert retrieved is None


@pytest.mark.asyncio
async def test_eviction_at_max_entries():
    store = InMemoryResultStore()
    base_time = datetime(2025, 1, 1, tzinfo=UTC)
    for i in range(101):
        ts = base_time.replace(hour=0, minute=0, second=0) + __import__("datetime").timedelta(
            minutes=i
        )
        result = _make_stored(run_id=f"run_{i:04d}", created_at=ts)
        await store.store(result)

    oldest = await store.get("run_0000")
    assert oldest is None, "Oldest entry should be evicted"

    newest = await store.get("run_0100")
    assert newest is not None, "Newest entry should remain"


@pytest.mark.asyncio
async def test_concurrent_access():
    store = InMemoryResultStore()

    async def _store_item(idx: int):
        result = _make_stored(run_id=f"concurrent_{idx}")
        await store.store(result)

    await asyncio.gather(*[_store_item(i) for i in range(20)])
    for i in range(20):
        retrieved = await store.get(f"concurrent_{i}")
        assert retrieved is not None
