"""Market regime stratification using a two-axis model.

**Trend axis**: 60-bar rolling regression slope of log prices.
**Volatility axis**: 21-bar rolling realized vol vs. 252-day percentile.

Provides a :class:`RegimeClassifier` protocol for Epic 3/5 extensibility,
and a default :class:`SimpleRegimeClassifier` implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import numpy as np
import pandas as pd


@dataclass
class RegimeStratification:
    labels: dict[str, pd.Series] = field(default_factory=dict)

    def __contains__(self, key: str) -> bool:
        return key in self.labels

    def __getitem__(self, key: str) -> pd.Series:
        return self.labels[key]

    def __iter__(self):
        return iter(self.labels)

    def keys(self) -> list[str]:
        return list(self.labels.keys())


@runtime_checkable
class RegimeClassifier(Protocol):
    def classify(self, prices: pd.Series) -> pd.Series: ...

    @property
    def regime_labels(self) -> tuple[str, ...]: ...


class SimpleRegimeClassifier:
    def __init__(self, trend_window: int = 60, vol_window: int = 21, lookback: int = 252):
        self._trend_window = trend_window
        self._vol_window = vol_window
        self._lookback = lookback

    @property
    def regime_labels(self) -> tuple[str, ...]:
        return (
            "trending",
            "mean_reverting",
            "high_vol",
            "low_vol",
        )

    def classify(self, prices: pd.Series) -> pd.Series:
        masks = self.stratify(prices)
        labels = pd.Series("unknown", index=prices.index, dtype="object")
        for label, mask in masks.items():
            labels[mask] = label
        return labels

    def stratify(self, close: pd.Series) -> dict[str, pd.Series]:
        n = len(close)
        min_bars = self._trend_window

        empty_mask = pd.Series(False, index=close.index)

        if n < min_bars:
            return {
                "trending": empty_mask.copy(),
                "mean_reverting": empty_mask.copy(),
                "high_vol": empty_mask.copy(),
                "low_vol": empty_mask.copy(),
            }

        log_prices = np.log(close.astype(float).clip(lower=1e-10))
        x = np.arange(self._trend_window, dtype=float)

        rolling_slope = log_prices.rolling(self._trend_window).apply(
            lambda w: np.polyfit(x, w, 1)[0], raw=True
        )

        slope_std = rolling_slope.std()
        threshold = slope_std * 0.5 if np.isfinite(slope_std) and slope_std > 0 else 0.0

        trending_up = rolling_slope > threshold
        trending_down = rolling_slope < -threshold
        trending = trending_up | trending_down
        mean_reverting = ~trending & ~rolling_slope.isna()

        rolling_vol = close.pct_change(fill_method=None).rolling(self._vol_window).std() * np.sqrt(252)

        vol_75 = rolling_vol.rolling(self._lookback, min_periods=60).quantile(0.75)
        vol_25 = rolling_vol.rolling(self._lookback, min_periods=60).quantile(0.25)

        high_vol = rolling_vol > vol_75
        low_vol = rolling_vol < vol_25

        result: dict[str, pd.Series] = {}
        min_days = 60

        for name, mask in [
            ("trending", trending),
            ("mean_reverting", mean_reverting),
            ("high_vol", high_vol),
            ("low_vol", low_vol),
        ]:
            bool_mask = mask.fillna(False).astype(bool)
            if bool_mask.sum() >= min_days:
                result[name] = bool_mask
            else:
                result[name] = empty_mask.copy()

        return result


def stratify_by_regime(
    ohlcv: pd.DataFrame,
    signals: pd.Series,
) -> RegimeStratification:
    if "adj_close" in ohlcv.columns:
        close = ohlcv["adj_close"].astype(float)
    elif "close" in ohlcv.columns:
        close = ohlcv["close"].astype(float)
    else:
        close = pd.Series(dtype=float)

    if len(close) < 60:
        empty = pd.Series(False, index=close.index if len(close) > 0 else pd.Index([]))
        return RegimeStratification(
            labels={
                "trending": empty.copy(),
                "mean_reverting": empty.copy(),
                "high_vol": empty.copy(),
                "low_vol": empty.copy(),
            }
        )

    classifier = SimpleRegimeClassifier()
    labels = classifier.stratify(close)

    return RegimeStratification(labels=labels)
