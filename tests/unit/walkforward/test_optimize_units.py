import pytest
from trade_advisor.backtest.walkforward.optimize import (
    monotonic_increasing,
    min_spacing,
    _enumerate_candidates,
    _median_prune,
    TrialResult,
)

def test_constraints():
    c1 = monotonic_increasing("fast", "slow")
    assert c1({"fast": 10, "slow": 20}) is True
    assert c1({"fast": 20, "slow": 20}) is False

def test_median_prune():
    results = [
        TrialResult(params={}, metric=float(i), status="evaluated") for i in range(1, 6)
    ]
    n = _median_prune(results, maximize=True, min_trials=5)
    assert n == 2
