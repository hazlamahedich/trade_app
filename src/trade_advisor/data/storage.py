from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import pandas as pd
from pydantic import BaseModel

from trade_advisor.core.config import DataConfig
from trade_advisor.core.errors import DataError
from trade_advisor.infra.db import DatabaseManager

log = logging.getLogger(__name__)

_OHLCV_INSERT_COLUMNS = [
    "symbol",
    "interval",
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "adj_close",
    "volume",
    "source",
    "split_factor",
    "div_factor",
]

_UPSERT_SQL = f"""
INSERT OR REPLACE INTO ohlcv_cache
    ({", ".join(_OHLCV_INSERT_COLUMNS)})
VALUES ({", ".join(["?" for _ in _OHLCV_INSERT_COLUMNS])})
"""

_DATA_SOURCE_UPSERT_SQL = """
INSERT OR REPLACE INTO data_sources (name, provider_type, last_fetch, supported_intervals)
VALUES (?, ?, CURRENT_TIMESTAMP, ?)
"""

_EXISTING_SOURCE_SQL = """
SELECT timestamp, source, adj_close FROM ohlcv_cache
WHERE symbol = ? AND interval = ? AND timestamp IN ({placeholders})
"""

_LOAD_SQL = """
SELECT {columns} FROM ohlcv_cache
WHERE symbol = ? AND interval = ?
"""

_LOAD_RANGE_SQL = """
SELECT {columns} FROM ohlcv_cache
WHERE symbol = ? AND interval = ? AND timestamp >= ? AND timestamp < ?
"""

_LOAD_START_SQL = """
SELECT {columns} FROM ohlcv_cache
WHERE symbol = ? AND interval = ? AND timestamp >= ?
"""

_LOAD_END_SQL = """
SELECT {columns} FROM ohlcv_cache
WHERE symbol = ? AND interval = ? AND timestamp < ?
"""

_FRESHNESS_SQL = """
SELECT MAX(created_at) FROM ohlcv_cache WHERE symbol = ? AND interval = ?
"""

_COUNT_SQL = """
SELECT COUNT(*) FROM ohlcv_cache WHERE symbol = ? AND interval = ?
"""


class FreshnessStatus(BaseModel):
    symbol: str
    interval: str
    last_updated: datetime | None = None
    bar_count: int = 0
    is_stale: bool = True
    staleness_threshold_hours: int


class DataRepository:
    def __init__(self, db: DatabaseManager, config: DataConfig | None = None) -> None:
        self._db = db
        cfg = config or DataConfig()
        self._staleness_threshold_sec = cfg.staleness_threshold_sec

    async def store(self, df: pd.DataFrame, *, provider_name: str | None = None) -> None:
        if df.empty:
            return

        df = df.copy()
        if "split_factor" not in df.columns:
            df["split_factor"] = 1.0
        if "div_factor" not in df.columns:
            df["div_factor"] = 1.0

        cols = list(df.columns)
        for col in _OHLCV_INSERT_COLUMNS:
            if col not in cols:
                raise DataError(f"Missing required column: {col}")

        incoming_source = str(df["source"].iloc[0]) if "source" in cols else provider_name
        rows = self._prepare_rows(df)

        existing_adj_close = await self._get_existing_adj_close(df)

        if existing_adj_close:
            for i, row in enumerate(rows):
                ts = row[2]
                if ts in existing_adj_close:
                    existing_source, existing_adj = existing_adj_close[ts]
                    if incoming_source != existing_source and existing_adj is not None:
                        rows[i] = (
                            row[0],
                            row[1],
                            row[2],
                            row[3],
                            row[4],
                            row[5],
                            row[6],
                            existing_adj,
                            row[8],
                            row[9],
                            row[10],
                            row[11],
                        )

        batch_size = 1000
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            await self._db.write_many(_UPSERT_SQL, batch)

        if provider_name:
            intervals = ",".join(sorted(df["interval"].unique()))
            await self._db.write(
                _DATA_SOURCE_UPSERT_SQL,
                (provider_name, incoming_source, intervals),
            )

    def _prepare_rows(self, df: pd.DataFrame) -> list[tuple]:
        values = df[_OHLCV_INSERT_COLUMNS].values.tolist()
        return [tuple(row) for row in values]

    async def _get_existing_adj_close(
        self, df: pd.DataFrame
    ) -> dict[object, tuple[str, float | None]]:
        symbol = df["symbol"].iloc[0]
        interval = df["interval"].iloc[0]
        timestamps = df["timestamp"].tolist()

        if not timestamps:
            return {}

        batch_size = 500
        result: dict[object, tuple[str, float | None]] = {}

        for i in range(0, len(timestamps), batch_size):
            chunk = timestamps[i : i + batch_size]
            placeholders = ", ".join(["?" for _ in chunk])
            sql = _EXISTING_SOURCE_SQL.format(placeholders=placeholders)
            params = (symbol, interval, *chunk)
            rows = await self._db.read(sql, params)
            for row in rows:
                result[row[0]] = (row[1], row[2])

        return result

    async def load(
        self,
        symbol: str,
        interval: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> pd.DataFrame | None:
        cols = ", ".join(_OHLCV_INSERT_COLUMNS)
        if start is not None and end is not None:
            sql = _LOAD_RANGE_SQL.format(columns=cols)
            rows = await self._db.read(sql, (symbol, interval, start, end))
        elif start is not None:
            sql = _LOAD_START_SQL.format(columns=cols)
            rows = await self._db.read(sql, (symbol, interval, start))
        elif end is not None:
            sql = _LOAD_END_SQL.format(columns=cols)
            rows = await self._db.read(sql, (symbol, interval, end))
        else:
            sql = _LOAD_SQL.format(columns=cols)
            rows = await self._db.read(sql, (symbol, interval))

        if not rows:
            return None

        df = pd.DataFrame(rows, columns=_OHLCV_INSERT_COLUMNS)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        for col in ("open", "high", "low", "close", "adj_close"):
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype("int64")
        return df.sort_values("timestamp").reset_index(drop=True)

    async def check_freshness(self, symbol: str, interval: str) -> FreshnessStatus:
        count_rows = await self._db.read(_COUNT_SQL, (symbol, interval))
        bar_count = count_rows[0][0] if count_rows else 0

        freshness_rows = await self._db.read(_FRESHNESS_SQL, (symbol, interval))
        last_updated = freshness_rows[0][0] if freshness_rows and freshness_rows[0][0] else None

        threshold_hours = max(1, self._staleness_threshold_sec // 3600)
        is_stale = True
        if last_updated is not None:
            if isinstance(last_updated, str):
                last_updated = datetime.fromisoformat(last_updated)
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=UTC)
            elapsed = datetime.now(UTC) - last_updated
            is_stale = elapsed > timedelta(seconds=self._staleness_threshold_sec)

        return FreshnessStatus(
            symbol=symbol,
            interval=interval,
            last_updated=last_updated,
            bar_count=bar_count,
            is_stale=is_stale,
            staleness_threshold_hours=threshold_hours,
        )


def load_from_cache(symbol: str, interval: str) -> pd.DataFrame | None:
    raise NotImplementedError("Use DataRepository.load() with an async context")


def check_freshness(symbol: str, interval: str, *, max_age_hours: int = 24) -> FreshnessStatus:
    raise NotImplementedError("Use DataRepository.check_freshness() with an async context")
