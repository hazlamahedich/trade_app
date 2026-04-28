from __future__ import annotations

import pytest

from tests.conftest import _synthetic_ohlcv


@pytest.mark.asyncio
async def test_store_and_load_roundtrip():
    from trade_advisor.core.config import DatabaseConfig
    from trade_advisor.data.storage import DataRepository
    from trade_advisor.infra.db import DatabaseManager

    config = DatabaseConfig(path=":memory:")
    async with DatabaseManager(config) as db:
        repo = DataRepository(db)
        df = _synthetic_ohlcv(n=10)
        await repo.store(df, provider_name="synthetic")
        loaded = await repo.load("TEST", "1d")
        assert loaded is not None
        assert len(loaded) == 10


@pytest.mark.asyncio
async def test_store_upserts_existing_data():
    from trade_advisor.core.config import DatabaseConfig
    from trade_advisor.data.storage import DataRepository
    from trade_advisor.infra.db import DatabaseManager

    config = DatabaseConfig(path=":memory:")
    async with DatabaseManager(config) as db:
        repo = DataRepository(db)
        df1 = _synthetic_ohlcv(n=10, seed=1)
        await repo.store(df1, provider_name="synthetic")

        df2 = _synthetic_ohlcv(n=10, seed=2)
        await repo.store(df2, provider_name="synthetic")

        loaded = await repo.load("TEST", "1d")
        assert loaded is not None
        assert len(loaded) == 10


@pytest.mark.asyncio
async def test_load_returns_none_for_missing_symbol():
    from trade_advisor.core.config import DatabaseConfig
    from trade_advisor.data.storage import DataRepository
    from trade_advisor.infra.db import DatabaseManager

    config = DatabaseConfig(path=":memory:")
    async with DatabaseManager(config) as db:
        repo = DataRepository(db)
        result = await repo.load("NONEXISTENT", "1d")
        assert result is None


@pytest.mark.asyncio
async def test_load_filters_by_date_range():
    from datetime import UTC, datetime

    from trade_advisor.core.config import DatabaseConfig
    from trade_advisor.data.storage import DataRepository
    from trade_advisor.infra.db import DatabaseManager

    config = DatabaseConfig(path=":memory:")
    async with DatabaseManager(config) as db:
        repo = DataRepository(db)
        df = _synthetic_ohlcv(n=100)
        await repo.store(df, provider_name="synthetic")

        start = datetime(2020, 2, 1, tzinfo=UTC)
        end = datetime(2020, 3, 1, tzinfo=UTC)
        loaded = await repo.load("TEST", "1d", start=start, end=end)
        assert loaded is not None
        assert loaded["timestamp"].min() >= start
        assert loaded["timestamp"].max() < end


@pytest.mark.asyncio
async def test_check_freshness_stale():
    from trade_advisor.core.config import DatabaseConfig, DataConfig
    from trade_advisor.data.storage import DataRepository
    from trade_advisor.infra.db import DatabaseManager

    config = DatabaseConfig(path=":memory:")
    data_config = DataConfig(staleness_threshold_sec=1)
    async with DatabaseManager(config) as db:
        repo = DataRepository(db, config=data_config)
        df = _synthetic_ohlcv(n=5)
        await repo.store(df, provider_name="synthetic")

        import asyncio

        await asyncio.sleep(1.1)

        freshness = await repo.check_freshness("TEST", "1d")
        assert freshness.is_stale is True


@pytest.mark.asyncio
async def test_check_freshness_fresh():
    from trade_advisor.core.config import DatabaseConfig, DataConfig
    from trade_advisor.data.storage import DataRepository
    from trade_advisor.infra.db import DatabaseManager

    config = DatabaseConfig(path=":memory:")
    data_config = DataConfig(staleness_threshold_sec=3600)
    async with DatabaseManager(config) as db:
        repo = DataRepository(db, config=data_config)
        df = _synthetic_ohlcv(n=5)
        await repo.store(df, provider_name="synthetic")

        freshness = await repo.check_freshness("TEST", "1d")
        assert freshness.is_stale is False


@pytest.mark.asyncio
async def test_check_freshness_never_fetched():
    from trade_advisor.core.config import DatabaseConfig
    from trade_advisor.data.storage import DataRepository
    from trade_advisor.infra.db import DatabaseManager

    config = DatabaseConfig(path=":memory:")
    async with DatabaseManager(config) as db:
        repo = DataRepository(db)
        freshness = await repo.check_freshness("NO_DATA", "1d")
        assert freshness.last_updated is None
        assert freshness.is_stale is True
        assert freshness.bar_count == 0


@pytest.mark.asyncio
async def test_identical_fetch_produces_identical_cache():
    import pandas as pd

    from trade_advisor.core.config import DatabaseConfig
    from trade_advisor.data.storage import DataRepository
    from trade_advisor.infra.db import DatabaseManager

    config = DatabaseConfig(path=":memory:")
    async with DatabaseManager(config) as db:
        repo = DataRepository(db)
        df = _synthetic_ohlcv(n=10)
        await repo.store(df, provider_name="synthetic")
        loaded1 = await repo.load("TEST", "1d")

        await repo.store(df, provider_name="synthetic")
        loaded2 = await repo.load("TEST", "1d")

        pd.testing.assert_frame_equal(loaded1, loaded2)


@pytest.mark.asyncio
async def test_data_sources_registry_updated_on_store():
    from trade_advisor.core.config import DatabaseConfig
    from trade_advisor.data.storage import DataRepository
    from trade_advisor.infra.db import DatabaseManager

    config = DatabaseConfig(path=":memory:")
    async with DatabaseManager(config) as db:
        repo = DataRepository(db)
        df = _synthetic_ohlcv(n=5)
        await repo.store(df, provider_name="synthetic")

        rows = await db.read(
            "SELECT name, provider_type FROM data_sources WHERE name = ?", ("synthetic",)
        )
        assert len(rows) == 1
        assert rows[0][0] == "synthetic"


@pytest.mark.asyncio
async def test_store_atomicity_rollback_on_error():
    import pandas as pd

    from trade_advisor.core.config import DatabaseConfig
    from trade_advisor.core.errors import DataError
    from trade_advisor.data.storage import DataRepository
    from trade_advisor.infra.db import DatabaseManager

    config = DatabaseConfig(path=":memory:")
    async with DatabaseManager(config) as db:
        repo = DataRepository(db)
        df = pd.DataFrame(
            {
                "symbol": ["TEST"] * 5,
                "interval": ["1d"] * 5,
                "timestamp": pd.date_range("2024-01-01", periods=5, tz="UTC"),
                "open": [100.0] * 5,
                "high": [101.0] * 5,
                "low": [99.0] * 5,
                "close": [100.5] * 5,
                "adj_close": [100.5] * 5,
                "volume": [1000] * 5,
                "source": ["test"] * 5,
            }
        )
        await repo.store(df, provider_name="test")

        bad_df = df.copy()
        bad_df.drop(columns=["close"], inplace=True)
        with pytest.raises(DataError, match="Missing required column"):
            await repo.store(bad_df, provider_name="test")

        loaded = await repo.load("TEST", "1d")
        assert loaded is not None
        assert len(loaded) == 5


@pytest.mark.asyncio
async def test_cache_partition_case_sensitivity():
    from trade_advisor.core.config import DatabaseConfig
    from trade_advisor.data.storage import DataRepository
    from trade_advisor.infra.db import DatabaseManager

    config = DatabaseConfig(path=":memory:")
    async with DatabaseManager(config) as db:
        repo = DataRepository(db)

        df_lower = _synthetic_ohlcv(n=5, symbol="spy")
        await repo.store(df_lower, provider_name="test")

        df_upper = _synthetic_ohlcv(n=5, symbol="SPY")
        await repo.store(df_upper, provider_name="test")

        lower = await repo.load("spy", "1d")
        upper = await repo.load("SPY", "1d")
        assert lower is not None
        assert upper is not None
