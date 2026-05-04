"""Shared ATDD fixtures for Epic 4: Walk-Forward Validation & Honest Evaluation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from trade_advisor.core.config import DatabaseConfig
from trade_advisor.infra.db import DatabaseManager


@dataclass
class WalkForwardContext:
    run_id: str = ""
    n_windows: int = 0
    is_window_ids: list[str] = field(default_factory=list)
    oos_window_ids: list[str] = field(default_factory=list)


@dataclass
class StitchedEquityContext:
    oos_equity: pd.Series | None = None
    is_equity: pd.Series | None = None
    wfe_ratio: float = 0.0
    run_id: str = ""


@dataclass
class DeflatedSharpeContext:
    standard_sharpe: float = 0.0
    deflated_sharpe: float = 0.0
    n_trials: int = 0
    run_id: str = ""


def _make_wf_ohlcv(n_bars: int = 500, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2020-01-01", periods=n_bars, freq="B", tz="UTC")
    close = 100.0 + np.cumsum(rng.standard_normal(n_bars) * 0.5)
    high = close + np.abs(rng.standard_normal(n_bars) * 0.3)
    low = close - np.abs(rng.standard_normal(n_bars) * 0.3)
    opn = close + rng.standard_normal(n_bars) * 0.2
    volume = np.abs(rng.standard_normal(n_bars) * 1_000_000) + 100_000
    return pd.DataFrame(
        {
            "timestamp": dates,
            "open": opn,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


def _make_wf_windows(
    n_windows: int = 5,
    is_bars: int = 60,
    oos_bars: int = 20,
    seed: int = 42,
) -> list[dict]:
    rng = np.random.default_rng(seed)
    windows = []
    for i in range(n_windows):
        is_equity = pd.Series(
            100_000 + np.cumsum(rng.standard_normal(is_bars) * 500),
            name=f"is_window_{i}",
        )
        oos_equity = pd.Series(
            100_000 + np.cumsum(rng.standard_normal(oos_bars) * 300),
            name=f"oos_window_{i}",
        )
        windows.append(
            {
                "window_idx": i,
                "is_sharpe": float(rng.uniform(0.5, 2.5)),
                "oos_sharpe": float(rng.uniform(0.1, 1.5)),
                "is_return": float(rng.uniform(0.05, 0.30)),
                "oos_return": float(rng.uniform(0.01, 0.15)),
                "is_equity": is_equity,
                "oos_equity": oos_equity,
                "params": {"fast": 10 + i * 5, "slow": 50},
            }
        )
    return windows


@pytest.fixture
def wf_ohlcv() -> pd.DataFrame:
    return _make_wf_ohlcv()


@pytest.fixture
def wf_ohlcv_short() -> pd.DataFrame:
    return _make_wf_ohlcv(n_bars=120)


@pytest.fixture
def wf_windows() -> list[dict]:
    return _make_wf_windows()


@pytest.fixture
def wf_result(wf_windows):
    from trade_advisor.backtest.walkforward.engine import (
        DataBoundary,
        WalkForwardConfig,
        WalkForwardResult,
        WindowResult,
    )
    from trade_advisor.config import BacktestConfig

    windows = []
    for w in wf_windows:
        i = w["window_idx"]
        is_bars = 60
        oos_bars = 20
        gap_bars = 1
        start = i * (is_bars + gap_bars + oos_bars)

        boundary = DataBoundary(
            is_start=start,
            is_end=start + is_bars,
            oos_start=start + is_bars + gap_bars,
            oos_end=start + is_bars + gap_bars + oos_bars,
        )

        windows.append(
            WindowResult(
                boundary=boundary,
                is_segment=pd.DataFrame({"close": range(is_bars)}),
                oos_segment=pd.DataFrame({"close": range(oos_bars)}),
                is_equity=w["is_equity"],
                oos_equity=w["oos_equity"],
                is_sharpe=w["is_sharpe"],
                oos_sharpe=w["oos_sharpe"],
                is_return=w["is_return"],
                oos_return=w["oos_return"],
                status="OK",
            )
        )

    return WalkForwardResult(
        n_windows=len(windows),
        windows=windows,
        config=WalkForwardConfig(
            mode="rolling",
            is_bars=60,
            oos_bars=20,
            seed=42,
            backtest=BacktestConfig(),  # type: ignore[call-arg]
        ),
    )


@pytest_asyncio.fixture
async def db_with_wf_results():
    config = DatabaseConfig(path=":memory:")
    db = DatabaseManager(config)
    now = datetime.now(UTC)

    wf_windows = _make_wf_windows(n_windows=5)

    trade_analysis = {
        "stitched_equity": [
            {"time": f"2020-01-{i + 1:02d}", "value": float(100_000 + i * 200)}
            for i in range(100)
        ],
        "baseline_equity": [
            {"time": f"2020-01-{i + 1:02d}", "value": float(100_000 + i * 100)}
            for i in range(100)
        ],
        "windows": [
            {
                "is_start": f"2020-01-{1 + w['window_idx'] * 17:02d}",
                "is_end": f"2020-03-{1 + w['window_idx'] * 2:02d}",
                "oos_start": f"2020-03-{2 + w['window_idx'] * 2:02d}",
                "oos_end": f"2020-04-{1 + w['window_idx']:02d}",
                "is_sharpe": w["is_sharpe"],
                "oos_sharpe": w["oos_sharpe"],
                "is_return": w["is_return"],
                "oos_return": w["oos_return"],
                "params": w["params"],
            }
            for w in wf_windows
        ],
    }

    metrics = {
        "wf_sharpe": 1.2,
        "wfe": 0.65,
        "wfe_status": "caution",
        "risk_adj_wfe": 0.60,
        "expected_value": 0.008,
        "dsr": 0.04,
        "dsr_significant": False,
        "regime_variance": 0.12,
        "hints": {"wfe_tip": "Strategy shows partial overfitting"},
    }

    config_json = {
        "strategy_type": "sma",
        "symbol": "SPY",
        "wf_mode": "rolling",
        "is_bars": 60,
        "oos_bars": 20,
        "n_windows": 5,
    }

    async with db:
        await db.write(
            "INSERT INTO experiments "
            "(run_id, config_hash, strategy, metrics_json, seed, status, "
            "created_at, completed_at, config_json, trade_analysis_json, "
            "engine_mode, is_label, sample_type) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "run_wf_001",
                "hash_wf_001",
                "SmaCross",
                json.dumps(metrics),
                42,
                "completed",
                now,
                now,
                json.dumps(config_json),
                json.dumps(trade_analysis),
                "vectorized",
                "Walk-Forward OOS",
                "oos",
            ),
        )

        for w in wf_windows:
            for src_base, eq in [("is", w["is_equity"]), ("oos", w["oos_equity"])]:
                src = f"{src_base}_window_{w['window_idx']}"
                idx = pd.date_range(
                    f"2020-01-{1 + w['window_idx'] * 5:02d}",
                    periods=len(eq),
                    freq="B",
                    tz="UTC",
                )
                series_data = [
                    ("run_wf_001", src, "equity", ts, float(val))
                    for ts, val in zip(idx, eq, strict=True)
                ]
                await db.write_many(
                    "INSERT INTO result_series (run_id, source, series_type, ts, value) "
                    "VALUES (?, ?, ?, ?, ?)",
                    series_data,
                )

        ctx = WalkForwardContext(
            run_id="run_wf_001",
            n_windows=5,
            is_window_ids=[f"is_window_{i}" for i in range(5)],
            oos_window_ids=[f"oos_window_{i}" for i in range(5)],
        )
        yield db, ctx


async def _build_wf_client(db):
    from trade_advisor.main import app

    original_db = getattr(app.state, "db", None)
    app.state.db = db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.get("/health")
            yield client
    finally:
        app.state.db = original_db


@pytest_asyncio.fixture
async def wf_app_client(db_with_wf_results):
    db, _ctx = db_with_wf_results
    async for client in _build_wf_client(db):
        yield client


@pytest_asyncio.fixture
async def wf_sse_client():
    config = DatabaseConfig(path=":memory:")
    db = DatabaseManager(config)
    async with db:
        await _seed_ohlcv_for_sse(db)
        async for client in _build_wf_client(db):
            yield client


async def _seed_ohlcv_for_sse(db):
    rng = np.random.default_rng(42)
    n = 500
    dates = pd.date_range("2020-01-01", periods=n, freq="B", tz="UTC")
    close = 100.0 + np.cumsum(rng.standard_normal(n) * 0.5)
    high = close + np.abs(rng.standard_normal(n) * 0.3)
    low = close - np.abs(rng.standard_normal(n) * 0.3)
    opn = close + rng.standard_normal(n) * 0.2
    volume = np.abs(rng.standard_normal(n) * 1_000_000) + 100_000
    rows = [
        (
            "SPY",
            "1d",
            str(ts),
            float(op),
            float(hi),
            float(lo),
            float(cl),
            float(ac),
            float(vl),
        )
        for ts, op, hi, lo, cl, ac, vl in zip(
            dates, opn, high, low, close, close, volume, strict=True
        )
    ]
    await db.write_many(
        "INSERT INTO ohlcv_cache (symbol, interval, timestamp, open, high, low, close, adj_close, volume) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )


@pytest.fixture(autouse=True)
def _reset_result_store():
    from trade_advisor.web.services.result_store import get_result_store

    get_result_store()._store.clear()
    yield
    get_result_store()._store.clear()
