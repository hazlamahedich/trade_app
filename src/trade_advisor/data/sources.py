"""yfinance data source adapter.

Returns a canonical OHLCV DataFrame with UTC timestamps.
Network access is isolated to this module.
"""
from __future__ import annotations

import logging
from datetime import datetime

import pandas as pd

log = logging.getLogger(__name__)

CANONICAL_COLUMNS = [
    "symbol", "interval", "timestamp",
    "open", "high", "low", "close", "adj_close", "volume",
    "source",
]


def fetch_yfinance(
    symbol: str,
    start: str | datetime | None = None,
    end: str | datetime | None = None,
    interval: str = "1d",
) -> pd.DataFrame:
    """Fetch OHLCV from yfinance and normalize to canonical schema.

    Args:
        symbol: Ticker in yfinance format (e.g. 'AAPL', 'EURUSD=X', 'BTC-USD').
        start: Inclusive start date. If None, yfinance default (max history) is used.
        end: Exclusive end date. If None, today.
        interval: '1d', '1h', etc. See yfinance docs.

    Returns:
        DataFrame in canonical OHLCV format, sorted by timestamp, deduped.
    """
    # Import lazily so unit tests that don't hit the network don't need yfinance installed.
    import yfinance as yf

    log.info("yfinance fetch: %s interval=%s start=%s end=%s", symbol, interval, start, end)
    raw = yf.download(
        tickers=symbol,
        start=start,
        end=end,
        interval=interval,
        auto_adjust=False,
        progress=False,
        threads=False,
        group_by="column",
    )

    if raw is None or raw.empty:
        raise RuntimeError(f"yfinance returned no data for {symbol}")

    df = _normalize(raw, symbol=symbol, interval=interval)
    return df


def _normalize(raw: pd.DataFrame, *, symbol: str, interval: str) -> pd.DataFrame:
    """Normalize a yfinance DataFrame to canonical schema."""
    df = raw.copy()

    # yfinance sometimes returns MultiIndex columns even for a single symbol.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.rename(columns={
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Adj Close": "adj_close",
        "Volume": "volume",
    })

    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"yfinance response missing columns: {missing}")

    if "adj_close" not in df.columns:
        df["adj_close"] = df["close"]

    df = df.reset_index().rename(columns={df.index.name or "Date": "timestamp", "Date": "timestamp", "Datetime": "timestamp"})
    # After reset_index the date column may be named 'Date' or 'Datetime'; handle both.
    if "timestamp" not in df.columns:
        # Fall back to whichever datetime-like column exists.
        dt_cols = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
        if not dt_cols:
            raise ValueError("Could not locate timestamp column in yfinance response")
        df = df.rename(columns={dt_cols[0]: "timestamp"})

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df["symbol"] = symbol
    df["interval"] = interval
    df["source"] = "yfinance"

    df = df[CANONICAL_COLUMNS].sort_values("timestamp").drop_duplicates("timestamp")
    df["volume"] = df["volume"].fillna(0).astype("int64")
    for col in ("open", "high", "low", "close", "adj_close"):
        df[col] = df[col].astype("float64")
    return df.reset_index(drop=True)
