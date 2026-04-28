from __future__ import annotations

from unittest.mock import patch

import pytest

from tests.conftest import _synthetic_ohlcv


def test_yahoo_provider_implements_protocol():
    from trade_advisor.data.providers.base import DataProvider
    from trade_advisor.data.providers.yahoo import YahooProvider

    yf = YahooProvider()
    assert isinstance(yf, DataProvider)


def test_yahoo_provider_name():
    from trade_advisor.data.providers.yahoo import YahooProvider

    assert YahooProvider().name == "yahoo"


def test_yahoo_provider_supported_intervals():
    from trade_advisor.data.providers.yahoo import YahooProvider

    intervals = YahooProvider().supported_intervals
    assert "1d" in intervals
    assert "1h" in intervals


@pytest.mark.asyncio
async def test_yahoo_provider_fetch_returns_canonical_columns():
    from trade_advisor.data.providers.yahoo import YahooProvider
    from trade_advisor.data.sources import CANONICAL_COLUMNS

    df = _synthetic_ohlcv(n=5)
    with patch("trade_advisor.data.providers.yahoo.fetch_yfinance", return_value=df):
        provider = YahooProvider()
        result = await provider.fetch("TEST", start=None, end=None, interval="1d")
        assert list(result.columns) == CANONICAL_COLUMNS


@pytest.mark.asyncio
async def test_yahoo_provider_fetch_utc_timestamps():
    from trade_advisor.data.providers.yahoo import YahooProvider

    df = _synthetic_ohlcv(n=5)
    with patch("trade_advisor.data.providers.yahoo.fetch_yfinance", return_value=df):
        provider = YahooProvider()
        result = await provider.fetch("TEST", start=None, end=None, interval="1d")
        assert result["timestamp"].dt.tz is not None


def test_yahoo_provider_validate_delegates():
    from trade_advisor.data.providers.yahoo import YahooProvider

    df = _synthetic_ohlcv(n=10)
    provider = YahooProvider()
    warnings = provider.validate(df)
    assert isinstance(warnings, list)


@pytest.mark.asyncio
async def test_yahoo_provider_connectivity_success():
    from trade_advisor.data.providers.yahoo import YahooProvider

    df = _synthetic_ohlcv(n=1)
    with patch("trade_advisor.data.providers.yahoo.fetch_yfinance", return_value=df):
        provider = YahooProvider()
        status = await provider.check_connectivity()
        assert status.connected is True
        assert status.provider_name == "yahoo"


@pytest.mark.asyncio
async def test_yahoo_provider_connectivity_failure():
    from trade_advisor.data.providers.yahoo import YahooProvider

    with patch(
        "trade_advisor.data.providers.yahoo.fetch_yfinance",
        side_effect=RuntimeError("Network error"),
    ):
        provider = YahooProvider()
        status = await provider.check_connectivity()
        assert status.connected is False
        assert "Network error" in status.error_message


@pytest.mark.asyncio
async def test_yahoo_provider_retry_on_transient_error():
    from trade_advisor.core.config import DataConfig
    from trade_advisor.data.providers.yahoo import YahooProvider

    config = DataConfig(retry_attempts=3, retry_delay_sec=0.01)
    df = _synthetic_ohlcv(n=1)
    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise RuntimeError("Transient error")
        return df

    with patch("trade_advisor.data.providers.yahoo.fetch_yfinance", side_effect=side_effect):
        provider = YahooProvider(config=config)
        result = await provider.fetch("TEST", start=None, end=None, interval="1d")
        assert len(result) == 1
        assert call_count == 3


@pytest.mark.asyncio
async def test_yahoo_provider_fetch_raises_after_all_retries():
    from trade_advisor.core.config import DataConfig
    from trade_advisor.core.errors import DataError
    from trade_advisor.data.providers.yahoo import YahooProvider

    config = DataConfig(retry_attempts=2, retry_delay_sec=0.01)
    with patch(
        "trade_advisor.data.providers.yahoo.fetch_yfinance", side_effect=RuntimeError("fail")
    ):
        provider = YahooProvider(config=config)
        with pytest.raises(DataError, match="Failed to fetch"):
            await provider.fetch("TEST", start=None, end=None, interval="1d")
