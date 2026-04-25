from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

import pandas as pd
from pydantic import BaseModel, Field


class ConnectivityStatus(BaseModel):
    connected: bool
    provider_name: str
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    error_message: str | None = None


@runtime_checkable
class DataProvider(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def supported_intervals(self) -> list[str]: ...

    async def fetch(
        self,
        symbol: str,
        *,
        start: datetime | None,
        end: datetime | None,
        interval: str,
    ) -> pd.DataFrame: ...

    def validate(self, df: pd.DataFrame) -> list[str]: ...

    async def check_connectivity(self) -> ConnectivityStatus: ...
