"""ATDD tests: Story 1.5 — Data Provider Interface & Yahoo Finance.

Tests are now unskipped as Story 1.5 is implemented.
"""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from tests.conftest import _synthetic_ohlcv


class TestStory15DataProvider:
    """Story 1.5: DataProvider Protocol, Yahoo Finance, caching."""

    def test_data_provider_protocol_exists(self):
        from trade_advisor.data.providers.base import DataProvider

        assert hasattr(DataProvider, "fetch")
        assert hasattr(DataProvider, "validate")

    def test_yahoo_provider_implements_protocol(self):
        from trade_advisor.data.providers.base import DataProvider
        from trade_advisor.data.providers.yahoo import YahooProvider

        yf = YahooProvider()
        assert isinstance(yf, DataProvider)

    @pytest.mark.asyncio
    async def test_fetch_returns_ohlcv_dataframe(self):
        from trade_advisor.data.providers.yahoo import YahooProvider

        provider = YahooProvider()
        df = _synthetic_ohlcv(n=5)
        with patch("trade_advisor.data.providers.yahoo.fetch_yfinance", return_value=df):
            result = await provider.fetch(
                "SPY", start="2024-01-01", end="2024-01-07", interval="1d"
            )
            assert not result.empty
            assert "close" in result.columns
            assert "timestamp" in result.columns

    @pytest.mark.asyncio
    async def test_cached_data_loads_without_network(self):
        from trade_advisor.core.config import DatabaseConfig
        from trade_advisor.data.storage import DataRepository
        from trade_advisor.infra.db import DatabaseManager

        config = DatabaseConfig(path=":memory:")
        async with DatabaseManager(config) as db:
            repo = DataRepository(db)
            df = _synthetic_ohlcv(n=5, symbol="SPY")
            await repo.store(df, provider_name="yahoo")
            cached = await repo.load("SPY", "1d")
            assert cached is not None
            assert len(cached) == 5

    @pytest.mark.asyncio
    async def test_connectivity_status_displayed_when_unreachable(self):
        from trade_advisor.data.providers.yahoo import YahooProvider

        provider = YahooProvider()
        with patch(
            "trade_advisor.data.providers.yahoo.fetch_yfinance",
            side_effect=RuntimeError("Network unreachable"),
        ):
            status = await provider.check_connectivity()
            assert status.connected is False

    @pytest.mark.asyncio
    async def test_stale_data_detected_and_flagged(self):
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
    async def test_identical_fetch_produces_identical_cache(self):
        from trade_advisor.data.providers.yahoo import YahooProvider

        provider = YahooProvider()
        df = _synthetic_ohlcv(n=5, symbol="TESTSTALE")
        with patch("trade_advisor.data.providers.yahoo.fetch_yfinance", return_value=df):
            df1 = await provider.fetch("TESTSTALE", start="2024-01-01", interval="1d")
            df2 = await provider.fetch("TESTSTALE", start="2024-01-01", interval="1d")

        pd.testing.assert_frame_equal(df1, df2)

    def test_pluggable_provider_interface(self):
        """Alternative data sources register via DataProvider Protocol (DL-4)."""
        from trade_advisor.data.providers.registry import _providers, register_provider

        class MockProvider:
            @property
            def name(self) -> str:
                return "mock"

            @property
            def supported_intervals(self) -> list[str]:
                return ["1d"]

            async def fetch(self, symbol, *, start=None, end=None, interval="1d"):
                return pd.DataFrame()

            def validate(self, df):
                return []

            async def check_connectivity(self):
                from trade_advisor.data.providers.base import ConnectivityStatus

                return ConnectivityStatus(connected=True, provider_name="mock")

        register_provider("mock_atdd", MockProvider)
        assert "mock_atdd" in _providers
        _providers.pop("mock_atdd")
