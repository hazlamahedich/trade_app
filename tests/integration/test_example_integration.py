"""Sample integration test demonstrating network-dependent patterns."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


class TestDataFetch:
    """Given a real symbol, When data is fetched, Then OHLCV is returned."""

    def test_fetch_spy(self, real_symbol, real_start_date):
        from trade_advisor.data.cache import get_ohlcv

        df = get_ohlcv(real_symbol, start=real_start_date)
        assert not df.empty
        assert "close" in df.columns
        assert len(df) > 0
