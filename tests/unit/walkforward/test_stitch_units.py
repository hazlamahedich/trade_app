import pandas as pd
import pytest
from trade_advisor.backtest.walkforward.stitch import (
    stitch_oos_equity,
    wfe_status,
    WFEThresholds,
    compute_ev_significance,
)

def test_stitch_oos_equity_compounding():
    idx1 = pd.date_range("2023-01-01", periods=2)
    s1 = pd.Series([110.0, 121.0], index=idx1)
    idx2 = pd.date_range("2023-01-03", periods=2)
    s2 = pd.Series([105.0, 115.5], index=idx2)
    stitched = stitch_oos_equity([s1, s2], initial_cash=100.0)
    assert stitched.iloc[-1] == pytest.approx(139.755)
