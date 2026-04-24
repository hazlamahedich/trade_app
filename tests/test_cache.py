"""Tests for cache + validators using synthetic data (offline)."""

from __future__ import annotations

import pandas as pd
import pytest

from trade_advisor.data import cache as cache_mod
from trade_advisor.data.cache import (
    DataValidationError,
    get_ohlcv,
    load_cached,
    save_cache,
    validate_ohlcv,
)


@pytest.fixture(autouse=True)
def _isolate_cache(tmp_path, monkeypatch):
    """Redirect the cache root to a tmp dir for every test."""
    monkeypatch.setattr(cache_mod, "OHLCV_ROOT", tmp_path / "ohlcv")


def test_validate_ok(synthetic_ohlcv):
    warnings = validate_ohlcv(synthetic_ohlcv, "TEST")
    assert warnings == []


def test_validate_detects_duplicates(synthetic_ohlcv):
    df = pd.concat([synthetic_ohlcv, synthetic_ohlcv.iloc[[0]]], ignore_index=True)
    with pytest.raises(DataValidationError, match="duplicate"):
        validate_ohlcv(df, "TEST")


def test_validate_detects_unsorted(synthetic_ohlcv):
    df = synthetic_ohlcv.iloc[::-1].reset_index(drop=True)
    with pytest.raises(DataValidationError, match="not sorted"):
        validate_ohlcv(df, "TEST")


def test_save_and_load_roundtrip(synthetic_ohlcv):
    save_cache(synthetic_ohlcv, "TEST", "1d")
    loaded = load_cached("TEST", "1d")
    assert loaded is not None
    assert len(loaded) == len(synthetic_ohlcv)
    assert list(loaded.columns) == list(synthetic_ohlcv.columns)


def test_get_ohlcv_uses_fetcher_on_miss(fake_fetcher):
    df = get_ohlcv("TEST", start="2020-01-01", interval="1d", fetcher=fake_fetcher)
    assert not df.empty

    # Subsequent call should hit cache; pass a fetcher that would raise if used
    def _forbidden(*a, **kw):
        raise AssertionError("should not refetch")

    df2 = get_ohlcv("TEST", start="2020-01-01", interval="1d", fetcher=_forbidden)
    assert len(df2) == len(df)


def test_get_ohlcv_slices_by_date(fake_fetcher):
    full = get_ohlcv("TEST", interval="1d", fetcher=fake_fetcher)
    sliced = get_ohlcv("TEST", start="2021-01-01", interval="1d", fetcher=fake_fetcher)
    assert len(sliced) < len(full)
    assert sliced["timestamp"].min() >= pd.Timestamp("2021-01-01", tz="UTC")
