"""Unit tests for trade_advisor.experiments.compare."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio

from trade_advisor.core.config import DatabaseConfig
from trade_advisor.experiments.compare import (
    _check_compatibility,
    _compute_metrics_diff,
    _compute_parameter_diff_list,
    _detect_missing_sections,
    _determine_order,
    _parse_json,
    _safe_float,
    compare_runs,
    compare_trades,
)
from trade_advisor.experiments.tracker import ExperimentRecord, ExperimentRepository
from trade_advisor.infra.db import DatabaseManager


def _now():
    return datetime.now(UTC)


def _rec(run_id, strategy="SmaCross", sharpe=1.0, total_return=0.1, max_dd=-0.1, days_ago=0):
    now = _now()
    return ExperimentRecord(
        run_id=run_id,
        config_hash=f"h_{run_id}",
        strategy=strategy,
        metrics_json=json.dumps(
            {"sharpe": sharpe, "total_return": total_return, "max_drawdown": max_dd}
        ),
        seed=42,
        status="completed",
        created_at=now - timedelta(days=days_ago),
        completed_at=now - timedelta(days=days_ago),
    )


@pytest_asyncio.fixture
async def db_two_runs():
    config = DatabaseConfig(path=":memory:")
    db = DatabaseManager(config)
    async with db:
        await ExperimentRepository.store_run(
            db, _rec("run_a", sharpe=1.0, total_return=0.1, max_dd=-0.1, days_ago=1)
        )
        await ExperimentRepository.store_run(
            db, _rec("run_b", sharpe=1.5, total_return=0.25, max_dd=-0.05, days_ago=0)
        )
        await db.write(
            "UPDATE experiments SET config_json = ? WHERE run_id = ?",
            (
                json.dumps({"strategy_type": "sma", "symbol": "SPY", "fast": 10, "slow": 50}),
                "run_a",
            ),
        )
        await db.write(
            "UPDATE experiments SET config_json = ? WHERE run_id = ?",
            (
                json.dumps({"strategy_type": "sma", "symbol": "SPY", "fast": 20, "slow": 50}),
                "run_b",
            ),
        )
        yield db


@pytest_asyncio.fixture
async def db_identical_runs():
    config = DatabaseConfig(path=":memory:")
    db = DatabaseManager(config)
    async with db:
        await ExperimentRepository.store_run(
            db, _rec("run_self", sharpe=1.0, total_return=0.1, days_ago=0)
        )
        await db.write(
            "UPDATE experiments SET config_json = ? WHERE run_id = ?",
            (json.dumps({"strategy_type": "sma", "fast": 20}), "run_self"),
        )
        yield db


@pytest_asyncio.fixture
async def db_incomplete_run():
    config = DatabaseConfig(path=":memory:")
    db = DatabaseManager(config)
    async with db:
        await ExperimentRepository.store_run(db, _rec("run_full", sharpe=1.0, days_ago=1))
        rec_empty = ExperimentRecord(
            run_id="run_empty",
            config_hash="he",
            strategy="SmaCross",
            metrics_json=None,
            seed=42,
            status="completed",
            created_at=_now(),
            completed_at=_now(),
        )
        await ExperimentRepository.store_run(db, rec_empty)
        await db.write(
            "UPDATE experiments SET config_json = ? WHERE run_id = ?",
            (json.dumps({"symbol": "SPY"}), "run_full"),
        )
        yield db


@pytest_asyncio.fixture
async def db_cross_strategy():
    config = DatabaseConfig(path=":memory:")
    db = DatabaseManager(config)
    async with db:
        await ExperimentRepository.store_run(
            db, _rec("run_sma", strategy="SmaCross", sharpe=1.0, days_ago=1)
        )
        await ExperimentRepository.store_run(
            db, _rec("run_mr", strategy="MeanRevert", sharpe=0.5, days_ago=0)
        )
        await db.write(
            "UPDATE experiments SET config_json = ? WHERE run_id = ?",
            (json.dumps({"symbol": "SPY", "interval": "1d"}), "run_sma"),
        )
        await db.write(
            "UPDATE experiments SET config_json = ? WHERE run_id = ?",
            (json.dumps({"symbol": "QQQ", "interval": "1h"}), "run_mr"),
        )
        yield db


# ── Level A: compare_runs unit tests ──────────────────────────────────────


class TestCompareRuns:
    def test_two_runs_differing_metrics(self, db_two_runs):
        diff = compare_runs(db_two_runs, "run_a", "run_b")
        assert diff.baseline_id == "run_a"
        assert diff.challenger_id == "run_b"
        assert "sharpe" in diff.metrics_diff
        assert diff.metrics_diff["sharpe"].direction == "improvement"

    def test_identical_metrics_self_comparison(self, db_identical_runs):
        diff = compare_runs(db_identical_runs, "run_self", "run_self")
        for change in diff.metrics_diff.values():
            assert change.delta is not None
            assert abs(change.delta) < 1e-10
        assert diff.parameter_diff == []

    def test_missing_metrics_json(self, db_incomplete_run):
        diff = compare_runs(db_incomplete_run, "run_full", "run_empty")
        assert "metrics" in diff.missing_sections

    def test_missing_config_json(self, db_incomplete_run):
        diff = compare_runs(db_incomplete_run, "run_full", "run_empty")
        assert "config" in diff.missing_sections

    def test_same_strategy_no_warning(self, db_two_runs):
        diff = compare_runs(db_two_runs, "run_a", "run_b")
        assert diff.compatibility_warning is None

    def test_different_strategies_warning(self, db_cross_strategy):
        diff = compare_runs(db_cross_strategy, "run_sma", "run_mr")
        assert diff.compatibility_warning is not None
        assert "incompatible" in diff.compatibility_warning.lower()

    def test_nonexistent_run_raises(self, db_two_runs):
        with pytest.raises(ValueError, match="Run not found"):
            compare_runs(db_two_runs, "run_a", "nonexistent")

    def test_incomplete_run_missing_sections(self, db_incomplete_run):
        diff = compare_runs(db_incomplete_run, "run_full", "run_empty")
        assert len(diff.missing_sections) > 0

    def test_self_comparison_no_warning(self, db_identical_runs):
        diff = compare_runs(db_identical_runs, "run_self", "run_self")
        assert diff.compatibility_warning is None

    def test_baseline_challenger_ordering(self, db_two_runs):
        diff = compare_runs(db_two_runs, "run_b", "run_a")
        assert diff.baseline_id == "run_a"
        assert diff.challenger_id == "run_b"


# ── Level B: _compute_metrics_diff tests ──────────────────────────────────


class TestComputeMetricsDiff:
    def test_improvement_direction(self):
        diff = _compute_metrics_diff({"sharpe": 1.0}, {"sharpe": 1.5})
        assert diff["sharpe"].direction == "improvement"
        assert diff["sharpe"].delta == 0.5

    def test_degradation_direction(self):
        diff = _compute_metrics_diff({"sharpe": 1.5}, {"sharpe": 1.0})
        assert diff["sharpe"].direction == "degradation"
        assert diff["sharpe"].delta == -0.5

    def test_neutral_same_value(self):
        diff = _compute_metrics_diff({"sharpe": 1.0}, {"sharpe": 1.0})
        assert diff["sharpe"].direction == "neutral"

    def test_max_drawdown_less_negative_is_improvement(self):
        diff = _compute_metrics_diff({"max_drawdown": -0.2}, {"max_drawdown": -0.05})
        assert diff["max_drawdown"].delta == pytest.approx(0.15)
        assert diff["max_drawdown"].direction == "improvement"

    def test_max_drawdown_more_negative_is_degradation(self):
        diff = _compute_metrics_diff({"max_drawdown": -0.05}, {"max_drawdown": -0.2})
        assert diff["max_drawdown"].delta == pytest.approx(-0.15)
        assert diff["max_drawdown"].direction == "degradation"

    def test_max_drawdown_positive_values_correct_direction(self):
        diff = _compute_metrics_diff({"max_drawdown": 0.05}, {"max_drawdown": 0.15})
        assert diff["max_drawdown"].direction == "improvement"

    def test_max_drawdown_positive_to_lower(self):
        diff = _compute_metrics_diff({"max_drawdown": 0.15}, {"max_drawdown": 0.05})
        assert diff["max_drawdown"].direction == "degradation"

    def test_var_95_lower_is_improvement(self):
        diff = _compute_metrics_diff({"var_95": 0.03}, {"var_95": 0.01})
        assert diff["var_95"].direction == "improvement"

    def test_var_95_higher_is_degradation(self):
        diff = _compute_metrics_diff({"var_95": 0.01}, {"var_95": 0.03})
        assert diff["var_95"].direction == "degradation"

    def test_none_values_neutral(self):
        diff = _compute_metrics_diff({"sharpe": None}, {"sharpe": 1.0})
        assert diff["sharpe"].direction == "neutral"
        assert diff["sharpe"].delta is None

    def test_nan_values_neutral(self):
        diff = _compute_metrics_diff({"sharpe": float("nan")}, {"sharpe": 1.0})
        assert diff["sharpe"].direction == "neutral"

    def test_inf_values_neutral(self):
        diff = _compute_metrics_diff({"sharpe": float("inf")}, {"sharpe": 1.0})
        assert diff["sharpe"].direction == "neutral"

    def test_unknown_metric_default_higher_better(self, caplog):
        with caplog.at_level(logging.WARNING):
            diff = _compute_metrics_diff({"custom_metric": 1.0}, {"custom_metric": 2.0})
        assert diff["custom_metric"].direction == "improvement"
        assert "Unknown metric" in caplog.text

    def test_float_precision_edge_case(self):
        diff = _compute_metrics_diff({"sharpe": 1.0}, {"sharpe": 1.0 + 1e-11})
        assert diff["sharpe"].direction == "neutral"


# ── Level C: _compute_parameter_diff_list tests ───────────────────────────


class TestComputeParameterDiffList:
    def test_changed_params(self):
        diff = _compute_parameter_diff_list({"fast": 10, "slow": 50}, {"fast": 20, "slow": 50})
        assert len(diff) == 1
        assert diff[0].field == "fast"
        assert diff[0].old_value == 10
        assert diff[0].new_value == 20

    def test_no_changes_empty_list(self):
        diff = _compute_parameter_diff_list({"fast": 10, "slow": 50}, {"fast": 10, "slow": 50})
        assert diff == []

    def test_config_none_empty_dict(self):
        diff = _compute_parameter_diff_list(None, {"fast": 10})
        assert diff == []

    def test_asymmetric_configs_no_shared_key_diff(self):
        diff = _compute_parameter_diff_list(
            {"fast": 10, "unique_a": 1}, {"fast": 20, "unique_b": 2}
        )
        fields = [d.field for d in diff]
        assert "fast" in fields
        assert "unique_a" not in fields
        assert "unique_b" not in fields


# ── Level D: _check_compatibility tests ───────────────────────────────────


class TestCheckCompatibility:
    def test_same_strategy_returns_none(self):
        result = _check_compatibility(
            {"strategy": "SmaCross", "config_json": None},
            {"strategy": "SmaCross", "config_json": None},
        )
        assert result is None

    def test_same_strategy_with_pre_parsed_configs(self):
        result = _check_compatibility(
            {"strategy": "SmaCross"},
            {"strategy": "SmaCross"},
            config_a={"symbol": "SPY"},
            config_b={"symbol": "SPY"},
        )
        assert result is None

    def test_different_strategy_names_warning(self):
        result = _check_compatibility(
            {"strategy": "SmaCross", "config_json": None},
            {"strategy": "MeanRevert", "config_json": None},
        )
        assert result is not None
        assert "SmaCross" in result
        assert "MeanRevert" in result

    def test_same_strategy_different_symbol_warning(self):
        result = _check_compatibility(
            {"strategy": "SmaCross", "config_json": json.dumps({"symbol": "SPY"})},
            {"strategy": "SmaCross", "config_json": json.dumps({"symbol": "QQQ"})},
        )
        assert result is not None
        assert "SPY" in result
        assert "QQQ" in result

    def test_same_strategy_different_interval_warning(self):
        result = _check_compatibility(
            {"strategy": "SmaCross", "config_json": json.dumps({"interval": "1d"})},
            {"strategy": "SmaCross", "config_json": json.dumps({"interval": "1h"})},
        )
        assert result is not None
        assert "1d" in result
        assert "1h" in result

    def test_case_sensitive_strategy_names(self):
        result = _check_compatibility(
            {"strategy": "SmaCross", "config_json": None},
            {"strategy": "smacross", "config_json": None},
        )
        assert result is not None


# ── Level E: Web API tests ────────────────────────────────────────────────


@pytest_asyncio.fixture
async def api_db():
    config = DatabaseConfig(path=":memory:")
    db = DatabaseManager(config)
    async with db:
        await ExperimentRepository.store_run(
            db, _rec("api_run_a", sharpe=1.0, total_return=0.1, days_ago=1)
        )
        await ExperimentRepository.store_run(
            db, _rec("api_run_b", sharpe=1.5, total_return=0.2, days_ago=0)
        )
        await db.write(
            "UPDATE experiments SET config_json = ? WHERE run_id = ?",
            (json.dumps({"fast": 10}), "api_run_a"),
        )
        await db.write(
            "UPDATE experiments SET config_json = ? WHERE run_id = ?",
            (json.dumps({"fast": 20}), "api_run_b"),
        )
        yield db


@pytest.mark.asyncio
async def test_api_compare_200(api_db):
    from httpx import ASGITransport, AsyncClient

    from trade_advisor.main import app

    app.state.db = api_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/health")
        resp = await client.get("/api/experiments/compare?run_a=api_run_a&run_b=api_run_b")
    assert resp.status_code == 200
    data = resp.json()
    assert "metrics_diff" in data
    assert "parameter_diff" in data
    assert "baseline_id" in data
    assert "challenger_id" in data
    assert "missing_sections" in data


@pytest.mark.asyncio
async def test_api_compare_400_empty_params(api_db):
    from httpx import ASGITransport, AsyncClient

    from trade_advisor.main import app

    app.state.db = api_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/health")
        resp = await client.get("/api/experiments/compare?run_a=&run_b=")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_api_compare_404_missing_run(api_db):
    from httpx import ASGITransport, AsyncClient

    from trade_advisor.main import app

    app.state.db = api_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/health")
        resp = await client.get("/api/experiments/compare?run_a=api_run_a&run_b=nope")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_compare_html_page(api_db):
    from httpx import ASGITransport, AsyncClient

    from trade_advisor.main import app

    app.state.db = api_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/health")
        resp = await client.get("/experiments/compare?run_a=api_run_a&run_b=api_run_b")
    assert resp.status_code == 200
    html = resp.text
    assert "baseline" in html.lower()
    assert "challenger" in html.lower()


# ── Level F: compare_trades tests ─────────────────────────────────────────


@pytest_asyncio.fixture
async def db_with_positions():
    config = DatabaseConfig(path=":memory:")
    db = DatabaseManager(config)
    async with db:
        await ExperimentRepository.store_run(db, _rec("t_run_a", days_ago=1))
        await ExperimentRepository.store_run(db, _rec("t_run_b", days_ago=0))
        await db.write_many(
            "INSERT INTO result_series (run_id, source, series_type, ts, value) VALUES (?, ?, ?, ?, ?)",
            [
                ("t_run_a", "strategy", "positions", "2024-01-01", 1.0),
                ("t_run_a", "strategy", "positions", "2024-01-02", 0.0),
                ("t_run_a", "strategy", "positions", "2024-01-03", -1.0),
            ],
        )
        await db.write_many(
            "INSERT INTO result_series (run_id, source, series_type, ts, value) VALUES (?, ?, ?, ?, ?)",
            [
                ("t_run_b", "strategy", "positions", "2024-01-01", 1.0),
                ("t_run_b", "strategy", "positions", "2024-01-02", 1.0),
            ],
        )
        yield db


class TestCompareTrades:
    def test_two_runs_with_trades(self, db_with_positions):
        result = compare_trades(db_with_positions, "t_run_a", "t_run_b")
        assert result.alignment_strategy == "sequential"
        assert len(result.trades_a) == 3
        assert len(result.trades_b) == 2
        assert result.trades_a[0].price is None
        assert result.trades_a[0].quantity == 1.0

    def test_empty_trades_both_sides(self, db_two_runs):
        result = compare_trades(db_two_runs, "run_a", "run_b")
        assert result.trades_a == []
        assert result.trades_b == []

    def test_nonexistent_run_raises(self, db_two_runs):
        with pytest.raises(ValueError, match="Run not found"):
            compare_trades(db_two_runs, "run_a", "nonexistent")

    def test_alignment_strategy_sequential(self, db_with_positions):
        result = compare_trades(db_with_positions, "t_run_a", "t_run_b")
        assert result.alignment_strategy == "sequential"

    def test_different_trade_counts(self, db_with_positions):
        result = compare_trades(db_with_positions, "t_run_a", "t_run_b")
        assert len(result.trades_a) != len(result.trades_b)

    def test_single_trade_per_side(self, db_two_runs):
        import asyncio

        async def _add():
            await db_two_runs.write_many(
                "INSERT INTO result_series (run_id, source, series_type, ts, value) VALUES (?, ?, ?, ?, ?)",
                [("run_a", "strategy", "positions", "2024-01-01", 1.0)],
            )
            await db_two_runs.write_many(
                "INSERT INTO result_series (run_id, source, series_type, ts, value) VALUES (?, ?, ?, ?, ?)",
                [("run_b", "strategy", "positions", "2024-01-01", 1.0)],
            )

        asyncio.get_event_loop().run_until_complete(_add())
        result = compare_trades(db_two_runs, "run_a", "run_b")
        assert len(result.trades_a) == 1
        assert len(result.trades_b) == 1


# ── Helper function tests ─────────────────────────────────────────────────


class TestHelpers:
    def test_parse_json_none(self):
        assert _parse_json(None) == {}

    def test_parse_json_empty(self):
        assert _parse_json("") == {}

    def test_parse_json_malformed(self):
        assert _parse_json("not json") == {}

    def test_parse_json_valid(self):
        assert _parse_json('{"a": 1}') == {"a": 1}

    def test_safe_float_none(self):
        assert _safe_float(None) is None

    def test_safe_float_nan(self):
        assert _safe_float(float("nan")) is None

    def test_safe_float_inf(self):
        assert _safe_float(float("inf")) is None

    def test_safe_float_valid(self):
        assert _safe_float(3.14) == 3.14

    def test_determine_order_by_created_at(self):
        now = _now()
        a = {"run_id": "a", "created_at": now - timedelta(days=1)}
        b = {"run_id": "b", "created_at": now}
        baseline, challenger = _determine_order(a, b)
        assert baseline["run_id"] == "a"
        assert challenger["run_id"] == "b"

    def test_determine_order_fallback_lexicographic(self):
        a = {"run_id": "alpha", "created_at": None}
        b = {"run_id": "beta", "created_at": None}
        baseline, _challenger = _determine_order(a, b)
        assert baseline["run_id"] == "alpha"

    def test_detect_missing_sections_metrics(self):
        row = {"metrics_json": None, "config_json": "{}"}
        assert "metrics" in _detect_missing_sections(row)

    def test_detect_missing_sections_config(self):
        row = {"metrics_json": "{}", "config_json": None}
        assert "config" in _detect_missing_sections(row)

    def test_detect_missing_sections_none(self):
        row = {"metrics_json": '{"sharpe": 1.0}', "config_json": '{"fast": 20}'}
        assert _detect_missing_sections(row) == []


class TestTradeEdgeCases:
    def test_inf_value_skipped(self, db_with_positions):
        import asyncio

        async def _add_inf():
            await db_with_positions.write_many(
                "INSERT INTO result_series (run_id, source, series_type, ts, value) "
                "VALUES (?, ?, ?, ?, ?)",
                [("t_run_a", "strategy", "positions", "2024-01-04", float("inf"))],
            )

        asyncio.get_event_loop().run_until_complete(_add_inf())
        result = compare_trades(db_with_positions, "t_run_a", "t_run_b")
        assert len(result.trades_a) == 3

    def test_nan_value_skipped(self, db_with_positions):
        import asyncio

        async def _add_nan():
            await db_with_positions.write_many(
                "INSERT INTO result_series (run_id, source, series_type, ts, value) "
                "VALUES (?, ?, ?, ?, ?)",
                [("t_run_a", "strategy", "positions", "2024-01-04", float("nan"))],
            )

        asyncio.get_event_loop().run_until_complete(_add_nan())
        result = compare_trades(db_with_positions, "t_run_a", "t_run_b")
        for t in result.trades_a:
            import math

            assert math.isfinite(t.quantity)
