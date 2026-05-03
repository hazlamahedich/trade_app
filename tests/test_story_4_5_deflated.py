import numpy as np
import pytest
from trade_advisor.backtest.walkforward.deflated import (
    compute_dsr,
    compute_expected_max_sr,
    compute_trial_stats_online,
)

def test_dsr_math_oracles():
    # Observed SR (daily), N=1, SR_variance=0.01, returns (normal)
    # With N=1, SR_0 should be 0
    returns = np.random.normal(0, 1, 1000)
    observed_sr = 0.05  # daily
    n_trials = 1
    sr_variance = 0.01
    
    dsr = compute_dsr(observed_sr, n_trials, sr_variance, returns)
    assert 0.0 < dsr < 1.0
    
    # With many trials, DSR should decrease
    dsr_many = compute_dsr(observed_sr, 100, sr_variance, returns)
    assert dsr_many < dsr

def test_expected_max_sr():
    # N=1 => SR_0=0
    assert compute_expected_max_sr(1, 0.1) == 0.0
    
    # N=100, var=0.1
    sr0 = compute_expected_max_sr(100, 0.1)
    assert sr0 > 0
    
    # Increasing N increases SR_0
    assert compute_expected_max_sr(1000, 0.1) > sr0

def test_trial_stats_online():
    metrics = [1.0, 2.0, 3.0, 4.0, 5.0]
    stats = compute_trial_stats_online(5, metrics)
    assert stats.n_trials == 5
    assert stats.mean == 3.0
    assert stats.variance == pytest.approx(statistics_variance(metrics))

def statistics_variance(data):
    n = len(data)
    if n < 2: return 0.0
    mean = sum(data) / n
    return sum((x - mean) ** 2 for x in data) / (n - 1)

def test_degenerate_distribution():
    # Zero variance returns
    returns = [0.01] * 1000
    dsr = compute_dsr(0.5, 10, 0.1, returns)
    assert dsr == 0.0

def test_invalid_inputs():
    with pytest.raises(ValueError):
        compute_dsr(0.5, 0, 0.1, [0.1]*100)
    
    with pytest.raises(ValueError):
        compute_trial_stats_online(0, [])

def test_minimum_sample_size_stability():
    # AC-1: Minimum sample size 250 mentioned in story.
    # While we don't hard-fail, we should verify it handles small T gracefully.
    returns = np.random.normal(0, 1, 10)
    dsr = compute_dsr(0.1, 1, 0.01, returns)
    assert 0.0 <= dsr <= 1.0
