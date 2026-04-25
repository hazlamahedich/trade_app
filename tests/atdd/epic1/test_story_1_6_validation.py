"""ATDD tests: Story 1.6 — Data Validation & Anomaly Detection."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError


class TestStory16DataValidation:
    """Story 1.6: Anomaly detection, bar validity, HTMX/Preact bridge."""

    def test_nan_runs_detected(self):
        from trade_advisor.data.validation import detect_anomalies

        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=10, tz="UTC"),
                "open": [100.0] * 10,
                "high": [101.0] * 10,
                "low": [99.0] * 10,
                "close": [100.5, np.nan, np.nan, np.nan, 100.0, 100.5, 101.0, 101.5, 102.0, 102.5],
                "volume": [1e6] * 10,
            }
        )
        result = detect_anomalies(df, symbol="TEST")
        nan_anomalies = [a for a in result.anomalies if "NaN" in a.message or "nan" in a.message]
        assert len(nan_anomalies) > 0

    def test_duplicate_timestamps_detected(self):
        from trade_advisor.data.validation import detect_anomalies

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
        assert len(dupe_anomalies) > 0

    def test_price_gap_beyond_threshold_detected(self):
        from trade_advisor.data.validation import detect_anomalies

        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=5, tz="UTC"),
                "open": [100.0, 101.0, 102.0, 200.0, 203.0],
                "high": [101.0, 102.0, 103.0, 201.0, 204.0],
                "low": [99.0, 100.0, 101.0, 199.0, 202.0],
                "close": [101.0, 102.0, 103.0, 201.0, 204.0],
                "volume": [1e6] * 5,
            }
        )
        result = detect_anomalies(df, symbol="TEST")
        gap_anomalies = [a for a in result.anomalies if "gap" in a.message.lower()]
        assert len(gap_anomalies) > 0

    def test_zero_volume_bars_detected(self):
        from trade_advisor.data.validation import detect_anomalies

        n = 25
        vol = [2e6] * 20 + [0, 2e6, 0, 2e6, 0]
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=n, tz="UTC"),
                "open": [100.0] * n,
                "high": [101.0] * n,
                "low": [99.0] * n,
                "close": [100.5] * n,
                "volume": vol,
            }
        )
        result = detect_anomalies(df, symbol="TEST")
        vol_anomalies = [
            a
            for a in result.anomalies
            if "volume" in a.message.lower() or "zero" in a.message.lower()
        ]
        assert len(vol_anomalies) > 0

    def test_anomalies_have_severity_levels(self):
        from trade_advisor.data.validation import AnomalySeverity, detect_anomalies

        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=5, tz="UTC"),
                "open": [100.0] * 5,
                "high": [101.0] * 5,
                "low": [99.0] * 5,
                "close": [100.5] * 5,
                "volume": [0] * 5,
            }
        )
        result = detect_anomalies(df, symbol="TEST")
        for a in result.anomalies:
            assert a.severity in (AnomalySeverity.WARNING, AnomalySeverity.ERROR)

    def test_bar_validity_high_ge_max_open_close(self):
        from trade_advisor.data.schemas import Bar

        with pytest.raises(ValidationError, match="high.*must be >= max"):
            Bar(
                symbol="TEST",
                timestamp=pd.Timestamp("2024-01-01", tz="UTC"),
                resolution=pd.Timedelta("1d"),
                open=100.0,
                high=99.0,
                low=98.0,
                close=100.5,
                volume=1e6,
            )

    def test_bar_validity_low_le_min_open_close(self):
        from trade_advisor.data.schemas import Bar

        with pytest.raises(ValidationError, match="low.*must be <= min"):
            Bar(
                symbol="TEST",
                timestamp=pd.Timestamp("2024-01-01", tz="UTC"),
                resolution=pd.Timedelta("1d"),
                open=100.0,
                high=103.0,
                low=100.5,
                close=99.0,
                volume=1e6,
            )

    def test_invalid_bars_flagged_not_dropped(self):
        from trade_advisor.data.validation import detect_anomalies

        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=5, tz="UTC"),
                "open": [100.0] * 5,
                "high": [99.0] * 5,
                "low": [101.0] * 5,
                "close": [100.5] * 5,
                "volume": [1e6] * 5,
            }
        )
        original = df.copy()
        result = detect_anomalies(df, symbol="TEST")
        assert len(result.anomalies) > 0
        pd.testing.assert_frame_equal(df, original)

    @pytest.mark.skip(reason="Requires DuckDB with pre-inserted data — integration test")
    def test_data_freshness_tracked_per_symbol_interval(self):
        from trade_advisor.data.validation import get_data_freshness

        freshness = get_data_freshness("SPY", "1d")
        assert hasattr(freshness, "last_updated")
        assert hasattr(freshness, "symbol")
        assert hasattr(freshness, "interval")

    def test_sse_event_models_pydantic_typed(self):
        from trade_advisor.web.sse import ErrorEvent, ProgressEvent, SSEEvent

        assert issubclass(ProgressEvent, SSEEvent)
        assert issubclass(ErrorEvent, SSEEvent)
        evt = ProgressEvent(
            event_type="progress",
            run_id="test",
            timestamp="2024-01-01T00:00:00Z",
            current=1,
            total=10,
            message="Running",
        )
        assert evt.event_type == "progress"

    def test_frontend_events_typed_map(self):
        from trade_advisor.web.events import TAEventMap

        event_map = TAEventMap()
        assert "ta:strategy:forked" in event_map.events or len(event_map.events) > 0
