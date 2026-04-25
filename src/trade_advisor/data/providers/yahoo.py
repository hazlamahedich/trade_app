from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

import pandas as pd

from trade_advisor.core.config import DataConfig
from trade_advisor.core.errors import DataError
from trade_advisor.data.cache import validate_ohlcv
from trade_advisor.data.providers.base import ConnectivityStatus
from trade_advisor.data.sources import fetch_yfinance

log = logging.getLogger(__name__)


class YahooProvider:
    def __init__(self, config: DataConfig | None = None) -> None:
        cfg = config or DataConfig()
        self._retry_attempts = cfg.retry_attempts
        self._retry_delay_sec = cfg.retry_delay_sec

    @property
    def name(self) -> str:
        return "yahoo"

    @property
    def supported_intervals(self) -> list[str]:
        return ["1d", "1h", "5m", "15m", "30m", "60m", "1wk", "1mo"]

    async def fetch(
        self,
        symbol: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        interval: str = "1d",
    ) -> pd.DataFrame:
        last_exc: Exception | None = None
        for attempt in range(self._retry_attempts):
            try:
                return await asyncio.to_thread(
                    fetch_yfinance, symbol, start=start, end=end, interval=interval
                )
            except (RuntimeError, ConnectionError, OSError) as exc:
                last_exc = exc
                if attempt < self._retry_attempts - 1:
                    await asyncio.sleep(self._retry_delay_sec)
            except Exception as exc:
                last_exc = exc
                break
        raise DataError(
            f"Failed to fetch {symbol} ({interval}) after {self._retry_attempts} attempts: {last_exc}. "
            f"Try loading cached data if available.",
            details={"symbol": symbol, "interval": interval},
        ) from last_exc

    def validate(self, df: pd.DataFrame) -> list[str]:
        if df.empty:
            return []
        return validate_ohlcv(
            df, symbol=str(df["symbol"].iloc[0]) if "symbol" in df.columns else "unknown"
        )

    async def check_connectivity(self) -> ConnectivityStatus:
        now = datetime.now(UTC)
        try:
            end = datetime.now(UTC)
            start = end - timedelta(days=5)
            await asyncio.to_thread(fetch_yfinance, "SPY", start=start, end=end, interval="1d")
            return ConnectivityStatus(connected=True, provider_name=self.name, checked_at=now)
        except Exception as exc:
            return ConnectivityStatus(
                connected=False,
                provider_name=self.name,
                checked_at=now,
                error_message=str(exc),
            )
