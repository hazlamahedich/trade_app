"""ATDD red-phase: Story 1.5 — Data Provider Interface & Yahoo Finance.

All tests are SKIPPED (TDD red phase). Remove when implementing Story 1.5.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


class TestStory15DataProvider:
    """Story 1.5: DataProvider Protocol, Yahoo Finance, caching."""

    @pytest.mark.skip(reason="ATDD red phase — Story 1.5 not implemented")
    def test_data_provider_protocol_exists(self):
        from trade_advisor.data.providers.base import DataProvider

        assert hasattr(DataProvider, "fetch")
        assert hasattr(DataProvider, "validate")

    @pytest.mark.skip(reason="ATDD red phase — Story 1.5 not implemented")
    def test_yahoo_provider_implements_protocol(self):
        from trade_advisor.data.providers.base import DataProvider
        from trade_advisor.data.providers.yahoo import YahooProvider

        yf = YahooProvider()
        assert isinstance(yf, DataProvider)

    @pytest.mark.skip(reason="ATDD red phase — Story 1.5 not implemented")
    def test_fetch_returns_ohlcv_dataframe(self):
        from trade_advisor.data.providers.yahoo import YahooProvider

        provider = YahooProvider()
        mock_df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=5, tz="UTC"),
            "open": [100.0] * 5,
            "high": [101.0] * 5,
            "low": [99.0] * 5,
            "close": [100.5] * 5,
            "volume": [1000000] * 5,
            "adj_close": [100.5] * 5,
        })
        with patch.object(provider, "fetch", return_value=mock_df):
            df = provider.fetch("SPY", start="2024-01-01", end="2024-01-07", interval="1d")
            assert not df.empty
            assert "close" in df.columns
            assert "timestamp" in df.columns

    @pytest.mark.skip(reason="ATDD red phase — Story 1.5 not implemented")
    def test_cached_data_loads_without_network(self):
        from trade_advisor.data.providers.yahoo import YahooProvider
        from trade_advisor.data.storage import load_from_cache

        with patch("trade_advisor.data.providers.yahoo.YahooProvider.fetch") as mock_fetch:
            mock_fetch.return_value = pd.DataFrame({
                "timestamp": pd.date_range("2024-01-01", periods=5, tz="UTC"),
                "open": [100.0] * 5,
                "high": [101.0] * 5,
                "low": [99.0] * 5,
                "close": [100.5] * 5,
                "volume": [1000000] * 5,
                "adj_close": [100.5] * 5,
                "symbol": "SPY",
                "interval": "1d",
            })
            provider = YahooProvider()
            provider.fetch("SPY", start="2024-01-01", interval="1d")

        cached = load_from_cache("SPY", "1d")
        assert cached is not None
        assert len(cached) == 5

    @pytest.mark.skip(reason="ATDD red phase — Story 1.5 not implemented")
    def test_connectivity_status_displayed_when_unreachable(self):
        from trade_advisor.data.providers.yahoo import YahooProvider

        provider = YahooProvider()
        with patch.object(provider, "fetch", side_effect=RuntimeError("Network unreachable")):
            status = provider.check_connectivity()
            assert status.connected is False

    @pytest.mark.skip(reason="ATDD red phase — Story 1.5 not implemented")
    def test_stale_data_detected_and_flagged(self):
        from datetime import UTC, datetime, timedelta

        from trade_advisor.data.storage import check_freshness

        stale_time = datetime.now(UTC) - timedelta(days=7)
        freshness = check_freshness("SPY", "1d", max_age_hours=24)
        assert freshness.is_stale is True or freshness.last_updated < stale_time

    @pytest.mark.skip(reason="ATDD red phase — Story 1.5 not implemented")
    def test_identical_fetch_produces_identical_cache(self):
        from trade_advisor.data.providers.yahoo import YahooProvider

        provider = YahooProvider()
        mock_df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=5, tz="UTC"),
            "open": [100.0] * 5,
            "high": [101.0] * 5,
            "low": [99.0] * 5,
            "close": [100.5] * 5,
            "volume": [1000000] * 5,
            "adj_close": [100.5] * 5,
        })
        with patch.object(provider, "fetch", return_value=mock_df):
            df1 = provider.fetch("TESTSTALE", start="2024-01-01", interval="1d")
            df2 = provider.fetch("TESTSTALE", start="2024-01-01", interval="1d")

        pd.testing.assert_frame_equal(df1, df2)

    @pytest.mark.skip(reason="ATDD red phase — Story 1.5 not implemented")
    def test_pluggable_provider_interface(self):
        """Alternative data sources register via DataProvider Protocol (DL-4)."""
        from trade_advisor.data.providers.base import DataProvider
        from trade_advisor.data.providers.registry import register_provider

        class MockProvider:
            def fetch(self, symbol, **kwargs):
                return pd.DataFrame()

            def validate(self, df):
                return []

        register_provider("mock", MockProvider)
