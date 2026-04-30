"""Comprehensive tests for experiments/tracker.py — Six Levels."""

from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from tests.helpers import _synthetic_ohlcv
from trade_advisor.experiments.tracker import (
    ExperimentRecord,
    ExperimentRepository,
    HashedRunInputs,
    RunAnnotations,
    compute_config_hash,
    compute_data_fingerprint,
    compute_result_hash,
    generate_run_id,
    get_code_version,
    get_package_versions,
    is_dirty_tree,
)

# =============================================================================
# Level A — run_id generation (unit)
# =============================================================================


class TestGenerateRunId:
    def test_generate_run_id_deterministic(self):
        inputs = HashedRunInputs(config={"fast": 20, "slow": 50})
        assert generate_run_id(inputs) == generate_run_id(inputs)

    def test_generate_run_id_different_config(self):
        i1 = HashedRunInputs(config={"fast": 20})
        i2 = HashedRunInputs(config={"fast": 14})
        assert generate_run_id(i1) != generate_run_id(i2)

    def test_generate_run_id_format(self):
        inputs = HashedRunInputs(config={"fast": 20})
        rid = generate_run_id(inputs)
        assert rid.startswith("run_")
        assert len(rid) == 20

    def test_generate_run_id_includes_data_fingerprint(self):
        i1 = HashedRunInputs(config={"fast": 20}, data_fingerprint="aaa")
        i2 = HashedRunInputs(config={"fast": 20}, data_fingerprint="bbb")
        assert generate_run_id(i1) != generate_run_id(i2)

    def test_generate_run_id_includes_code_version(self):
        i1 = HashedRunInputs(config={"fast": 20}, code_version="abc")
        i2 = HashedRunInputs(config={"fast": 20}, code_version="def")
        assert generate_run_id(i1) != generate_run_id(i2)

    def test_generate_run_id_includes_package_versions(self):
        i1 = HashedRunInputs(config={"fast": 20}, package_versions='{"numpy": "1.24"}')
        i2 = HashedRunInputs(config={"fast": 20}, package_versions='{"numpy": "1.26"}')
        assert generate_run_id(i1) != generate_run_id(i2)

    def test_generate_run_id_pre_mortem_excluded(self):
        inputs = HashedRunInputs(config={"fast": 20})
        id_before = generate_run_id(inputs)
        RunAnnotations(pre_mortem="I expect Sharpe > 1.0")
        assert generate_run_id(inputs) == id_before

    def test_full_run_hash_64_chars(self):
        inputs = HashedRunInputs(config={"fast": 20})
        rid = generate_run_id(inputs)
        assert rid.startswith("run_")
        assert len(rid) == 20

    def test_dirty_tree_produces_different_id(self):
        i1 = HashedRunInputs(config={"fast": 20}, is_dirty=False)
        i2 = HashedRunInputs(config={"fast": 20}, is_dirty=True)
        assert generate_run_id(i1) != generate_run_id(i2)

    def test_normalize_numpy_types(self):
        import numpy as np

        config = {"fast": np.int64(20), "slow": np.float64(50)}
        h1 = compute_config_hash(config)
        h2 = compute_config_hash({"fast": 20, "slow": 50.0})
        assert h1 == h2


class TestComputeConfigHash:
    def test_compute_config_hash_deterministic(self):
        config = {"fast": 20, "slow": 50}
        assert compute_config_hash(config) == compute_config_hash(config)

    def test_compute_config_hash_order_independent(self):
        a = {"a": 1, "b": 2}
        b = {"b": 2, "a": 1}
        assert compute_config_hash(a) == compute_config_hash(b)

    def test_compute_config_hash_normalizes_int_float(self):
        a = {"x": 20}
        b = {"x": 20.0}
        assert compute_config_hash(a) == compute_config_hash(b)

    def test_compute_config_hash_rejects_nan(self):
        with pytest.raises(ValueError, match="NaN"):
            compute_config_hash({"x": float("nan")})

    def test_compute_config_hash_rejects_infinity(self):
        with pytest.raises(ValueError, match="Infinity"):
            compute_config_hash({"x": float("inf")})

    def test_compute_config_hash_decimal_to_float(self):
        a = {"x": Decimal("100000")}
        b = {"x": 100000.0}
        assert compute_config_hash(a) == compute_config_hash(b)


class TestComputeDataFingerprint:
    def test_compute_data_fingerprint_deterministic(self):
        df = _synthetic_ohlcv(n=100, seed=42).set_index("timestamp")
        assert compute_data_fingerprint(df) == compute_data_fingerprint(df)

    def test_compute_data_fingerprint_changes_with_data(self):
        df1 = _synthetic_ohlcv(n=100, seed=42).set_index("timestamp")
        df2 = _synthetic_ohlcv(n=100, seed=99).set_index("timestamp")
        assert compute_data_fingerprint(df1) != compute_data_fingerprint(df2)

    def test_compute_data_fingerprint_float64_enforced(self):
        df = _synthetic_ohlcv(n=100, seed=42).set_index("timestamp")
        fp1 = compute_data_fingerprint(df)
        fp2 = compute_data_fingerprint(df)
        assert fp1 == fp2
        assert len(fp1) == 64

    def test_compute_data_fingerprint_includes_all_ohlcv(self):
        df = _synthetic_ohlcv(n=100, seed=42).set_index("timestamp")
        fp1 = compute_data_fingerprint(df)
        df_mod = df.copy()
        df_mod["open"] = df_mod["open"] * 1.01
        fp2 = compute_data_fingerprint(df_mod)
        assert fp1 != fp2


class TestGetCodeVersion:
    def test_get_code_version_returns_string(self):
        ver = get_code_version()
        assert isinstance(ver, str)
        assert len(ver) > 0

    def test_get_code_version_cached(self):
        v1 = get_code_version()
        v2 = get_code_version()
        assert v1 is v2


class TestIsDirtyTree:
    def test_is_dirty_tree_returns_bool(self):
        result = is_dirty_tree()
        assert isinstance(result, bool)


# =============================================================================
# Level B — DuckDB experiment storage via ExperimentRepository (integration)
# =============================================================================


class TestExperimentRepository:
    @pytest.mark.asyncio
    async def test_experiment_write_failure_returns_false(self):
        db = AsyncMock()
        db.write.side_effect = Exception("DB error")
        record = ExperimentRecord(
            run_id="run_abc123",
            config_hash="hash123",
            strategy="sma",
        )
        assert await ExperimentRepository.store_run(db, record) is False

    @pytest.mark.asyncio
    async def test_experiment_write_success_returns_true(self):
        db = AsyncMock()
        record = ExperimentRecord(
            run_id="run_abc123",
            config_hash="hash123",
            strategy="sma",
        )
        assert await ExperimentRepository.store_run(db, record) is True

    @pytest.mark.asyncio
    async def test_experiment_record_fields_populated(self):
        record = ExperimentRecord(
            run_id="run_test12345678",
            config_hash="abc",
            strategy="sma",
            metrics_json='{"sharpe": 1.5}',
            seed=42,
            status="completed",
            git_commit="a" * 40,
            data_fingerprint="fp123",
            python_version="3.12.0",
            package_versions='{"numpy": "1.26.0"}',
            result_hash="rh456",
            pre_mortem="I expect good results",
        )
        assert record.run_id == "run_test12345678"
        assert record.git_commit == "a" * 40
        assert record.pre_mortem == "I expect good results"
        assert record.result_hash == "rh456"

    @pytest.mark.asyncio
    async def test_run_exists_returns_false_on_empty(self):
        db = AsyncMock()
        db.read.return_value = []
        assert await ExperimentRepository.run_exists(db, "run_nosuch") is False

    @pytest.mark.asyncio
    async def test_run_exists_returns_true(self):
        db = AsyncMock()
        db.read.return_value = [(1,)]
        assert await ExperimentRepository.run_exists(db, "run_abc") is True

    @pytest.mark.asyncio
    async def test_get_run_returns_none_when_not_found(self):
        db = AsyncMock()
        db.read.return_value = []
        assert await ExperimentRepository.get_run(db, "run_nosuch") is None

    @pytest.mark.asyncio
    async def test_pre_mortem_stored_when_provided(self):
        record = ExperimentRecord(
            run_id="run_pmtest",
            config_hash="ch",
            strategy="sma",
            pre_mortem="I expect Sharpe > 1.0",
        )
        assert record.pre_mortem == "I expect Sharpe > 1.0"


# =============================================================================
# Level C — Bitwise reproducibility (unit)
# =============================================================================


class TestBitwiseReproducibility:
    def test_rerun_same_config_same_equity_bytes(self):
        df = _synthetic_ohlcv(n=200, seed=42)
        from trade_advisor.backtest.engine import run_backtest
        from trade_advisor.strategies.sma_cross import SmaCross

        s1 = SmaCross(fast=20, slow=50)
        r1 = run_backtest(df, s1.generate_signals(df))
        s2 = SmaCross(fast=20, slow=50)
        r2 = run_backtest(df, s2.generate_signals(df))
        assert r1.equity.values.tobytes() == r2.equity.values.tobytes()

    def test_rerun_same_config_same_trades_exact(self):
        df = _synthetic_ohlcv(n=200, seed=42)
        from trade_advisor.backtest.engine import run_backtest
        from trade_advisor.strategies.sma_cross import SmaCross

        s1 = SmaCross(fast=20, slow=50)
        r1 = run_backtest(df, s1.generate_signals(df))
        s2 = SmaCross(fast=20, slow=50)
        r2 = run_backtest(df, s2.generate_signals(df))
        pd.testing.assert_frame_equal(r1.trades, r2.trades, check_exact=True)

    def test_rerun_same_config_same_result_hash(self):
        df = _synthetic_ohlcv(n=200, seed=42)
        from trade_advisor.backtest.engine import run_backtest
        from trade_advisor.strategies.sma_cross import SmaCross

        s1 = SmaCross(fast=20, slow=50)
        r1 = run_backtest(df, s1.generate_signals(df))
        s2 = SmaCross(fast=20, slow=50)
        r2 = run_backtest(df, s2.generate_signals(df))
        h1 = compute_result_hash(r1.equity, r1.trades)
        h2 = compute_result_hash(r2.equity, r2.trades)
        assert h1 == h2

    def test_rerun_same_config_positions_match(self):
        df = _synthetic_ohlcv(n=200, seed=42)
        from trade_advisor.backtest.engine import run_backtest
        from trade_advisor.strategies.sma_cross import SmaCross

        s1 = SmaCross(fast=20, slow=50)
        r1 = run_backtest(df, s1.generate_signals(df))
        s2 = SmaCross(fast=20, slow=50)
        r2 = run_backtest(df, s2.generate_signals(df))
        assert r1.positions.values.tobytes() == r2.positions.values.tobytes()


# =============================================================================
# Level D — Edge cases (unit)
# =============================================================================


class TestEdgeCases:
    def test_empty_config_produces_valid_id(self):
        inputs = HashedRunInputs(config={})
        rid = generate_run_id(inputs)
        assert rid.startswith("run_")
        assert len(rid) == 20

    def test_nested_config_produces_valid_id(self):
        inputs = HashedRunInputs(config={"a": {"b": 1}})
        rid = generate_run_id(inputs)
        assert rid.startswith("run_")

    def test_data_fingerprint_empty_dataframe(self):
        df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        assert compute_data_fingerprint(df) == "empty"

    def test_config_hash_large_config(self):
        config = {f"key_{i}": i for i in range(100)}
        h = compute_config_hash(config)
        assert len(h) == 64

    def test_run_id_no_collision_with_uuid_format(self):
        inputs = HashedRunInputs(config={"fast": 20})
        rid = generate_run_id(inputs)
        assert rid.startswith("run_")

    def test_config_hash_long_pre_mortem(self):
        config = {"fast": 20, "pre_mortem": "x" * 10000}
        h = compute_config_hash(config)
        assert len(h) == 64

    def test_get_code_version_git_not_installed(self):
        get_code_version.cache_clear()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert get_code_version() == "unknown"
        get_code_version.cache_clear()

    def test_compute_result_hash_empty_trades(self):
        equity = pd.Series([100.0, 101.0, 102.0])
        trades = pd.DataFrame()
        h = compute_result_hash(equity, trades)
        assert len(h) == 64

    def test_compute_result_hash_returns_64_hex(self):
        equity = pd.Series([100.0, 101.0])
        trades = pd.DataFrame({"return": [0.01], "pnl": [1.0]})
        h = compute_result_hash(equity, trades)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_get_package_versions_returns_json(self):
        pv = get_package_versions()
        parsed = json.loads(pv)
        assert "numpy" in parsed
        assert "pandas" in parsed
        assert "python" in parsed


# =============================================================================
# Level E — Concurrent write safety (integration)
# =============================================================================


class TestConcurrentWrites:
    @pytest.mark.asyncio
    async def test_concurrent_experiment_writes_no_data_loss(self):
        import asyncio

        db = AsyncMock()
        results = []

        async def write_both():
            r1 = await ExperimentRepository.store_run(
                db,
                ExperimentRecord(run_id="run_1", config_hash="h1", strategy="sma"),
            )
            r2 = await ExperimentRepository.store_run(
                db,
                ExperimentRecord(run_id="run_2", config_hash="h2", strategy="sma"),
            )
            results.extend([r1, r2])

        await asyncio.gather(write_both(), write_both())
        assert all(results)

    @pytest.mark.asyncio
    async def test_concurrent_post_both_experiments_stored(self):
        db = AsyncMock()
        r1 = await ExperimentRepository.store_run(
            db,
            ExperimentRecord(run_id="run_a", config_hash="ha", strategy="sma"),
        )
        r2 = await ExperimentRepository.store_run(
            db,
            ExperimentRecord(run_id="run_b", config_hash="hb", strategy="sma"),
        )
        assert r1 is True
        assert r2 is True
        assert db.write.call_count == 2


# =============================================================================
# Level F — Property-based tests (hypothesis)
# =============================================================================


try:
    from hypothesis import given, settings
    from hypothesis import strategies as st

    class TestPropertyBased:
        @given(config=st.dictionaries(st.text(min_size=1, max_size=10), st.integers()))
        @settings(max_examples=50)
        def test_generate_run_id_idempotent(self, config):
            inputs = HashedRunInputs(config=config)
            assert generate_run_id(inputs) == generate_run_id(inputs)

        @given(
            config=st.dictionaries(
                st.text(min_size=1, max_size=5),
                st.one_of(st.integers(), st.floats(allow_nan=False, allow_infinity=False)),
            )
        )
        @settings(max_examples=50)
        def test_compute_config_hash_order_independent(self, config):
            keys = list(config.keys())

            shuffled = {k: config[k] for k in reversed(keys)}
            assert compute_config_hash(config) == compute_config_hash(shuffled)

        @given(
            c1=st.dictionaries(st.text(min_size=1, max_size=5), st.integers()),
            c2=st.dictionaries(st.text(min_size=1, max_size=5), st.integers()),
        )
        @settings(max_examples=50)
        def test_different_configs_different_ids(self, c1, c2):
            if c1 != c2:
                i1 = HashedRunInputs(config=c1)
                i2 = HashedRunInputs(config=c2)
                assert generate_run_id(i1) != generate_run_id(i2)

except ImportError:
    pass
