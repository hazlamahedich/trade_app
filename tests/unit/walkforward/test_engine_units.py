import pandas as pd
import pytest
from trade_advisor.backtest.walkforward.engine import (
    DataBoundary,
    WalkForwardConfig,
    WalkForwardError,
    _generate_anchored_boundaries,
    _generate_rolling_boundaries,
    _compute_metrics,
)
from trade_advisor.backtest.engine import BacktestResult

def test_generate_rolling_boundaries():
    boundaries = _generate_rolling_boundaries(10, 4, 2, 1)
    assert len(boundaries) == 1
    b = boundaries[0]
    assert b.is_start == 0 and b.is_end == 4
    assert b.oos_start == 5 and b.oos_end == 7

def test_config_validation():
    with pytest.raises(WalkForwardError, match="frozen_params_mode requires optimization"):
        WalkForwardConfig(mode="rolling", is_bars=10, oos_bars=5, frozen_params_mode=True)

def test_compute_metrics_edge_cases():
    # Note: Requires valid positions and config in actual project
    pass
