"""ATDD: Story 2.9 — Strategy Lab & Backtest Viewer Web Pages."""

from __future__ import annotations

import time

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from trade_advisor.core.config import DatabaseConfig
from trade_advisor.data.storage import DataRepository
from trade_advisor.infra.db import DatabaseManager


def _make_ohlcv_for_backtest(n: int = 500, symbol: str = "TEST", start: str = "2020-01-01"):
    from tests.support.factories.ohlcv_factory import make_ohlcv

    return make_ohlcv(n=n, symbol=symbol, start=start, seed=42)


@pytest_asyncio.fixture
async def async_client_with_data():
    from trade_advisor.main import app

    config = DatabaseConfig(path=":memory:")
    db = DatabaseManager(config)
    async with db:
        original_db = getattr(app.state, "db", None)
        app.state.db = db
        try:
            df = _make_ohlcv_for_backtest(n=500, symbol="SPY", start="2020-01-01")
            repo = DataRepository(db)
            await repo.store(df, provider_name="synthetic")

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                yield client
        finally:
            app.state.db = original_db


@pytest.fixture(autouse=True)
def _reset_result_store():
    from trade_advisor.web.services.result_store import get_result_store

    get_result_store()._store.clear()
    yield
    get_result_store()._store.clear()


class TestStrategyLabPage:
    @pytest.mark.asyncio
    async def test_strategy_lab_page_renders(self, async_client_with_data):
        response = await async_client_with_data.get("/strategies")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_strategy_lab_form_has_defaults(self, async_client_with_data):
        response = await async_client_with_data.get("/strategies")
        text = response.text
        assert "SPY" in text
        assert 'value="20"' in text
        assert 'value="50"' in text
        assert "1d" in text

    @pytest.mark.asyncio
    async def test_strategy_lab_form_has_interval_selector(self, async_client_with_data):
        response = await async_client_with_data.get("/strategies")
        text = response.text
        assert "interval" in text
        assert "1h" in text
        assert "5m" in text

    @pytest.mark.asyncio
    async def test_strategy_lab_select_engine_mode(self, async_client_with_data):
        response = await async_client_with_data.get("/strategies")
        text = response.text
        assert "vectorized" in text.lower()
        assert "event" in text.lower()

    @pytest.mark.asyncio
    async def test_strategy_lab_configure_cost_model(self, async_client_with_data):
        response = await async_client_with_data.get("/strategies")
        text = response.text
        assert "commission" in text.lower()

    @pytest.mark.asyncio
    async def test_strategy_lab_htmx_partial_render(self, async_client_with_data):
        response = await async_client_with_data.get("/strategies", headers={"hx-request": "true"})
        assert response.status_code == 200
        assert "DOCTYPE" not in response.text or "<html" not in response.text.lower()

    @pytest.mark.asyncio
    async def test_strategy_lab_full_page_render(self, async_client_with_data):
        response = await async_client_with_data.get("/strategies")
        assert response.status_code == 200
        assert "<!DOCTYPE html>" in response.text
        assert "Strategy Lab" in response.text

    @pytest.mark.asyncio
    async def test_strategy_lab_nav_link(self, async_client_with_data):
        response = await async_client_with_data.get("/strategies")
        assert "/strategies" in response.text
        assert "Strategy Lab" in response.text


class TestBacktestViewer:
    @pytest.mark.asyncio
    async def test_backtest_viewer_404_for_missing(self, async_client_with_data):
        response = await async_client_with_data.get("/backtests/nonexistent123")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_backtests_index_redirects_to_strategies(self, async_client_with_data):
        response = await async_client_with_data.get("/backtests", follow_redirects=False)
        assert response.status_code == 302
        assert "/strategies" in response.headers.get("location", "")

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
    @pytest.mark.asyncio
    async def test_sse_endpoint_returns_event_stream(self, async_client_with_data):
        response = await async_client_with_data.get("/strategies/run/test123/stream")
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")


class TestRunBacktest:
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

    @pytest.mark.asyncio
    async def test_page_load_under_3_seconds(self, async_client_with_data):
        start = time.monotonic()
        await async_client_with_data.get("/strategies")
        elapsed = time.monotonic() - start
        assert elapsed < 3.0


class TestSerialization:
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
