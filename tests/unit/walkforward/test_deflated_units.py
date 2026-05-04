import pytest
from trade_advisor.backtest.walkforward.deflated import TrialStats

def test_trial_stats_merge():
    ts1 = TrialStats()
    for x in [1.0, 2.0]: ts1.update(x)
    ts2 = TrialStats()
    for x in [3.0, 4.0, 5.0]: ts2.update(x)
    ts1.merge(ts2)
    assert ts1.n_trials == 5
    assert ts1.mean == 3.0
    assert ts1.variance == pytest.approx(2.5)
