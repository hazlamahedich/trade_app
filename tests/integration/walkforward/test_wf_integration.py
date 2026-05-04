import numpy as np
import pandas as pd
import pytest
from trade_advisor.backtest.walkforward.engine import walk_forward, WalkForwardConfig
from trade_advisor.backtest.walkforward.optimize import OptimizationConfig
from trade_advisor.backtest.walkforward.stitch import build_stitched_result

@pytest.fixture
def ohlcv_data():
    np.random.seed(42)
    idx = pd.date_range("2023-01-01", periods=200, freq="D")
    data = pd.DataFrame({
        "open": np.random.normal(100, 1, 200),
        "high": np.random.normal(101, 1, 200),
        "low": np.random.normal(99, 1, 200),
        "close": np.random.normal(100, 1, 200),
        "volume": np.random.normal(1000, 100, 200),
    }, index=idx)
    return data

def test_full_wf_cycle_with_optimization(ohlcv_data):
    config = WalkForwardConfig(
        mode="rolling",
        is_bars=40,
        oos_bars=10,
        gap_bars=1,
        strategy_type="sma",
        strategy_params={"fast": 10, "slow": 20},
        optimization=OptimizationConfig(
            param_ranges={"fast": [5, 10], "slow": [20, 30]},
            max_trials=10,
            metric="sharpe"
        )
    )
    
    # 1. Run Engine
    result = walk_forward(ohlcv_data, config)
    assert result.n_windows > 0
    assert result.total_trials > 0
    
    # 2. Build Stitched Result
    stitched = build_stitched_result(result, ohlcv_data)
    assert len(stitched.stitched_equity) > 0
    assert stitched.wfe_status in ["healthy", "caution", "unreliable"]
    assert stitched.diagnostics is not None

def test_frozen_params_mode_integration(ohlcv_data):
    config = WalkForwardConfig(
        mode="rolling",
        is_bars=40,
        oos_bars=10,
        gap_bars=1,
        strategy_type="sma",
        strategy_params={"fast": 10, "slow": 20},
        optimization=OptimizationConfig(
            param_ranges={"fast": [5, 10], "slow": [20, 30]},
            max_trials=4,
            metric="sharpe"
        ),
        frozen_params_mode=True
    )
    
    result = walk_forward(ohlcv_data, config)
    # Check that windows (except the first possibly) use prior best params
    for i, w in enumerate(result.windows):
        if i > 0:
            assert w.frozen_oos_params is not None
            # The source window should be the one before it
            assert w.frozen_params_source_window == i - 1
