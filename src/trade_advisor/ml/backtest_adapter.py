"""ML-based strategy signal bridge — PredictionProvider Protocol and MLStrategy adapter.

This module defines the contract between the backtest engine and ML prediction
sources.  The ``PredictionProvider`` Protocol specifies what predictions look like;
``MLStrategy`` wraps any conforming provider as a ``Strategy`` Protocol implementation.

Dependency direction: ``ml/`` imports from ``strategies/``; nothing in ``strategies/``
or ``backtest/`` imports from ``ml/``.
"""

from __future__ import annotations

import enum
import logging
from typing import Protocol, runtime_checkable

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PredictionProvider Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class PredictionProvider(Protocol):
    """Contract for ML prediction sources.

    Implementations receive OHLCV data and return float predictions in
    ``[-1.0, +1.0]`` aligned with the OHLCV index.  Normalization /
    calibration is the caller's responsibility (Epic 5).
    """

    def predict(self, ohlcv: pd.DataFrame) -> pd.Series:
        """Return float predictions in ``[-1.0, +1.0]`` aligned with *ohlcv* index."""
        ...


# ---------------------------------------------------------------------------
# SignalMode enum
# ---------------------------------------------------------------------------


class SignalMode(enum.StrEnum):
    CONTINUOUS = "continuous"
    DISCRETE = "discrete"


# ---------------------------------------------------------------------------
# MLStrategyConfig
# ---------------------------------------------------------------------------


class MLStrategyConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    signal_mode: SignalMode = SignalMode.CONTINUOUS
    long_threshold: float = Field(default=0.3, ge=0.0, le=1.0)
    short_threshold: float = Field(default=-0.3, ge=-1.0, le=0.0)
    warmup_period: int = Field(default=0, ge=0)
    prediction_source_id: str = "unknown"

    @model_validator(mode="after")
    def thresholds_valid(self) -> MLStrategyConfig:
        if self.short_threshold >= self.long_threshold:
            raise ValueError(
                f"short_threshold ({self.short_threshold}) must be < long_threshold ({self.long_threshold})"
            )
        if self.long_threshold <= 0.0:
            raise ValueError(f"long_threshold ({self.long_threshold}) must be > 0.0")
        return self


# ---------------------------------------------------------------------------
# MLStrategy — Strategy Protocol adapter
# ---------------------------------------------------------------------------


class MLStrategy:
    """Wraps a ``PredictionProvider`` as a ``Strategy`` Protocol implementation.

    The adapter applies signal conversion (continuous or discrete), NaN → 0.0
    mapping, length/timestamp alignment, and a mandatory 1-bar shift for
    lookahead protection.
    """

    def __init__(
        self,
        provider: PredictionProvider,
        config: MLStrategyConfig | None = None,
    ) -> None:
        self._provider = provider
        self._config = config or MLStrategyConfig()
        self.name: str = f"ml_adapter:{self._config.prediction_source_id}"

    def __repr__(self) -> str:
        return f"MLStrategy({self.name!r})"

    @property
    def information_latency(self) -> int:
        return 1

    @property
    def warmup_period(self) -> int:
        return self._config.warmup_period

    @property
    def config(self) -> MLStrategyConfig:
        return self._config

    def generate_signals(self, ohlcv: pd.DataFrame) -> pd.Series:
        """Generate trading signals from ML predictions.

        Returns a ``pd.Series[float]`` in ``[-1.0, +1.0]`` aligned with
        *ohlcv* index, shifted by 1 bar to prevent lookahead bias.
        """
        if ohlcv.empty:
            return pd.Series(dtype="float64", name="signal")

        raw_predictions = self._safe_predict(ohlcv)

        predictions = self._align_predictions(raw_predictions, ohlcv)

        predictions = predictions.fillna(0.0)

        clipped = predictions.clip(-1.0, 1.0)
        if not clipped.equals(predictions):
            log.warning(
                "ta:ml_adapter:clipped out_of_range_count=%d",
                int((predictions != clipped).sum()),
            )
        predictions = clipped

        if self._config.signal_mode == SignalMode.DISCRETE:
            signals = self._discretize(predictions)
        else:
            signals = predictions

        signals = signals.shift(1).fillna(0.0)

        if self._config.warmup_period > 0:
            signals.iloc[: self._config.warmup_period] = 0.0

        signals = signals.astype("float64")
        signals.name = "signal"
        signals.index = ohlcv.index

        return signals

    def _safe_predict(self, ohlcv: pd.DataFrame) -> pd.Series:
        """Call provider.predict with defensive error handling."""
        try:
            raw = self._provider.predict(ohlcv)
        except Exception as exc:
            log.error("ta:ml_adapter:predict_failed err=%s", exc)
            return pd.Series(0.0, index=ohlcv.index, dtype="float64")

        if not isinstance(raw, pd.Series):
            log.warning(
                "ta:ml_adapter:bad_return_type got=%s expected=Series",
                type(raw).__name__,
            )
            return pd.Series(0.0, index=ohlcv.index, dtype="float64")

        if not pd.api.types.is_numeric_dtype(raw.dtype):
            log.warning("ta:ml_adapter:bad_dtype got=%s", raw.dtype)
            return pd.Series(0.0, index=ohlcv.index, dtype="float64")

        return raw

    def _align_predictions(self, predictions: pd.Series, ohlcv: pd.DataFrame) -> pd.Series:
        """Align predictions to OHLCV index, handling length/timestamp mismatches."""
        if len(predictions) == len(ohlcv) and predictions.index.equals(ohlcv.index):
            result = predictions.copy()
            result.index = ohlcv.index
            return result

        if len(predictions) > len(ohlcv):
            if isinstance(predictions.index, (pd.RangeIndex, pd.DatetimeIndex)):
                result = predictions.iloc[: len(ohlcv)].copy()
                result.index = ohlcv.index[: len(result)]
                return result
            result = predictions.reindex(ohlcv.index, method=None).fillna(0.0)
            return result

        if len(predictions) < len(ohlcv):
            if isinstance(predictions.index, pd.DatetimeIndex) and isinstance(
                ohlcv.index, pd.DatetimeIndex
            ):
                predictions = self._sanitise_for_ffill(predictions)
                log.warning(
                    "ta:ml_adapter:short_predictions ohlcv_bars=%d pred_bars=%d strategy=ffill",
                    len(ohlcv),
                    len(predictions),
                )
                result = predictions.reindex(ohlcv.index, method="ffill").fillna(0.0)
                return result

            pad_count = len(ohlcv) - len(predictions)
            log.warning(
                "ta:ml_adapter:short_predictions padded=%d ohlcv_bars=%d pred_bars=%d",
                pad_count,
                len(ohlcv),
                len(predictions),
            )
            result = pd.Series(0.0, index=ohlcv.index, dtype="float64")
            result.iloc[: len(predictions)] = predictions.values
            return result

        if isinstance(predictions.index, pd.DatetimeIndex) and isinstance(
            ohlcv.index, pd.DatetimeIndex
        ):
            predictions = self._sanitise_for_ffill(predictions)
            result = predictions.reindex(ohlcv.index, method="ffill").fillna(0.0)
            return result

        log.warning("ta:ml_adapter:positional_fallback ohlcv_bars=%d pred_bars=%d", len(ohlcv), len(predictions))
        result = pd.Series(0.0, index=ohlcv.index, dtype="float64")
        common_len = min(len(predictions), len(ohlcv))
        result.iloc[:common_len] = predictions.iloc[:common_len].values
        return result

    @staticmethod
    def _sanitise_for_ffill(predictions: pd.Series) -> pd.Series:
        """Deduplicate and sort DatetimeIndex so reindex(method='ffill') is safe."""
        if predictions.index.has_duplicates:
            dup_count = int(predictions.index.duplicated().sum())
            log.warning("ta:ml_adapter:dedup count=%d", dup_count)
            predictions = predictions[~predictions.index.duplicated(keep="last")]
        if not predictions.index.is_monotonic_increasing:
            predictions = predictions.sort_index()
        return predictions

    def _discretize(self, predictions: pd.Series) -> pd.Series:
        """Map continuous predictions to discrete ``{-1.0, 0.0, +1.0}``."""
        signals = pd.Series(0.0, index=predictions.index, dtype="float64")
        signals[predictions >= self._config.long_threshold] = 1.0
        signals[predictions <= self._config.short_threshold] = -1.0
        return signals

    def to_config(self) -> MLStrategyConfig:
        return self._config

    @classmethod
    def from_config(cls, config: MLStrategyConfig, provider: PredictionProvider) -> MLStrategy:
        return cls(provider=provider, config=config)


# ---------------------------------------------------------------------------
# FakePredictionProvider implementations (testing only)
# ---------------------------------------------------------------------------


class ConstantPredictionProvider:
    """Always returns the same prediction value."""

    def __init__(self, value: float) -> None:
        self.value = value

    def predict(self, ohlcv: pd.DataFrame) -> pd.Series:
        return pd.Series(self.value, index=ohlcv.index, dtype="float64")


class AlternatingPredictionProvider:
    """Cycles through a list of prediction values."""

    def __init__(self, values: list[float]) -> None:
        if not values:
            raise ValueError("values must not be empty")
        self.values = values

    def predict(self, ohlcv: pd.DataFrame) -> pd.Series:
        n = len(ohlcv)
        tiled = (self.values * ((n // len(self.values)) + 1))[:n]
        return pd.Series(tiled, index=ohlcv.index, dtype="float64")


class NoisyPredictionProvider:
    """Random predictions with a fixed seed for reproducibility."""

    def __init__(self, seed: int = 42, noise_std: float = 0.3) -> None:
        self.seed = seed
        self.noise_std = noise_std

    def predict(self, ohlcv: pd.DataFrame) -> pd.Series:
        rng = np.random.default_rng(self.seed)
        raw = rng.normal(0.0, self.noise_std, size=len(ohlcv))
        return pd.Series(raw, index=ohlcv.index, dtype="float64")


class SparsePredictionProvider:
    """Wraps a base provider and introduces NaN gaps."""

    def __init__(
        self,
        base: PredictionProvider,
        fill_fraction: float = 0.5,
        seed: int = 0,
    ) -> None:
        if not 0.0 <= fill_fraction <= 1.0:
            raise ValueError("fill_fraction must be in [0.0, 1.0]")
        self.base = base
        self.fill_fraction = fill_fraction
        self.seed = seed

    def predict(self, ohlcv: pd.DataFrame) -> pd.Series:
        result = self.base.predict(ohlcv).copy()
        n = len(result)
        rng = np.random.default_rng(self.seed)
        mask = rng.random(n) > self.fill_fraction
        result.iloc[mask.nonzero()[0]] = np.nan
        return result


class NaNPredictionProvider:
    """Returns NaN at specified integer positions."""

    def __init__(self, nan_positions: list[int]) -> None:
        if not nan_positions:
            raise ValueError("nan_positions must not be empty")
        for pos in nan_positions:
            if pos < 0:
                raise ValueError(f"nan_positions must be non-negative, got {pos}")
        self.nan_positions = nan_positions

    def predict(self, ohlcv: pd.DataFrame) -> pd.Series:
        result = pd.Series(0.5, index=ohlcv.index, dtype="float64")
        for pos in self.nan_positions:
            if pos < len(result):
                result.iloc[pos] = np.nan
        return result
