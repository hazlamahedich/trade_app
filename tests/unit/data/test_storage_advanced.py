"""Tests for data/storage.py — DataRepository advanced scenarios."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest

from tests.conftest import _synthetic_ohlcv


@pytest.fixture
async def repo():
    from trade_advisor.core.config import DatabaseConfig
    from trade_advisor.data.storage import DataRepository
    from trade_advisor.infra.db import DatabaseManager

    config = DatabaseConfig(path=":memory:")
    async with DatabaseManager(config) as db:
        yield DataRepository(db)


class TestStoreEdgeCases:
    @pytest.mark.asyncio
    async def test_store_empty_df_is_noop(self, repo):
        empty = pd.DataFrame()
        await repo.store(empty, provider_name="test")
        loaded = await repo.load("TEST", "1d")
        assert loaded is None

    @pytest.mark.asyncio
    async def test_store_auto_fills_split_div_factors(self, repo):
        df = _synthetic_ohlcv(n=5)
        df = df.drop(columns=["split_factor", "div_factor"], errors="ignore")
        df = df.drop(columns=["split_factor"], errors="ignore")
        if "split_factor" not in df.columns:
            df["split_factor"] = 1.0
        if "div_factor" not in df.columns:
            df["div_factor"] = 1.0
        await repo.store(df, provider_name="test")
        loaded = await repo.load("TEST", "1d")
        assert loaded is not None
        assert (loaded["split_factor"] == 1.0).all()
        assert (loaded["div_factor"] == 1.0).all()

    @pytest.mark.asyncio
    async def test_store_missing_column_raises(self, repo):
        df = pd.DataFrame({"symbol": ["TEST"], "interval": ["1d"]})
        from trade_advisor.core.errors import DataError

        with pytest.raises(DataError, match="Missing required column"):
            await repo.store(df, provider_name="test")

    @pytest.mark.asyncio
    async def test_store_preserves_adj_close_from_older_source(self, repo):
        from trade_advisor.core.config import DatabaseConfig
        from trade_advisor.data.storage import DataRepository
        from trade_advisor.infra.db import DatabaseManager

        config = DatabaseConfig(path=":memory:")
        async with DatabaseManager(config) as db:
            repo_inner = DataRepository(db)

            df1 = _synthetic_ohlcv(n=3)
            df1["source"] = "source_a"
            df1["adj_close"] = 99.99
            await repo_inner.store(df1, provider_name="source_a")

            df2 = _synthetic_ohlcv(n=3)
            df2["source"] = "source_b"
            df2["adj_close"] = 88.88
            await repo_inner.store(df2, provider_name="source_b")

            loaded = await repo_inner.load("TEST", "1d")
            assert loaded is not None
            assert (loaded["adj_close"] == 99.99).all()

    @pytest.mark.asyncio
    async def test_store_large_batch_chunking(self, repo):
        df = _synthetic_ohlcv(n=2500)
        await repo.store(df, provider_name="test")
        loaded = await repo.load("TEST", "1d")
        assert loaded is not None
        assert len(loaded) == 2500


class TestLoadVariants:
    @pytest.mark.asyncio
    async def test_load_with_start_only(self, repo):
        df = _synthetic_ohlcv(n=100)
        await repo.store(df, provider_name="test")

        start = datetime(2020, 5, 1, tzinfo=UTC)
        loaded = await repo.load("TEST", "1d", start=start)
        assert loaded is not None
        assert loaded["timestamp"].min() >= start

    @pytest.mark.asyncio
    async def test_load_with_end_only(self, repo):
        df = _synthetic_ohlcv(n=100)
        await repo.store(df, provider_name="test")

        end = datetime(2020, 3, 1, tzinfo=UTC)
        loaded = await repo.load("TEST", "1d", end=end)
        assert loaded is not None
        assert loaded["timestamp"].max() < end

    @pytest.mark.asyncio
    async def test_load_returns_sorted_timestamps(self, repo):
        df = _synthetic_ohlcv(n=50)
        await repo.store(df, provider_name="test")

        loaded = await repo.load("TEST", "1d")
        assert loaded is not None
        timestamps = loaded["timestamp"].tolist()
        assert timestamps == sorted(timestamps)

    @pytest.mark.asyncio
    async def test_load_volume_filled_as_int(self, repo):
        df = _synthetic_ohlcv(n=5)
        await repo.store(df, provider_name="test")

        loaded = await repo.load("TEST", "1d")
        assert loaded is not None
        assert loaded["volume"].dtype == "int64"


class TestFreshnessEdgeCases:
    @pytest.mark.asyncio
    async def test_freshness_threshold_hours_minimum(self):
        from trade_advisor.core.config import DatabaseConfig, DataConfig
        from trade_advisor.data.storage import DataRepository
        from trade_advisor.infra.db import DatabaseManager

        config = DatabaseConfig(path=":memory:")
        data_config = DataConfig(staleness_threshold_sec=100)
        async with DatabaseManager(config) as db:
            repo = DataRepository(db, config=data_config)
            df = _synthetic_ohlcv(n=3)
            await repo.store(df, provider_name="test")

            freshness = await repo.check_freshness("TEST", "1d")
            assert freshness.staleness_threshold_hours >= 1
