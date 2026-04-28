from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

from trade_advisor.data.validation import (
    Anomaly,
    AnomalyAction,
    AnomalySeverity,
    ValidationLevel,
    ValidationResult,
    detect_anomalies,
)


def _make_df(rows: int = 100, **overrides) -> pd.DataFrame:
    base = {
        "timestamp": pd.date_range("2024-01-01", periods=rows, tz="UTC"),
        "open": np.linspace(100, 110, rows),
        "high": np.linspace(101, 111, rows),
        "low": np.linspace(99, 109, rows),
        "close": np.linspace(100.5, 110.5, rows),
        "volume": np.full(rows, 1_000_000.0),
    }
    base.update(overrides)
    return pd.DataFrame(base)


class TestDetectAnomaliesHappyPath:
    def test_clean_data_passes(self):
        df = _make_df()
        result = detect_anomalies(df, symbol="TEST")
        assert result.level == ValidationLevel.PASS
        assert result.anomaly_count == 0
        assert result.error_count == 0
        assert result.warning_count == 0

    def test_error_mask_clean(self):
        df = _make_df()
        result = detect_anomalies(df, symbol="TEST")
        assert result.error_mask is not None
        assert not result.error_mask.any()


class TestEdgeCases:
    def test_empty_dataframe(self):
        df = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
        result = detect_anomalies(df, symbol="TEST")
        assert result.level == ValidationLevel.PASS
        assert result.anomalies == []
        assert result.error_mask is None

    def test_single_row(self):
        df = pd.DataFrame(
            {
                "timestamp": [pd.Timestamp("2024-01-01", tz="UTC")],
                "open": [100.0],
                "high": [101.0],
                "low": [99.0],
                "close": [100.5],
                "volume": [1e6],
            }
        )
        result = detect_anomalies(df, symbol="TEST")
        assert result.level == ValidationLevel.PASS
        assert result.anomaly_count == 0

    def test_multi_symbol_raises(self):
        df = pd.DataFrame(
            {
                "symbol": ["A", "B"],
                "timestamp": pd.date_range("2024-01-01", periods=2, tz="UTC"),
                "open": [100.0, 200.0],
                "high": [101.0, 201.0],
                "low": [99.0, 199.0],
                "close": [100.5, 200.5],
                "volume": [1e6, 1e6],
            }
        )
        with pytest.raises(ValueError, match="single-symbol"):
            detect_anomalies(df, symbol="TEST")


class TestNaNRuns:
    def test_run_length_1_warning(self):
        df = _make_df(rows=5, close=[100.0, np.nan, 102.0, 103.0, 104.0])
        result = detect_anomalies(df, symbol="TEST")
        nan_anomalies = [a for a in result.anomalies if "NaN" in a.message]
        assert len(nan_anomalies) >= 1
        assert any(a.severity == AnomalySeverity.WARNING for a in nan_anomalies)

    def test_run_length_2_warning(self):
        df = _make_df(rows=5, close=[100.0, np.nan, np.nan, 103.0, 104.0])
        result = detect_anomalies(df, symbol="TEST")
        nan_anomalies = [a for a in result.anomalies if "NaN" in a.message]
        assert len(nan_anomalies) >= 1
        assert any(a.severity == AnomalySeverity.WARNING for a in nan_anomalies)

    def test_run_length_3_error(self):
        df = _make_df(rows=5, close=[100.0, np.nan, np.nan, np.nan, 104.0])
        result = detect_anomalies(df, symbol="TEST")
        nan_anomalies = [a for a in result.anomalies if "NaN" in a.message]
        assert any(a.severity == AnomalySeverity.ERROR for a in nan_anomalies)

    def test_run_length_5_error(self):
        df = _make_df(rows=7, close=[100.0, np.nan, np.nan, np.nan, np.nan, np.nan, 106.0])
        result = detect_anomalies(df, symbol="TEST")
        nan_anomalies = [a for a in result.anomalies if "NaN" in a.message]
        assert any(a.severity == AnomalySeverity.ERROR for a in nan_anomalies)
        assert any("5" in a.message for a in nan_anomalies)


class TestDuplicateTimestamps:
    def test_duplicates_detected(self):
        ts = list(pd.date_range("2024-01-01", periods=5, tz="UTC"))
        ts.append(ts[-1])
        df = pd.DataFrame(
            {
                "timestamp": ts,
                "open": [100.0] * 6,
                "high": [101.0] * 6,
                "low": [99.0] * 6,
                "close": [100.5] * 6,
                "volume": [1e6] * 6,
            }
        )
        result = detect_anomalies(df, symbol="TEST")
        dupe_anomalies = [a for a in result.anomalies if "duplicate" in a.message.lower()]
        assert len(dupe_anomalies) >= 1
        assert dupe_anomalies[0].severity == AnomalySeverity.ERROR


class TestPriceOutliers:
    def test_rolling_zscore_outlier(self):
        close = [100.0] * 62 + [200.0]
        df = _make_df(rows=63, close=close)
        result = detect_anomalies(df, symbol="TEST")
        outlier_anomalies = [a for a in result.anomalies if "outlier" in a.message.lower()]
        assert len(outlier_anomalies) >= 1
        assert outlier_anomalies[0].severity == AnomalySeverity.ERROR

    def test_no_outlier_normal_data(self):
        df = _make_df(rows=100)
        result = detect_anomalies(df, symbol="TEST")
        outlier_anomalies = [a for a in result.anomalies if "outlier" in a.message.lower()]
        assert len(outlier_anomalies) == 0


class TestFlatPriceGaps:
    def test_large_gap_detected(self):
        close = [100.0, 101.0, 102.0, 200.0, 203.0]
        high = [c + 1 for c in close]
        low = [c - 1 for c in close]
        df = _make_df(
            rows=5, close=close, high=high, low=low, open=[100.0, 101.0, 102.0, 200.0, 203.0]
        )
        result = detect_anomalies(df, symbol="TEST")
        gap_anomalies = [a for a in result.anomalies if "gap" in a.message.lower()]
        assert len(gap_anomalies) >= 1


class TestZeroVolume:
    def test_zero_volume_high_adv_flagged(self):
        vol = [2e6] * 10 + [0, 2e6, 0, 2e6, 0]
        df = _make_df(rows=15, volume=vol)
        result = detect_anomalies(df, symbol="TEST")
        vol_anomalies = [
            a
            for a in result.anomalies
            if "volume" in a.message.lower() or "zero" in a.message.lower()
        ]
        assert len(vol_anomalies) >= 1
        assert all(a.severity == AnomalySeverity.WARNING for a in vol_anomalies)

    def test_zero_volume_low_adv_not_flagged(self):
        vol = [500.0] * 20 + [0, 500.0, 0, 500.0, 0]
        df = _make_df(rows=25, volume=vol)
        result = detect_anomalies(df, symbol="TEST")
        vol_anomalies = [
            a
            for a in result.anomalies
            if "volume" in a.message.lower() or "zero" in a.message.lower()
        ]
        assert len(vol_anomalies) == 0


class TestNegativeZeroPrices:
    def test_negative_close_detected(self):
        df = _make_df(rows=5, close=[100.0, 101.0, -1.0, 103.0, 104.0])
        result = detect_anomalies(df, symbol="TEST")
        invalid = [a for a in result.anomalies if "Invalid price" in a.message]
        assert len(invalid) >= 1
        assert all(a.severity == AnomalySeverity.ERROR for a in invalid)

    def test_zero_open_detected(self):
        df = _make_df(rows=5, open=[100.0, 0, 102.0, 103.0, 104.0])
        result = detect_anomalies(df, symbol="TEST")
        invalid = [a for a in result.anomalies if "Invalid price" in a.message]
        assert len(invalid) >= 1


class TestSkeletonBars:
    def test_skeleton_bar_detected(self):
        df = _make_df(rows=5)
        df.loc[2, ["open", "high", "low", "close", "volume"]] = 0
        result = detect_anomalies(df, symbol="TEST")
        skeleton = [a for a in result.anomalies if "Skeleton" in a.message]
        assert len(skeleton) >= 1
        assert skeleton[0].severity == AnomalySeverity.ERROR


class TestInvalidBars:
    def test_high_less_than_close(self):
        df = _make_df(rows=5, high=[99.0] * 5, close=[100.5] * 5)
        result = detect_anomalies(df, symbol="TEST")
        invalid = [a for a in result.anomalies if "Invalid bar" in a.message]
        assert len(invalid) >= 1

    def test_low_greater_than_open(self):
        df = _make_df(rows=5, low=[102.0] * 5, open=[100.0] * 5)
        result = detect_anomalies(df, symbol="TEST")
        invalid = [a for a in result.anomalies if "Invalid bar" in a.message]
        assert len(invalid) >= 1


class TestTimestampGaps:
    def test_gap_detected_with_expected_interval(self):
        ts = list(pd.date_range("2024-01-01", periods=4, freq="B", tz="UTC"))
        ts.insert(2, ts[1] + timedelta(days=10))
        df = pd.DataFrame(
            {
                "timestamp": ts,
                "open": [100.0] * 5,
                "high": [101.0] * 5,
                "low": [99.0] * 5,
                "close": [100.5] * 5,
                "volume": [1e6] * 5,
            }
        )
        result = detect_anomalies(df, symbol="TEST", expected_interval=timedelta(days=1))
        gap_anomalies = [a for a in result.anomalies if "Timestamp gap" in a.message]
        assert len(gap_anomalies) >= 1

    def test_no_gap_detection_without_interval(self):
        ts = list(pd.date_range("2024-01-01", periods=4, freq="B", tz="UTC"))
        ts.insert(2, ts[1] + timedelta(days=10))
        df = pd.DataFrame(
            {
                "timestamp": ts,
                "open": [100.0] * 5,
                "high": [101.0] * 5,
                "low": [99.0] * 5,
                "close": [100.5] * 5,
                "volume": [1e6] * 5,
            }
        )
        result = detect_anomalies(df, symbol="TEST")
        gap_anomalies = [a for a in result.anomalies if "Timestamp gap" in a.message]
        assert len(gap_anomalies) == 0


class TestInputImmutability:
    def test_dataframe_not_modified(self):
        df = _make_df(rows=50)
        original = df.copy()
        detect_anomalies(df, symbol="TEST")
        pd.testing.assert_frame_equal(df, original)

    def test_dataframe_with_anomalies_not_modified(self):
        df = _make_df(rows=5, close=[100.0, np.nan, np.nan, np.nan, 104.0])
        original = df.copy()
        detect_anomalies(df, symbol="TEST")
        pd.testing.assert_frame_equal(df, original)


class TestQualityMask:
    def test_error_mask_marks_error_rows(self):
        df = _make_df(rows=5, close=[100.0, np.nan, np.nan, np.nan, 104.0])
        result = detect_anomalies(df, symbol="TEST")
        assert result.error_mask is not None
        assert result.error_mask.any()
        nan_errors = [
            a
            for a in result.anomalies
            if a.severity == AnomalySeverity.ERROR and a.row_index is not None
        ]
        for a in nan_errors:
            assert result.error_mask.iloc[a.row_index]

    def test_error_mask_all_false_on_pass(self):
        df = _make_df(rows=10)
        result = detect_anomalies(df, symbol="TEST")
        assert result.error_mask is not None
        assert not result.error_mask.any()


class TestValidationResult:
    def test_level_fail_with_error(self):
        result = ValidationResult(
            level=ValidationLevel.FAIL,
            anomalies=[
                Anomaly(
                    severity=AnomalySeverity.ERROR,
                    action=AnomalyAction.EXCLUDE,
                    message="test",
                    symbol="T",
                )
            ],
        )
        assert result.error_count == 1
        assert result.warning_count == 0

    def test_level_warn_with_warning(self):
        result = ValidationResult(
            level=ValidationLevel.WARN,
            anomalies=[
                Anomaly(
                    severity=AnomalySeverity.WARNING,
                    action=AnomalyAction.FLAG,
                    message="test",
                    symbol="T",
                )
            ],
        )
        assert result.error_count == 0
        assert result.warning_count == 1


class TestAnomalySeverity:
    def test_all_anomalies_have_severity(self):
        df = _make_df(rows=5, volume=[1e6, 0, 1e6, 0, 1e6])
        result = detect_anomalies(df, symbol="TEST")
        for a in result.anomalies:
            assert a.severity in (AnomalySeverity.WARNING, AnomalySeverity.ERROR)

    def test_all_anomalies_have_action(self):
        df = _make_df(rows=5, volume=[1e6, 0, 1e6, 0, 1e6])
        result = detect_anomalies(df, symbol="TEST")
        for a in result.anomalies:
            assert a.action in (AnomalyAction.EXCLUDE, AnomalyAction.FLAG, AnomalyAction.IGNORE)
