"""Shared pytest fixtures."""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest
import structlog

from .helpers import (  # noqa: F401 — re-exported for `from tests.conftest import ...`
    StubDataProvider,
    _synthetic_ohlcv,
    assert_no_lookahead_bias,
    bootstrap_test_container,
    strategy_conforms_to_protocol,
)


@pytest.fixture(autouse=True)
def _reset_structlog():
    """Reset structlog configuration before each test."""
    structlog.reset_defaults()
    yield
    structlog.reset_defaults()


@pytest.fixture
def synthetic_ohlcv() -> pd.DataFrame:
    return _synthetic_ohlcv()


@pytest.fixture
def short_ohlcv() -> pd.DataFrame:
    return _synthetic_ohlcv(n=120)


@pytest.fixture
def fake_fetcher():
    """A fetcher callable matching the get_ohlcv signature, returning synthetic data."""

    def _f(symbol, start=None, end=None, interval="1d"):
        df = _synthetic_ohlcv(n=500, symbol=symbol)
        if start is not None:
            df = df[df["timestamp"] >= pd.to_datetime(start, utc=True)]
        if end is not None:
            df = df[df["timestamp"] < pd.to_datetime(end, utc=True)]
        return df.reset_index(drop=True)

    return _f


@pytest.fixture(autouse=True)
def _inject_csrf_support(monkeypatch: pytest.MonkeyPatch):
    import httpx

    from trade_advisor.web.csrf import CSRF_COOKIE, CSRF_HEADER

    def _add_csrf_header(client: httpx.AsyncClient, kwargs: dict[str, Any]) -> dict[str, Any]:
        csrf_token = client.cookies.get(CSRF_COOKIE)
        if csrf_token is None:
            return kwargs
        headers: dict[str, str] = dict(kwargs.get("headers") or {})
        headers[CSRF_HEADER] = csrf_token
        return {**kwargs, "headers": headers}

    _orig_post = httpx.AsyncClient.post
    _orig_delete = httpx.AsyncClient.delete
    _orig_put = httpx.AsyncClient.put
    _orig_patch = httpx.AsyncClient.patch

    async def _csrf_post(client: httpx.AsyncClient, url: str, **kwargs: Any) -> httpx.Response:
        return await _orig_post(client, url, **_add_csrf_header(client, kwargs))

    async def _csrf_delete(client: httpx.AsyncClient, url: str, **kwargs: Any) -> httpx.Response:
        return await _orig_delete(client, url, **_add_csrf_header(client, kwargs))

    async def _csrf_put(client: httpx.AsyncClient, url: str, **kwargs: Any) -> httpx.Response:
        return await _orig_put(client, url, **_add_csrf_header(client, kwargs))

    async def _csrf_patch(client: httpx.AsyncClient, url: str, **kwargs: Any) -> httpx.Response:
        return await _orig_patch(client, url, **_add_csrf_header(client, kwargs))

    monkeypatch.setattr(httpx.AsyncClient, "post", _csrf_post)
    monkeypatch.setattr(httpx.AsyncClient, "delete", _csrf_delete)
    monkeypatch.setattr(httpx.AsyncClient, "put", _csrf_put)
    monkeypatch.setattr(httpx.AsyncClient, "patch", _csrf_patch)
    yield
