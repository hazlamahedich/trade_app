from __future__ import annotations

from datetime import datetime


def test_data_provider_protocol_exists():
    from trade_advisor.data.providers.base import DataProvider

    assert hasattr(DataProvider, "fetch")
    assert hasattr(DataProvider, "validate")
    assert hasattr(DataProvider, "check_connectivity")
    assert hasattr(DataProvider, "name")
    assert hasattr(DataProvider, "supported_intervals")


def test_connectivity_status_model():
    from trade_advisor.data.providers.base import ConnectivityStatus

    now = datetime(2024, 1, 1)
    status = ConnectivityStatus(connected=True, provider_name="test", checked_at=now)
    assert status.connected is True
    assert status.provider_name == "test"
    assert status.error_message is None

    status2 = ConnectivityStatus(
        connected=False,
        provider_name="test",
        checked_at=now,
        error_message="timeout",
    )
    assert status2.connected is False
    assert status2.error_message == "timeout"


def test_freshness_status_model():
    from trade_advisor.data.storage import FreshnessStatus

    fs = FreshnessStatus(
        symbol="SPY",
        interval="1d",
        last_updated=None,
        bar_count=0,
        is_stale=True,
        staleness_threshold_hours=1,
    )
    assert fs.symbol == "SPY"
    assert fs.is_stale is True
    assert fs.bar_count == 0
