"""ATDD: Story 2.9 — Strategy Lab & Backtest Viewer Web Pages."""

from __future__ import annotations

import time

import pytest


class TestStrategyLabPage:
    @pytest.mark.test_id("2.9-ATDD-001")
    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_strategy_lab_page_renders(self, async_client_with_data):
        response = await async_client_with_data.get("/strategies")
        assert response.status_code == 200

    @pytest.mark.test_id("2.9-ATDD-002")
    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_strategy_lab_form_has_defaults(self, async_client_with_data):
        response = await async_client_with_data.get("/strategies")
        text = response.text
        assert "SPY" in text
        assert 'value="20"' in text
        assert 'value="50"' in text
        assert "1d" in text

    @pytest.mark.test_id("2.9-ATDD-003")
    @pytest.mark.p2
    @pytest.mark.asyncio
    async def test_strategy_lab_form_has_interval_selector(self, async_client_with_data):
        response = await async_client_with_data.get("/strategies")
        text = response.text
        assert "interval" in text
        assert "1h" in text
        assert "5m" in text

    @pytest.mark.test_id("2.9-ATDD-004")
    @pytest.mark.p2
    @pytest.mark.asyncio
    async def test_strategy_lab_select_engine_mode(self, async_client_with_data):
        response = await async_client_with_data.get("/strategies")
        text = response.text
        assert "vectorized" in text.lower()
        assert "event" in text.lower()

    @pytest.mark.test_id("2.9-ATDD-005")
    @pytest.mark.p2
    @pytest.mark.asyncio
    async def test_strategy_lab_configure_cost_model(self, async_client_with_data):
        response = await async_client_with_data.get("/strategies")
        text = response.text
        assert "commission" in text.lower()

    @pytest.mark.test_id("2.9-ATDD-006")
    @pytest.mark.p2
    @pytest.mark.asyncio
    async def test_strategy_lab_htmx_partial_render(self, async_client_with_data):
        response = await async_client_with_data.get("/strategies", headers={"hx-request": "true"})
        assert response.status_code == 200
        assert "DOCTYPE" not in response.text or "<html" not in response.text.lower()

    @pytest.mark.test_id("2.9-ATDD-007")
    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_strategy_lab_full_page_render(self, async_client_with_data):
        response = await async_client_with_data.get("/strategies")
        assert response.status_code == 200
        assert "<!DOCTYPE html>" in response.text
        assert "Strategy Lab" in response.text

    @pytest.mark.test_id("2.9-ATDD-008")
    @pytest.mark.p2
    @pytest.mark.asyncio
    async def test_strategy_lab_nav_link(self, async_client_with_data):
        response = await async_client_with_data.get("/strategies")
        assert "/strategies" in response.text
        assert "Strategy Lab" in response.text


class TestBacktestViewer:
    @pytest.mark.test_id("2.9-ATDD-009")
    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_backtest_viewer_404_for_missing(self, async_client_with_data):
        response = await async_client_with_data.get("/backtests/nonexistent123")
        assert response.status_code == 404

    @pytest.mark.test_id("2.9-ATDD-010")
    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_backtests_index_redirects_to_strategies(self, async_client_with_data):
        response = await async_client_with_data.get("/backtests", follow_redirects=False)
        assert response.status_code == 302
        assert "/strategies" in response.headers.get("location", "")

    @pytest.mark.test_id("2.9-ATDD-011")
    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_backtest_viewer_page_renders_after_run(self, async_client_with_data):
        run_response = await async_client_with_data.post(
            "/strategies/run",
            data={
                "strategy_type": "sma",
                "symbol": "SPY",
                "fast": "20",
                "slow": "50",
                "interval": "1d",
                "start_date": "2021-01-01",
                "end_date": "2024-01-01",
                "engine_mode": "vectorized",
                "commission_pct": "0.001",
                "slippage_pct": "0.0005",
                "initial_cash": "100000",
            },
            headers={"hx-request": "true"},
        )
        redirect_url = run_response.headers.get("hx-redirect", "")
        assert redirect_url, f"Expected HX-Redirect, got: {run_response.headers}"
        run_id = redirect_url.split("/")[-1]

        response = await async_client_with_data.get(f"/backtests/{run_id}")
        assert response.status_code == 200
        assert "Strategy Metrics" in response.text or "Total Return" in response.text

    @pytest.mark.test_id("2.9-ATDD-012")
    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_backtest_viewer_shows_is_label(self, async_client_with_data):
        run_response = await async_client_with_data.post(
            "/strategies/run",
            data={
                "strategy_type": "sma",
                "symbol": "SPY",
                "fast": "20",
                "slow": "50",
                "interval": "1d",
                "start_date": "2021-01-01",
                "end_date": "2024-01-01",
                "engine_mode": "vectorized",
                "commission_pct": "0.001",
                "slippage_pct": "0.0005",
                "initial_cash": "100000",
            },
            headers={"hx-request": "true"},
        )
        redirect_url = run_response.headers.get("hx-redirect", "")
        run_id = redirect_url.split("/")[-1]

        response = await async_client_with_data.get(f"/backtests/{run_id}")
        assert "In-Sample Only" in response.text

    @pytest.mark.test_id("2.9-ATDD-013")
    @pytest.mark.p2
    @pytest.mark.asyncio
    async def test_backtest_viewer_equity_curve_render(self, async_client_with_data):
        run_response = await async_client_with_data.post(
            "/strategies/run",
            data={
                "strategy_type": "sma",
                "symbol": "SPY",
                "fast": "20",
                "slow": "50",
                "interval": "1d",
                "start_date": "2021-01-01",
                "end_date": "2024-01-01",
                "engine_mode": "vectorized",
                "commission_pct": "0.001",
                "slippage_pct": "0.0005",
                "initial_cash": "100000",
            },
            headers={"hx-request": "true"},
        )
        redirect_url = run_response.headers.get("hx-redirect", "")
        run_id = redirect_url.split("/")[-1]

        response = await async_client_with_data.get(f"/backtests/{run_id}")
        assert 'data-preact-mount="equityChart"' in response.text

    @pytest.mark.test_id("2.9-ATDD-014")
    @pytest.mark.p2
    @pytest.mark.asyncio
    async def test_equity_chart_props_no_decimal(self, async_client_with_data):
        run_response = await async_client_with_data.post(
            "/strategies/run",
            data={
                "strategy_type": "sma",
                "symbol": "SPY",
                "fast": "20",
                "slow": "50",
                "interval": "1d",
                "start_date": "2021-01-01",
                "end_date": "2024-01-01",
                "engine_mode": "vectorized",
                "commission_pct": "0.001",
                "slippage_pct": "0.0005",
                "initial_cash": "100000",
            },
            headers={"hx-request": "true"},
        )
        redirect_url = run_response.headers.get("hx-redirect", "")
        run_id = redirect_url.split("/")[-1]

        response = await async_client_with_data.get(f"/backtests/{run_id}")
        assert "Decimal" not in response.text


class TestStrategyValidation:
    @pytest.mark.test_id("2.9-ATDD-015")
    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_fast_equals_slow_rejected(self, async_client_with_data):
        response = await async_client_with_data.post(
            "/strategies/run",
            data={
                "strategy_type": "sma",
                "symbol": "SPY",
                "fast": "50",
                "slow": "50",
                "interval": "1d",
                "start_date": "2021-01-01",
                "end_date": "2024-01-01",
                "engine_mode": "vectorized",
                "commission_pct": "0.001",
                "slippage_pct": "0.0005",
                "initial_cash": "100000",
            },
        )
        assert "must be less than" in response.text

    @pytest.mark.test_id("2.9-ATDD-016")
    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_fast_greater_than_slow_rejected(self, async_client_with_data):
        response = await async_client_with_data.post(
            "/strategies/run",
            data={
                "strategy_type": "sma",
                "symbol": "SPY",
                "fast": "50",
                "slow": "20",
                "interval": "1d",
                "start_date": "2021-01-01",
                "end_date": "2024-01-01",
                "engine_mode": "vectorized",
                "commission_pct": "0.001",
                "slippage_pct": "0.0005",
                "initial_cash": "100000",
            },
        )
        assert "must be less than" in response.text

    @pytest.mark.test_id("2.9-ATDD-017")
    @pytest.mark.p2
    @pytest.mark.asyncio
    async def test_zero_initial_cash_rejected(self, async_client_with_data):
        response = await async_client_with_data.post(
            "/strategies/run",
            data={
                "strategy_type": "sma",
                "symbol": "SPY",
                "fast": "20",
                "slow": "50",
                "interval": "1d",
                "start_date": "2021-01-01",
                "end_date": "2024-01-01",
                "engine_mode": "vectorized",
                "commission_pct": "0.001",
                "slippage_pct": "0.0005",
                "initial_cash": "0",
            },
        )
        assert "positive" in response.text.lower() or "cash" in response.text.lower()

    @pytest.mark.test_id("2.9-ATDD-018")
    @pytest.mark.p2
    @pytest.mark.asyncio
    async def test_missing_symbol_rejected(self, async_client_with_data):
        response = await async_client_with_data.post(
            "/strategies/run",
            data={
                "strategy_type": "sma",
                "symbol": "   ",
                "fast": "20",
                "slow": "50",
                "interval": "1d",
                "start_date": "2021-01-01",
                "end_date": "2024-01-01",
                "engine_mode": "vectorized",
                "commission_pct": "0.001",
                "slippage_pct": "0.0005",
                "initial_cash": "100000",
            },
        )
        text = response.text.lower()
        assert "required" in text or "invalid" in text or "no cached data" in text

    @pytest.mark.test_id("2.9-ATDD-019")
    @pytest.mark.p2
    @pytest.mark.asyncio
    async def test_invalid_dates_rejected(self, async_client_with_data):
        response = await async_client_with_data.post(
            "/strategies/run",
            data={
                "strategy_type": "sma",
                "symbol": "SPY",
                "fast": "20",
                "slow": "50",
                "interval": "1d",
                "start_date": "2024-01-01",
                "end_date": "2021-01-01",
                "engine_mode": "vectorized",
                "commission_pct": "0.001",
                "slippage_pct": "0.0005",
                "initial_cash": "100000",
            },
        )
        assert "before" in response.text.lower() or "date" in response.text.lower()


class TestSSEStream:
    @pytest.mark.test_id("2.9-ATDD-020")
    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_sse_endpoint_returns_event_stream(self, async_client_with_data):
        response = await async_client_with_data.get("/strategies/run/test123/stream")
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")


class TestRunBacktest:
    @pytest.mark.test_id("2.9-ATDD-021")
    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_run_backtest_no_data(self, async_client_with_data):
        response = await async_client_with_data.post(
            "/strategies/run",
            data={
                "strategy_type": "sma",
                "symbol": "NONEXISTENT",
                "fast": "20",
                "slow": "50",
                "interval": "1d",
                "start_date": "2021-01-01",
                "end_date": "2024-01-01",
                "engine_mode": "vectorized",
                "commission_pct": "0.001",
                "slippage_pct": "0.0005",
                "initial_cash": "100000",
            },
        )
        assert "No cached data" in response.text or "error" in response.text.lower()

    @pytest.mark.test_id("2.9-ATDD-022")
    @pytest.mark.p2
    @pytest.mark.asyncio
    async def test_page_load_under_3_seconds(self, async_client_with_data):
        start = time.monotonic()
        await async_client_with_data.get("/strategies")
        elapsed = time.monotonic() - start
        assert elapsed < 3.0


class TestSerialization:
    @pytest.mark.test_id("2.9-ATDD-023")
    @pytest.mark.p1
    def test_metrics_to_context_converts_decimals(self):
        from decimal import Decimal

        from trade_advisor.backtest.metrics.performance import PerformanceMetrics

        metrics = PerformanceMetrics(
            total_return=Decimal("0.25"),
            cagr=Decimal("0.10"),
            sharpe=1.5,
            sortino=1.2,
            calmar=0.8,
            max_drawdown=Decimal("-0.15"),
            alpha=0.02,
            beta=1.0,
            information_ratio=0.5,
        )

        from trade_advisor.web.routes.backtests import _metrics_to_context

        ctx = _metrics_to_context(metrics)
        assert isinstance(ctx["total_return"], float)
        assert isinstance(ctx["cagr"], float)
        assert isinstance(ctx["max_drawdown"], float)
        assert isinstance(ctx["sharpe"], float)
        assert ctx["total_return"] == 0.25


class TestSparklineAnimation:
    @pytest.mark.test_id("2.9-ATDD-024")
    @pytest.mark.p1
    def test_sparkline_draw_duration_constant(self):
        from trade_advisor.web.components.result_card import SPARKLINE_DRAW_DURATION_MS

        assert SPARKLINE_DRAW_DURATION_MS == 600

    @pytest.mark.test_id("2.9-ATDD-025")
    @pytest.mark.p1
    def test_render_sparkline_produces_svg(self):
        from trade_advisor.web.components.result_card import render_sparkline

        svg = render_sparkline([1.0, 2.0, 1.5, 3.0, 2.5])
        assert svg.startswith("<svg")
        assert "sparkline" in svg
        assert "polyline" in svg

    @pytest.mark.test_id("2.9-ATDD-026")
    @pytest.mark.p1
    def test_render_sparkline_animation_600ms(self):
        from trade_advisor.web.components.result_card import render_sparkline

        svg = render_sparkline([1.0, 2.0, 3.0])
        assert "600ms" in svg
        assert "sparkline-draw" in svg

    @pytest.mark.test_id("2.9-ATDD-027")
    @pytest.mark.p2
    def test_render_sparkline_empty_for_single_value(self):
        from trade_advisor.web.components.result_card import render_sparkline

        assert render_sparkline([1.0]) == ""

    @pytest.mark.test_id("2.9-ATDD-028")
    @pytest.mark.p2
    def test_render_sparkline_has_aria_label(self):
        from trade_advisor.web.components.result_card import render_sparkline

        svg = render_sparkline([1.0, 2.0, 3.0])
        assert "aria-label" in svg
        assert "3 data points" in svg

    @pytest.mark.test_id("2.9-ATDD-029")
    @pytest.mark.p2
    @pytest.mark.asyncio
    async def test_base_html_has_sparkline_keyframes(self, async_client_with_data):
        response = await async_client_with_data.get("/strategies")
        assert "sparkline-draw" in response.text

    @pytest.mark.test_id("2.9-ATDD-030")
    @pytest.mark.p2
    @pytest.mark.asyncio
    async def test_base_html_reduced_motion_disables_sparkline(self, async_client_with_data):
        response = await async_client_with_data.get("/strategies")
        assert "stroke-dashoffset: 0" in response.text
