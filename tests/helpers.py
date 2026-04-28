"""Shared test helpers for strategy and container testing."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pandas as pd

from tests.support.factories.ohlcv_factory import make_ohlcv as _factory_ohlcv


def _synthetic_ohlcv(
    n: int = 500,
    symbol: str = "TEST",
    start: str = "2020-01-01",
    seed: int = 42,
    trend: float = 0.0003,
    vol: float = 0.01,
) -> pd.DataFrame:
    """Generate a deterministic synthetic OHLCV frame for offline tests."""
    if n <= 0:
        return pd.DataFrame(
            columns=[
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
            ],
        )
    return _factory_ohlcv(n=n, symbol=symbol, start=start, seed=seed, trend=trend, vol=vol)


class StubDataProvider:
    """Deterministic offline data provider for tests."""

    def __init__(self, df: pd.DataFrame | None = None) -> None:
        self._df = df if df is not None else _synthetic_ohlcv()

    @property
    def name(self) -> str:
        return "stub"

    @property
    def supported_intervals(self) -> list[str]:
        return ["1d"]

    async def fetch(
        self,
        symbol: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        interval: str = "1d",
    ) -> pd.DataFrame:
        df = self._df.copy()
        if start is not None:
            df = df[df["timestamp"] >= pd.to_datetime(start, utc=True)]
        if end is not None:
            df = df[df["timestamp"] < pd.to_datetime(end, utc=True)]
        return df.reset_index(drop=True)

    def validate(self, df: pd.DataFrame) -> list[str]:
        return []

    async def check_connectivity(self):
        from trade_advisor.data.providers.base import ConnectivityStatus

        return ConnectivityStatus(
            connected=True,
            provider_name=self.name,
            checked_at=datetime.now(UTC),
        )


def strategy_conforms_to_protocol(cls: type, **kwargs: object) -> bool:
    """Runtime-check that *cls* satisfies the Strategy Protocol."""
    from trade_advisor.strategies.interface import Strategy

    instance = cls(**kwargs)
    return isinstance(instance, Strategy)


def assert_no_lookahead_bias(cls: type, **kwargs: object) -> None:
    """Oracle Shuffle + Truncation adversarial check for SE-5 compliance."""
    instance = cls(**kwargs)
    ohlcv_full = _synthetic_ohlcv(n=300, seed=123)
    cutoff = 200

    ohlcv_truncated = ohlcv_full.iloc[:cutoff].copy()
    signals_truncated = instance.generate_signals(ohlcv_truncated)

    rng = np.random.default_rng(99)
    shuffled_future = ohlcv_full.iloc[cutoff:].copy()
    shuffled_idx = rng.permutation(len(shuffled_future))
    ohlcv_shuffled = pd.concat(
        [ohlcv_truncated, shuffled_future.iloc[shuffled_idx].reset_index(drop=True)],
        ignore_index=True,
    )
    signals_shuffled = instance.generate_signals(ohlcv_shuffled)

    pd.testing.assert_series_equal(
        signals_truncated.reset_index(drop=True),
        signals_shuffled.iloc[:cutoff].reset_index(drop=True),
        check_names=False,
        obj="signals up to cutoff",
    )

    signals_full = instance.generate_signals(ohlcv_full)
    pd.testing.assert_series_equal(
        signals_truncated.reset_index(drop=True),
        signals_full.iloc[:cutoff].reset_index(drop=True),
        check_names=False,
        obj="signals at cutoff vs full data",
    )

    non_trivial = signals_truncated.iloc[instance.warmup_period : cutoff - 1]
    assert (non_trivial != 0).any(), (
        "assert_no_lookahead_bias: all signals before cutoff are zero — "
        "warmup_period may equal or exceed cutoff, making this check vacuous"
    )


def bootstrap_test_container(**overrides: object):
    """Pre-wired test container factory with sensible defaults."""
    import dataclasses

    from trade_advisor.core.config import AppConfig
    from trade_advisor.core.container import bootstrap

    cfg = AppConfig()  # type: ignore[call-arg]
    container = bootstrap(config=cfg)
    if overrides:
        container = dataclasses.replace(container, **overrides)
    return container
