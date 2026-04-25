from __future__ import annotations

import enum
import logging
from dataclasses import dataclass
from datetime import timedelta

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


class AnomalySeverity(enum.Enum):
    WARNING = "WARNING"
    ERROR = "ERROR"


class AnomalyAction(enum.Enum):
    EXCLUDE = "EXCLUDE"
    FLAG = "FLAG"
    IGNORE = "IGNORE"


class ValidationLevel(enum.Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass(frozen=True)
class Anomaly:
    severity: AnomalySeverity
    action: AnomalyAction
    message: str
    symbol: str
    row_index: int | pd.Timestamp | None = None
    column: str | None = None
    value: float | None = None


@dataclass
class ValidationResult:
    level: ValidationLevel
    anomalies: list[Anomaly]
    quality_mask: pd.Series | None = None

    @property
    def error_count(self) -> int:
        return sum(1 for a in self.anomalies if a.severity == AnomalySeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for a in self.anomalies if a.severity == AnomalySeverity.WARNING)

    @property
    def anomaly_count(self) -> int:
        return len(self.anomalies)


_OHLC_COLS = ("open", "high", "low", "close")
_REQUIRED_COLS = frozenset((*_OHLC_COLS, "volume"))


def detect_anomalies(
    df: pd.DataFrame,
    *,
    symbol: str,
    rolling_window: int = 63,
    z_threshold: float = 3.0,
    flat_gap_threshold: float = 0.10,
    adv_threshold: float = 1_000_000,
    adv_window: int = 20,
    expected_interval: timedelta | None = None,
    nan_run_threshold: int = 3,
) -> ValidationResult:
    if df.empty:
        return ValidationResult(level=ValidationLevel.PASS, anomalies=[], quality_mask=None)

    missing = _REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame missing required columns: {sorted(missing)}")

    if "symbol" in df.columns and df["symbol"].nunique() > 1:
        raise ValueError("detect_anomalies requires single-symbol DataFrame")

    if rolling_window < 2:
        raise ValueError(f"rolling_window must be >= 2, got {rolling_window}")
    if z_threshold <= 0:
        raise ValueError(f"z_threshold must be > 0, got {z_threshold}")
    if flat_gap_threshold <= 0:
        raise ValueError(f"flat_gap_threshold must be > 0, got {flat_gap_threshold}")
    if nan_run_threshold < 1:
        raise ValueError(f"nan_run_threshold must be >= 1, got {nan_run_threshold}")

    anomalies: list[Anomaly] = []

    anomalies.extend(_detect_nan_runs(df, symbol, nan_run_threshold))
    anomalies.extend(_detect_duplicate_timestamps(df, symbol))
    anomalies.extend(_detect_nat_timestamps(df, symbol))
    skel = _detect_skeleton_bars(df, symbol)
    skeleton_indices: set[int | pd.Timestamp] = {
        a.row_index for a in skel if a.row_index is not None
    }
    anomalies.extend(skel)
    anomalies.extend(_detect_negative_zero_prices(df, symbol, skeleton_indices))
    anomalies.extend(_detect_negative_volume(df, symbol))
    anomalies.extend(_detect_nan_volume(df, symbol))
    anomalies.extend(_detect_invalid_bars(df, symbol))
    anomalies.extend(_detect_inf_prices(df, symbol))
    anomalies.extend(_detect_zero_volume(df, symbol, adv_threshold, adv_window))

    if len(df) >= 2:
        anomalies.extend(_detect_price_outliers(df, symbol, rolling_window, z_threshold))
        anomalies.extend(_detect_flat_price_gaps(df, symbol, flat_gap_threshold, skeleton_indices))

    if expected_interval is not None and len(df) >= 2:
        anomalies.extend(_detect_timestamp_gaps(df, symbol, expected_interval))

    error_mask_arr = np.zeros(len(df), dtype=bool)
    for a in anomalies:
        if a.severity == AnomalySeverity.ERROR and a.row_index is not None:
            pos = df.index.get_loc(a.row_index)
            if isinstance(pos, int):
                error_mask_arr[pos] = True
            else:
                error_mask_arr[pos] = True

    quality_mask: pd.Series | None = None
    if len(df) > 0:
        quality_mask = pd.Series(error_mask_arr, index=df.index)

    has_errors = any(a.severity == AnomalySeverity.ERROR for a in anomalies)
    has_warnings = any(a.severity == AnomalySeverity.WARNING for a in anomalies)

    if has_errors:
        level = ValidationLevel.FAIL
    elif has_warnings:
        level = ValidationLevel.WARN
    else:
        level = ValidationLevel.PASS

    return ValidationResult(level=level, anomalies=anomalies, quality_mask=quality_mask)


def _detect_nan_runs(df: pd.DataFrame, symbol: str, nan_run_threshold: int) -> list[Anomaly]:
    anomalies: list[Anomaly] = []

    for col in _OHLC_COLS:
        is_nan = df[col].isna()
        if not is_nan.any():
            continue

        groups = (is_nan != is_nan.shift()).cumsum()
        for _gid, group in is_nan.groupby(groups):
            if not group.iloc[0]:
                continue
            run_len = int(group.sum())
            start_idx = group.index[0]
            severity = (
                AnomalySeverity.ERROR if run_len >= nan_run_threshold else AnomalySeverity.WARNING
            )
            action = AnomalyAction.EXCLUDE if run_len >= nan_run_threshold else AnomalyAction.FLAG
            anomalies.append(
                Anomaly(
                    severity=severity,
                    action=action,
                    message=f"NaN run of length {run_len} in '{col}' starting at index {start_idx}",
                    symbol=symbol,
                    row_index=start_idx,
                    column=col,
                )
            )
    return anomalies


def _detect_duplicate_timestamps(df: pd.DataFrame, symbol: str) -> list[Anomaly]:
    if "timestamp" not in df.columns:
        return []

    dupes = df["timestamp"].duplicated(keep=False)
    count = int(dupes.sum())
    if count == 0:
        return []

    anomalies: list[Anomaly] = [
        Anomaly(
            severity=AnomalySeverity.ERROR,
            action=AnomalyAction.EXCLUDE,
            message=f"Duplicate timestamps: {count} duplicate rows detected",
            symbol=symbol,
        )
    ]
    for idx in df.index[dupes]:
        anomalies.append(
            Anomaly(
                severity=AnomalySeverity.ERROR,
                action=AnomalyAction.EXCLUDE,
                message=f"Duplicate timestamp row at index {idx}",
                symbol=symbol,
                row_index=idx,
                column="timestamp",
            )
        )
    return anomalies


def _detect_negative_zero_prices(
    df: pd.DataFrame, symbol: str, skeleton_indices: set[int | pd.Timestamp] | None = None
) -> list[Anomaly]:
    anomalies: list[Anomaly] = []
    _skip = skeleton_indices or set()
    for col in _OHLC_COLS:
        bad_mask = df[col] <= 0
        for idx in df.index[bad_mask]:
            if idx in _skip:
                continue
            anomalies.append(
                Anomaly(
                    severity=AnomalySeverity.ERROR,
                    action=AnomalyAction.EXCLUDE,
                    message=f"Invalid price in '{col}': value {df.loc[idx, col]} <= 0",
                    symbol=symbol,
                    row_index=idx,
                    column=col,
                    value=float(df.loc[idx, col]),
                )
            )
    return anomalies


def _detect_skeleton_bars(df: pd.DataFrame, symbol: str) -> list[Anomaly]:
    skeleton_mask = (
        (df["open"] == 0)
        & (df["high"] == 0)
        & (df["low"] == 0)
        & (df["close"] == 0)
        & (df["volume"] == 0)
    )
    anomalies: list[Anomaly] = []
    for idx in df.index[skeleton_mask]:
        anomalies.append(
            Anomaly(
                severity=AnomalySeverity.ERROR,
                action=AnomalyAction.EXCLUDE,
                message=f"Skeleton bar (all zeros) at index {idx} — data provider placeholder",
                symbol=symbol,
                row_index=idx,
            )
        )
    return anomalies


def _detect_invalid_bars(df: pd.DataFrame, symbol: str) -> list[Anomaly]:
    anomalies: list[Anomaly] = []

    high_low_violation = df["high"] < df["low"]
    for idx in df.index[high_low_violation]:
        anomalies.append(
            Anomaly(
                severity=AnomalySeverity.ERROR,
                action=AnomalyAction.EXCLUDE,
                message=(
                    f"Invalid bar at index {idx}: "
                    f"high ({df.loc[idx, 'high']}) < low ({df.loc[idx, 'low']})"
                ),
                symbol=symbol,
                row_index=idx,
            )
        )

    high_violation = df["high"] < df[["open", "close"]].max(axis=1)
    for idx in df.index[high_violation]:
        anomalies.append(
            Anomaly(
                severity=AnomalySeverity.ERROR,
                action=AnomalyAction.EXCLUDE,
                message=(
                    f"Invalid bar at index {idx}: "
                    f"high ({df.loc[idx, 'high']}) < max(open, close) "
                    f"({max(df.loc[idx, 'open'], df.loc[idx, 'close'])})"
                ),
                symbol=symbol,
                row_index=idx,
            )
        )

    low_violation = df["low"] > df[["open", "close"]].min(axis=1)
    for idx in df.index[low_violation]:
        anomalies.append(
            Anomaly(
                severity=AnomalySeverity.ERROR,
                action=AnomalyAction.EXCLUDE,
                message=(
                    f"Invalid bar at index {idx}: "
                    f"low ({df.loc[idx, 'low']}) > min(open, close) "
                    f"({min(df.loc[idx, 'open'], df.loc[idx, 'close'])})"
                ),
                symbol=symbol,
                row_index=idx,
            )
        )

    return anomalies


def _detect_price_outliers(
    df: pd.DataFrame, symbol: str, rolling_window: int, z_threshold: float
) -> list[Anomaly]:
    if len(df) < 2:
        return []

    anomalies: list[Anomaly] = []

    inf_mask = ~np.isfinite(df["close"])
    for idx in df.index[inf_mask]:
        anomalies.append(
            Anomaly(
                severity=AnomalySeverity.ERROR,
                action=AnomalyAction.EXCLUDE,
                message=f"Non-finite close price at index {idx}: {df.loc[idx, 'close']}",
                symbol=symbol,
                row_index=idx,
                column="close",
                value=float(df.loc[idx, "close"]) if not pd.isna(df.loc[idx, "close"]) else None,
            )
        )

    clean_close = df["close"].where(np.isfinite(df["close"]))
    min_periods = max(5, rolling_window // 2)
    rolling_mean = clean_close.rolling(window=rolling_window, min_periods=min_periods).mean()
    rolling_std = clean_close.rolling(window=rolling_window, min_periods=min_periods).std()

    valid = rolling_std > 0
    z_scores = pd.Series(np.nan, index=df.index)
    z_scores[valid] = (clean_close - rolling_mean)[valid] / rolling_std[valid]

    outlier_mask = z_scores.abs() > z_threshold
    for idx in df.index[outlier_mask]:
        anomalies.append(
            Anomaly(
                severity=AnomalySeverity.ERROR,
                action=AnomalyAction.FLAG,
                message=(
                    f"Price outlier at index {idx}: z-score={z_scores[idx]:.2f}, "
                    f"close={df.loc[idx, 'close']:.4f}, "
                    f"rolling_mean={rolling_mean[idx]:.4f}"
                ),
                symbol=symbol,
                row_index=idx,
                column="close",
                value=float(z_scores[idx]),
            )
        )
    return anomalies


def _detect_flat_price_gaps(
    df: pd.DataFrame,
    symbol: str,
    flat_gap_threshold: float,
    skip_indices: set[int | pd.Timestamp] | None = None,
) -> list[Anomaly]:
    if len(df) < 2:
        return []

    close = df["close"]
    prev_close = close.shift(1)
    safe_prev = prev_close.where(prev_close.abs() > 0)
    pct_change = (close - prev_close).abs() / safe_prev.abs()
    gap_mask = pct_change > flat_gap_threshold
    gap_mask.iloc[0] = False

    _skip = skip_indices or set()
    anomalies: list[Anomaly] = []
    for idx in df.index[gap_mask]:
        if idx in _skip:
            continue
        prev_val = prev_close.loc[idx]
        gap_pct = pct_change.loc[idx]
        anomalies.append(
            Anomaly(
                severity=AnomalySeverity.WARNING,
                action=AnomalyAction.FLAG,
                message=(
                    f"Price gap at index {idx}: {gap_pct:.2%} change "
                    f"(close={close.loc[idx]:.4f}, prev_close={prev_val:.4f})"
                ),
                symbol=symbol,
                row_index=idx,
                column="close",
                value=float(gap_pct),
            )
        )
    return anomalies


def _detect_zero_volume(
    df: pd.DataFrame, symbol: str, adv_threshold: float, adv_window: int
) -> list[Anomaly]:
    zero_mask = df["volume"] == 0
    if not zero_mask.any():
        return []

    if len(df) >= adv_window:
        rolling_adv = df["volume"].rolling(window=adv_window, min_periods=1).mean()
    else:
        rolling_adv = df["volume"].expanding(min_periods=1).mean()

    anomalies: list[Anomaly] = []
    for idx in df.index[zero_mask]:
        adv = rolling_adv.loc[idx]
        if adv > adv_threshold:
            anomalies.append(
                Anomaly(
                    severity=AnomalySeverity.WARNING,
                    action=AnomalyAction.FLAG,
                    message=(
                        f"Zero volume at index {idx}: ADV={adv:,.0f} > threshold "
                        f"{adv_threshold:,.0f}"
                    ),
                    symbol=symbol,
                    row_index=idx,
                    column="volume",
                    value=0.0,
                )
            )
    return anomalies


def _detect_negative_volume(df: pd.DataFrame, symbol: str) -> list[Anomaly]:
    neg_mask = df["volume"] < 0
    anomalies: list[Anomaly] = []
    for idx in df.index[neg_mask]:
        anomalies.append(
            Anomaly(
                severity=AnomalySeverity.ERROR,
                action=AnomalyAction.EXCLUDE,
                message=f"Negative volume at index {idx}: {df.loc[idx, 'volume']}",
                symbol=symbol,
                row_index=idx,
                column="volume",
                value=float(df.loc[idx, "volume"]),
            )
        )
    return anomalies


def _detect_nan_volume(df: pd.DataFrame, symbol: str) -> list[Anomaly]:
    nan_mask = df["volume"].isna()
    anomalies: list[Anomaly] = []
    for idx in df.index[nan_mask]:
        anomalies.append(
            Anomaly(
                severity=AnomalySeverity.ERROR,
                action=AnomalyAction.EXCLUDE,
                message=f"NaN volume at index {idx}",
                symbol=symbol,
                row_index=idx,
                column="volume",
            )
        )
    return anomalies


def _detect_nat_timestamps(df: pd.DataFrame, symbol: str) -> list[Anomaly]:
    if "timestamp" not in df.columns:
        return []
    ts = pd.to_datetime(df["timestamp"], errors="coerce")
    nat_mask = ts.isna()
    anomalies: list[Anomaly] = []
    for idx in df.index[nat_mask]:
        anomalies.append(
            Anomaly(
                severity=AnomalySeverity.ERROR,
                action=AnomalyAction.EXCLUDE,
                message=f"NaT/invalid timestamp at index {idx}",
                symbol=symbol,
                row_index=idx,
                column="timestamp",
            )
        )
    return anomalies


def _detect_inf_prices(df: pd.DataFrame, symbol: str) -> list[Anomaly]:
    anomalies: list[Anomaly] = []
    for col in _OHLC_COLS:
        inf_mask = np.isinf(df[col])
        for idx in df.index[inf_mask]:
            anomalies.append(
                Anomaly(
                    severity=AnomalySeverity.ERROR,
                    action=AnomalyAction.EXCLUDE,
                    message=f"Infinite price in '{col}' at index {idx}: {df.loc[idx, col]}",
                    symbol=symbol,
                    row_index=idx,
                    column=col,
                    value=float(df.loc[idx, col]),
                )
            )
    return anomalies


def _detect_timestamp_gaps(
    df: pd.DataFrame, symbol: str, expected_interval: timedelta
) -> list[Anomaly]:
    if "timestamp" not in df.columns or len(df) < 2:
        return []

    ts = pd.to_datetime(df["timestamp"], errors="coerce")
    gaps = ts.diff().iloc[1:]
    tolerance = expected_interval * 2
    gap_mask = gaps > tolerance

    anomalies: list[Anomaly] = []
    for i in gaps.index[gap_mask]:
        gap_duration = gaps.loc[i]
        anomalies.append(
            Anomaly(
                severity=AnomalySeverity.WARNING,
                action=AnomalyAction.FLAG,
                message=(
                    f"Timestamp gap at index {i}: gap={gap_duration}, expected max={tolerance}"
                ),
                symbol=symbol,
                row_index=i,
            )
        )
    return anomalies


def get_data_freshness(symbol: str, interval: str):
    from trade_advisor.core.config import DatabaseConfig
    from trade_advisor.data.storage import DataRepository
    from trade_advisor.infra.db import DatabaseManager

    config = DatabaseConfig()

    async def _fetch():
        async with DatabaseManager(config) as db:
            repo = DataRepository(db)
            return await repo.check_freshness(symbol, interval)

    import asyncio

    try:
        asyncio.get_running_loop()
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, _fetch()).result()
    except RuntimeError:
        return asyncio.run(_fetch())
