from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from trade_advisor.core.errors import ConfigurationError, DataError
from trade_advisor.data.sources import CANONICAL_COLUMNS


def test_twelvedata_provider_implements_protocol():
    from trade_advisor.data.providers.base import DataProvider
    from trade_advisor.data.providers.twelvedata import TwelveDataProvider

    p = TwelveDataProvider(api_key="test-key")
    assert isinstance(p, DataProvider)


def test_twelvedata_provider_name():
    from trade_advisor.data.providers.twelvedata import TwelveDataProvider

    assert TwelveDataProvider(api_key="k").name == "twelvedata"


def test_twelvedata_provider_supported_intervals():
    from trade_advisor.data.providers.twelvedata import TwelveDataProvider

    intervals = TwelveDataProvider(api_key="k").supported_intervals
    assert "1d" in intervals
    assert "1h" in intervals
    assert "5m" in intervals


def _make_client(response_mock: MagicMock) -> AsyncMock:
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get.return_value = response_mock
    return mock_client


def _make_response(status_code: int = 200, json_data: dict | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    return resp


@pytest.mark.asyncio
async def test_twelvedata_fetch_normalizes_json_response():
    from trade_advisor.data.providers.twelvedata import TwelveDataProvider

    api_response = {
        "meta": {"symbol": "EUR/USD"},
        "values": [
            {"datetime": "2024-01-05", "open": "1.0941", "high": "1.0945", "low": "1.0938", "close": "1.0942", "volume": "0"},
            {"datetime": "2024-01-04", "open": "1.0901", "high": "1.0905", "low": "1.0898", "close": "1.0910", "volume": "0"},
        ],
        "status": "ok",
    }

    resp = _make_response(200, api_response)
    client = _make_client(resp)

    with patch("httpx.AsyncClient", return_value=client):
        provider = TwelveDataProvider(api_key="test-key")
        df = await provider.fetch("EUR/USD", start=None, end=None, interval="1d")

        assert list(df.columns) == CANONICAL_COLUMNS
        assert len(df) == 2
        assert df["symbol"].iloc[0] == "EUR/USD"
        assert df["source"].iloc[0] == "twelvedata"


@pytest.mark.asyncio
async def test_twelvedata_fetch_utc_timestamps():
    from trade_advisor.data.providers.twelvedata import TwelveDataProvider

    api_response = {
        "values": [
            {"datetime": "2024-01-05", "open": "1.0", "high": "1.1", "low": "0.9", "close": "1.05", "volume": "100"},
        ],
        "status": "ok",
    }

    resp = _make_response(200, api_response)
    client = _make_client(resp)

    with patch("httpx.AsyncClient", return_value=client):
        provider = TwelveDataProvider(api_key="test-key")
        df = await provider.fetch("EUR/USD", start=None, end=None, interval="1d")
        assert df["timestamp"].dt.tz is not None


@pytest.mark.asyncio
async def test_twelvedata_fetch_forex_pair_format():
    from trade_advisor.data.providers.twelvedata import TwelveDataProvider

    api_response = {
        "values": [
            {"datetime": "2024-01-05", "open": "1.0", "high": "1.1", "low": "0.9", "close": "1.05", "volume": "0"},
        ],
        "status": "ok",
    }

    resp = _make_response(200, api_response)
    client = _make_client(resp)

    with patch("httpx.AsyncClient", return_value=client):
        provider = TwelveDataProvider(api_key="test-key")
        df = await provider.fetch("GBP/JPY", start=None, end=None, interval="1d")
        assert df["symbol"].iloc[0] == "GBP/JPY"


@pytest.mark.asyncio
async def test_twelvedata_api_error_raises_data_error():
    from trade_advisor.data.providers.twelvedata import TwelveDataProvider

    resp = _make_response(200, {"status": "error", "message": "Invalid symbol"})
    client = _make_client(resp)

    with patch("httpx.AsyncClient", return_value=client):
        provider = TwelveDataProvider(api_key="test-key")
        with pytest.raises(DataError, match="Invalid symbol"):
            await provider.fetch("BAD", start=None, end=None, interval="1d")


@pytest.mark.asyncio
async def test_twelvedata_api_key_masked_in_errors():
    from trade_advisor.data.providers.twelvedata import TwelveDataProvider

    provider = TwelveDataProvider(api_key="secret_key_123")
    resp = _make_response(200, {"status": "error", "message": "Invalid symbol"})
    client = _make_client(resp)

    with patch("httpx.AsyncClient", return_value=client):
        try:
            await provider.fetch("BAD", start=None, end=None, interval="1d")
        except DataError as exc:
            assert "secret_key_123" not in str(exc)
            assert "secret_key_123" not in str(exc.details)


@pytest.mark.asyncio
async def test_twelvedata_missing_api_key_raises_config_error():
    from trade_advisor.data.providers.twelvedata import TwelveDataProvider

    provider = TwelveDataProvider(api_key=None)
    with pytest.raises(ConfigurationError, match="API key not configured"):
        await provider.fetch("EUR/USD", start=None, end=None, interval="1d")


@pytest.mark.asyncio
async def test_twelvedata_rate_limit_tracking():
    from trade_advisor.data.providers.twelvedata import TwelveDataProvider, _DAILY_CREDIT_LIMIT

    provider = TwelveDataProvider(api_key="test-key")
    assert provider._credits_used_today == 0

    api_response = {
        "values": [
            {"datetime": "2024-01-05", "open": "1.0", "high": "1.1", "low": "0.9", "close": "1.05", "volume": "0"},
        ],
        "status": "ok",
    }
    resp = _make_response(200, api_response)
    client = _make_client(resp)

    with patch("httpx.AsyncClient", return_value=client):
        await provider.fetch("EUR/USD", start=None, end=None, interval="1d")
        assert provider._credits_used_today == 1


@pytest.mark.asyncio
async def test_twelvedata_rate_limit_exhausted():
    from trade_advisor.data.providers.twelvedata import TwelveDataProvider, _DAILY_CREDIT_LIMIT

    provider = TwelveDataProvider(api_key="test-key")
    provider._credits_used_today = _DAILY_CREDIT_LIMIT
    provider._credit_reset_date = datetime.now(UTC).date()

    with pytest.raises(DataError, match="rate limit"):
        await provider.fetch("EUR/USD", start=None, end=None, interval="1d")


def test_twelvedata_validate_zero_volume_warning():
    from trade_advisor.data.providers.twelvedata import TwelveDataProvider

    df = pd.DataFrame(
        {
            "symbol": ["EUR/USD"] * 10,
            "interval": ["1d"] * 10,
            "timestamp": pd.date_range("2024-01-01", periods=10, tz="UTC"),
            "open": [1.0] * 10,
            "high": [1.1] * 10,
            "low": [0.9] * 10,
            "close": [1.05] * 10,
            "adj_close": [1.05] * 10,
            "volume": [0] * 10,
            "source": ["twelvedata"] * 10,
        }
    )
    provider = TwelveDataProvider(api_key="test-key")
    warnings = provider.validate(df)
    assert any("zero volume" in w.lower() for w in warnings)


@pytest.mark.asyncio
async def test_twelvedata_connectivity_success():
    from trade_advisor.data.providers.twelvedata import TwelveDataProvider

    resp = _make_response(200, {})
    client = _make_client(resp)

    with patch("httpx.AsyncClient", return_value=client):
        provider = TwelveDataProvider(api_key="test-key")
        status = await provider.check_connectivity()
        assert status.connected is True
        assert status.provider_name == "twelvedata"


@pytest.mark.asyncio
async def test_twelvedata_connectivity_failure():
    from trade_advisor.data.providers.twelvedata import TwelveDataProvider

    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.get.side_effect = Exception("Network error")

    with patch("httpx.AsyncClient", return_value=client):
        provider = TwelveDataProvider(api_key="test-key")
        status = await provider.check_connectivity()
        assert status.connected is False
        assert "Network error" in status.error_message


@pytest.mark.asyncio
async def test_twelvedata_429_raises_data_error():
    from trade_advisor.data.providers.twelvedata import TwelveDataProvider

    resp = _make_response(429, {})
    client = _make_client(resp)

    with patch("httpx.AsyncClient", return_value=client):
        provider = TwelveDataProvider(api_key="test-key")
        with pytest.raises(DataError, match="rate limit"):
            await provider.fetch("EUR/USD", start=None, end=None, interval="1d")
