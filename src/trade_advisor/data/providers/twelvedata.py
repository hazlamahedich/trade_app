from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import httpx
import pandas as pd

from trade_advisor.core.config import DataConfig
from trade_advisor.core.errors import ConfigurationError, DataError
from trade_advisor.data.cache import validate_ohlcv
from trade_advisor.data.providers.base import ConnectivityStatus
from trade_advisor.data.sources import CANONICAL_COLUMNS

log = logging.getLogger(__name__)

_BASE_URL = "https://api.twelvedata.com"
_DAILY_CREDIT_LIMIT = 800
_PER_MINUTE_CREDIT_LIMIT = 8


class TwelveDataProvider:
    def __init__(self, api_key: str | None = None, config: DataConfig | None = None) -> None:
        self._api_key = api_key
        cfg = config or DataConfig()
        self._retry_attempts = cfg.retry_attempts
        self._retry_delay_sec = cfg.retry_delay_sec
        self._credits_used_today = 0
        self._credit_reset_date: datetime | None = None

    def _check_credit_reset(self) -> None:
        today = datetime.now(UTC).date()
        if self._credit_reset_date is None or today != self._credit_reset_date:
            self._credits_used_today = 0
            self._credit_reset_date = today

    @property
    def name(self) -> str:
        return "twelvedata"

    @property
    def supported_intervals(self) -> list[str]:
        return ["1d", "1h", "5m", "15m", "30m", "1min"]

    async def fetch(
        self,
        symbol: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        interval: str = "1d",
    ) -> pd.DataFrame:
        if not self._api_key:
            raise ConfigurationError(
                "TwelveData API key not configured. Run: ta config set-key TWELVEDATA_API_KEY",
                details={"provider": "twelvedata"},
            )

        self._check_credit_reset()
        if self._credits_used_today >= _DAILY_CREDIT_LIMIT:
            raise DataError(
                f"TwelveData daily rate limit exceeded for {symbol}. "
                f"Try loading cached data if available.",
                details={"symbol": symbol, "interval": interval, "rate_limit": "daily"},
            )

        params: dict[str, Any] = {
            "symbol": symbol,
            "interval": interval,
            "format": "JSON",
            "apikey": self._api_key,
        }
        if start is not None:
            params["start_date"] = start.strftime("%Y-%m-%d")
        if end is not None:
            params["end_date"] = end.strftime("%Y-%m-%d")

        last_exc: Exception | None = None
        for attempt in range(self._retry_attempts):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(f"{_BASE_URL}/time_series", params=params)

                if response.status_code == 429:
                    raise DataError(
                        f"TwelveData rate limit exceeded for {symbol}. "
                        f"Try loading cached data if available.",
                        details={"symbol": symbol, "interval": interval, "rate_limit": "429"},
                    )

                try:
                    data = response.json()
                except Exception as exc:
                    raise DataError(
                        f"TwelveData returned non-JSON response for {symbol}: {exc}. "
                        f"Try loading cached data if available.",
                        details={"symbol": symbol, "interval": interval},
                    ) from exc

                if data.get("status") == "error":
                    api_msg = data.get("message", "Unknown API error")
                    raise DataError(
                        f"TwelveData API error for {symbol}: {api_msg}. "
                        f"Try loading cached data if available.",
                        details={"symbol": symbol, "interval": interval},
                    )

                values = data.get("values", [])
                if not values:
                    raise DataError(
                        f"TwelveData returned no data for {symbol}. "
                        f"Try loading cached data if available.",
                        details={"symbol": symbol, "interval": interval},
                    )

                self._credits_used_today += 1
                return self._normalize(values, symbol=symbol, interval=interval)

            except DataError:
                raise
            except (httpx.HTTPError, ConnectionError, OSError) as exc:
                last_exc = exc
                if attempt < self._retry_attempts - 1:
                    await asyncio.sleep(self._retry_delay_sec)
            except Exception as exc:
                last_exc = exc
                break

        raise DataError(
            f"Failed to fetch {symbol} ({interval}) from TwelveData after "
            f"{self._retry_attempts} attempts: {last_exc}. "
            f"Try loading cached data if available.",
            details={"symbol": symbol, "interval": interval},
        ) from last_exc

    def _normalize(
        self, values: list[dict[str, str]], *, symbol: str, interval: str
    ) -> pd.DataFrame:
        rows = []
        for v in values:
            try:
                rows.append(
                    {
                        "symbol": symbol,
                        "interval": interval,
                        "timestamp": pd.Timestamp(v["datetime"], tz="UTC"),
                        "open": float(v["open"]),
                        "high": float(v["high"]),
                        "low": float(v["low"]),
                        "close": float(v["close"]),
                        "adj_close": float(v["close"]),
                        "volume": int(float(v.get("volume", "0") or "0")),
                        "source": "twelvedata",
                    }
                )
            except (KeyError, ValueError, TypeError) as exc:
                log.warning("Skipping malformed TwelveData record for %s: %s", symbol, exc)
        if not rows:
            raise DataError(
                f"All TwelveData records malformed for {symbol}",
                details={"symbol": symbol, "interval": interval},
            )
        df = pd.DataFrame(rows, columns=CANONICAL_COLUMNS)
        df = df.sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        return df

    def validate(self, df: pd.DataFrame) -> list[str]:
        if df.empty:
            return []
        warnings = validate_ohlcv(
            df, symbol=str(df["symbol"].iloc[0]) if "symbol" in df.columns else "unknown"
        )

        if "volume" in df.columns and len(df) > 0:
            zero_ratio = (df["volume"] == 0).sum() / len(df)
            if zero_ratio > 0.5:
                symbol = df["symbol"].iloc[0] if "symbol" in df.columns else "unknown"
                warnings.append(
                    f"{symbol}: {zero_ratio:.0%} of bars have zero volume (forex data quality issue)"
                )

        return warnings

    async def check_connectivity(self) -> ConnectivityStatus:
        now = datetime.now(UTC)

        if not self._api_key:
            return ConnectivityStatus(
                connected=False,
                provider_name=self.name,
                checked_at=now,
                error_message="API key not configured",
            )

        self._check_credit_reset()
        if self._credits_used_today >= _DAILY_CREDIT_LIMIT:
            return ConnectivityStatus(
                connected=False,
                provider_name=self.name,
                checked_at=now,
                error_message="Rate limit exceeded",
            )

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{_BASE_URL}/price",
                    params={
                        "symbol": "EUR/USD",
                        "interval": "1min",
                        "outputsize": 1,
                        "apikey": self._api_key,
                    },
                )
            if resp.status_code == 200:
                self._credits_used_today += 1
                return ConnectivityStatus(connected=True, provider_name=self.name, checked_at=now)
            return ConnectivityStatus(
                connected=False,
                provider_name=self.name,
                checked_at=now,
                error_message=f"HTTP {resp.status_code}",
            )
        except Exception as exc:
            return ConnectivityStatus(
                connected=False,
                provider_name=self.name,
                checked_at=now,
                error_message=str(exc),
            )
