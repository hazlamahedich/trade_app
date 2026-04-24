"""Parquet-backed OHLCV cache.

Layout:
    data_cache/ohlcv/<SYMBOL>/<INTERVAL>/part.parquet

Incremental updates: if a cache file exists, we fetch only the range after
the last cached timestamp and append + dedupe.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pandas as pd

from trade_advisor.config import DATA_CACHE_DIR
from trade_advisor.data.sources import CANONICAL_COLUMNS, fetch_yfinance

log = logging.getLogger(__name__)

OHLCV_ROOT = DATA_CACHE_DIR / "ohlcv"


def cache_path(symbol: str, interval: str) -> Path:
    safe_symbol = symbol.replace("/", "_")
    return OHLCV_ROOT / safe_symbol / interval / "part.parquet"


def load_cached(symbol: str, interval: str) -> pd.DataFrame | None:
    p = cache_path(symbol, interval)
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


def save_cache(df: pd.DataFrame, symbol: str, interval: str) -> Path:
    p = cache_path(symbol, interval)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p, index=False)
    return p


def _range_covered(cached: pd.DataFrame, start, end) -> bool:
    first_ts = cached["timestamp"].min()
    last_ts = cached["timestamp"].max()
    if start is not None and pd.to_datetime(start, utc=True) < first_ts:
        return False
    return not (end is not None and pd.to_datetime(end, utc=True) > last_ts)


def get_ohlcv(
    symbol: str,
    start: str | datetime | None = None,
    end: str | datetime | None = None,
    interval: str = "1d",
    *,
    refresh: bool = False,
    fetcher: Callable[..., pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """Return OHLCV DataFrame, using cache when possible.

    If refresh=True, ignore cache and fetch fresh.
    """
    fetcher = fetcher or fetch_yfinance
    cached = None if refresh else load_cached(symbol, interval)

    if cached is None:
        log.info("Cache miss for %s %s; fetching full history.", symbol, interval)
        fresh = fetcher(symbol, start=start, end=end, interval=interval)
        save_cache(fresh, symbol, interval)
        return _slice(fresh, start, end)

    if _range_covered(cached, start, end):
        log.info("Cache hit for %s; requested range fully covered.", symbol)
        return _slice(cached, start, end)

    last_ts = cached["timestamp"].max()
    incr_start = (
        last_ts.tz_convert("UTC").to_pydatetime() if last_ts.tzinfo else last_ts.to_pydatetime()
    )
    log.info("Cache hit for %s; incremental fetch from %s", symbol, incr_start)
    try:
        fresh = fetcher(symbol, start=incr_start, end=end, interval=interval)
    except RuntimeError as exc:
        if "no data" in str(exc).lower():
            log.warning("Incremental fetch returned no rows; using cache as-is.")
            return _slice(cached, start, end)
        raise

    combined = (
        pd.concat([cached, fresh], ignore_index=True)
        .drop_duplicates(subset=["timestamp"], keep="last")
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
    save_cache(combined, symbol, interval)
    return _slice(combined, start, end)


def _slice(df: pd.DataFrame, start, end) -> pd.DataFrame:
    out = df
    if start is not None:
        start_ts = pd.to_datetime(start, utc=True)
        out = out[out["timestamp"] >= start_ts]
    if end is not None:
        end_ts = pd.to_datetime(end, utc=True)
        out = out[out["timestamp"] < end_ts]
    return out.reset_index(drop=True)


# ---------- Validation ----------


class DataValidationError(ValueError):
    pass


def validate_ohlcv(df: pd.DataFrame, symbol: str) -> list[str]:
    """Return a list of validation warnings; raise on fatal errors."""
    warnings: list[str] = []

    missing = set(CANONICAL_COLUMNS) - set(df.columns)
    if missing:
        raise DataValidationError(f"{symbol}: missing columns {missing}")

    if df.empty:
        raise DataValidationError(f"{symbol}: empty dataframe")

    if df["timestamp"].duplicated().any():
        raise DataValidationError(f"{symbol}: duplicate timestamps")

    if not df["timestamp"].is_monotonic_increasing:
        raise DataValidationError(f"{symbol}: timestamps not sorted")

    for col in ("open", "high", "low", "close", "adj_close"):
        if (df[col] <= 0).any():
            warnings.append(f"{symbol}: non-positive values in {col}")
        if df[col].isna().any():
            warnings.append(f"{symbol}: NaN values in {col}")

    # high must be >= low, >= open, >= close
    bad_hl = (df["high"] < df["low"]).sum()
    if bad_hl:
        warnings.append(f"{symbol}: {bad_hl} rows where high < low")

    return warnings
