from __future__ import annotations

from decimal import Decimal

import pytest

from trade_advisor.web.routes.backtests import _is_htmx, _metrics_to_context, _safe_float


class TestSafeFloat:
    def test_none_returns_fallback(self):
        assert _safe_float(None, 0.0) == 0.0

    def test_valid_number(self):
        assert _safe_float(3.14) == pytest.approx(3.14)

    def test_string_number(self):
        assert _safe_float("2.5") == pytest.approx(2.5)

    def test_nan_returns_fallback(self):
        assert _safe_float(float("nan")) == 0.0

    def test_inf_returns_fallback(self):
        assert _safe_float(float("inf")) == 0.0

    def test_negative_inf_returns_fallback(self):
        assert _safe_float(float("-inf")) == 0.0

    def test_decimal_converts(self):
        assert _safe_float(Decimal("1.5")) == pytest.approx(1.5)

    def test_custom_fallback(self):
        assert _safe_float(None, fallback=-1.0) == -1.0


class TestIsHtmx:
    def test_true_when_header_present(self):
        req = type("R", (), {"headers": {"hx-request": "true"}})()
        assert _is_htmx(req) is True

    def test_false_when_header_absent(self):
        req = type("R", (), {"headers": {}})()
        assert _is_htmx(req) is False

    def test_false_when_wrong_value(self):
        req = type("R", (), {"headers": {"hx-request": "false"}})()
        assert _is_htmx(req) is False


class TestMetricsToContext:
    def test_extracts_six_fields(self):
        metrics = type(
            "M",
            (),
            {
                "total_return": 0.1,
                "cagr": 0.05,
                "sharpe": 1.2,
                "max_drawdown": -0.08,
                "alpha": 0.03,
                "beta": 0.95,
            },
        )()
        ctx = _metrics_to_context(metrics)
        assert set(ctx.keys()) == {
            "total_return",
            "cagr",
            "sharpe",
            "max_drawdown",
            "alpha",
            "beta",
        }
        assert ctx["total_return"] == pytest.approx(0.1)

    def test_handles_nan_metrics(self):
        metrics = type(
            "M",
            (),
            {
                "total_return": float("nan"),
                "cagr": 0.05,
                "sharpe": float("inf"),
                "max_drawdown": -0.08,
                "alpha": 0.03,
                "beta": 0.95,
            },
        )()
        ctx = _metrics_to_context(metrics)
        assert ctx["total_return"] == 0.0
        assert ctx["sharpe"] == 0.0
        assert ctx["cagr"] == pytest.approx(0.05)
