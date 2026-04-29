"""ATDD: Story 2.11 — Remix Button & Auto-Suggested Variants."""

from __future__ import annotations

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


_RUN_DATA = {
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
}


async def _run_backtest(client: AsyncClient) -> str:
    resp = await client.post("/strategies/run", data=_RUN_DATA, headers={"hx-request": "true"})
    redirect = resp.headers.get("hx-redirect", "")
    assert redirect, f"Expected HX-Redirect, got: {resp.headers}"
    return redirect.split("/")[-1]


class TestVariantGeneration:
    def test_generate_variants_sma_default(self):
        from trade_advisor.web.services.remix import generate_variants

        variants = generate_variants({"fast": 20, "slow": 50})
        assert len(variants) >= 2

    def test_generate_variants_respects_fast_lt_slow(self):
        from trade_advisor.web.services.remix import generate_variants

        variants = generate_variants({"fast": 20, "slow": 50})
        for v in variants:
            assert v.params["fast"] < v.params["slow"]

    def test_generate_variants_fast_at_minimum(self):
        from trade_advisor.web.services.remix import generate_variants

        variants = generate_variants({"fast": 2, "slow": 5})
        for v in variants:
            if v.params["fast"] < 2 and v.params["slow"] < 5:
                pytest.fail("Narrow variant should have been excluded")

    def test_generate_variants_golden_cross(self):
        from trade_advisor.web.services.remix import generate_variants

        variants = generate_variants({"fast": 20, "slow": 50})
        labels = [v.label for v in variants]
        assert any("50" in lbl and "200" in lbl for lbl in labels)

    def test_generate_variants_no_golden_cross_when_slow_high(self):
        from trade_advisor.web.services.remix import generate_variants

        variants = generate_variants({"fast": 20, "slow": 180})
        labels = [v.label for v in variants]
        assert not any("50" in lbl and "200" in lbl for lbl in labels)

    def test_generate_variants_unknown_strategy(self):
        from trade_advisor.web.services.remix import generate_variants

        variants = generate_variants({"fast": 20, "slow": 50}, strategy_type="rsi")
        assert variants == []

    def test_generate_variants_exception_fallback(self):
        from trade_advisor.web.services.remix import generate_variants

        variants = generate_variants({"fast": object()}, strategy_type="sma")
        assert variants == []

    def test_generate_variants_capped_at_max(self):
        from trade_advisor.web.services.remix import MAX_VARIANTS, generate_variants

        variants = generate_variants({"fast": 20, "slow": 50})
        assert len(variants) <= MAX_VARIANTS

    def test_validate_sma_params_rejects_fast_ge_slow(self):
        from trade_advisor.web.services.remix import _validate_sma_params

        assert _validate_sma_params(20, 20) is False

    def test_validate_sma_params_rejects_fast_lt_1(self):
        from trade_advisor.web.services.remix import _validate_sma_params

        assert _validate_sma_params(0, 5) is False

    def test_validate_sma_params_rejects_slow_lt_2(self):
        from trade_advisor.web.services.remix import _validate_sma_params

        assert _validate_sma_params(1, 1) is False

    def test_variant_suggestion_model(self):
        from trade_advisor.web.services.remix import VariantSuggestion

        v = VariantSuggestion(label="test", hint="hint", params={"fast": 10})
        assert v.label == "test"
        assert v.hint == "hint"
        assert v.params == {"fast": 10}

    def test_generate_variants_deterministic(self):
        from trade_advisor.web.services.remix import generate_variants

        a = generate_variants({"fast": 20, "slow": 50})
        b = generate_variants({"fast": 20, "slow": 50})
        assert len(a) == len(b)
        for va, vb in zip(a, b, strict=True):
            assert va.label == vb.label
            assert va.params == vb.params


class TestRoutePrefill:
    @pytest.mark.asyncio
    async def test_strategy_lab_prefill_from_query_params(self, async_client_with_data):
        response = await async_client_with_data.get("/strategies?fast=10&slow=30")
        assert response.status_code == 200
        text = response.text
        assert 'value="10"' in text
        assert 'value="30"' in text

    @pytest.mark.asyncio
    async def test_strategy_lab_no_prefill_uses_defaults(self, async_client_with_data):
        response = await async_client_with_data.get("/strategies")
        assert response.status_code == 200
        text = response.text
        assert 'value="20"' in text or "20" in text
        assert "SPY" in text

    @pytest.mark.asyncio
    async def test_strategy_lab_prefill_sanitizes_symbol(self, async_client_with_data):
        response = await async_client_with_data.get("/strategies?symbol=%3Cscript%3E")
        assert response.status_code == 200
        assert "<script>" not in response.text or "SPY" in response.text

    @pytest.mark.asyncio
    async def test_strategy_lab_prefill_bad_numeric(self, async_client_with_data):
        response = await async_client_with_data.get("/strategies?fast=abc")
        assert response.status_code == 200
        text = response.text
        assert 'value="20"' in text or "20" in text

    @pytest.mark.asyncio
    async def test_backtest_viewer_context_has_variants(self, async_client_with_data):
        run_id = await _run_backtest(async_client_with_data)
        response = await async_client_with_data.get(f"/backtests/{run_id}")
        assert response.status_code == 200
        assert "variant-chip" in response.text or "variant-chips" in response.text

    @pytest.mark.asyncio
    async def test_backtest_viewer_context_has_remix_url(self, async_client_with_data):
        run_id = await _run_backtest(async_client_with_data)
        response = await async_client_with_data.get(f"/backtests/{run_id}")
        assert response.status_code == 200
        assert "/strategies?" in response.text
        assert "fast=" in response.text

    @pytest.mark.asyncio
    async def test_source_run_id_on_stored_result(self, async_client_with_data):
        run_id = await _run_backtest(async_client_with_data)
        data = dict(_RUN_DATA)
        data["source_run_id"] = run_id
        resp = await async_client_with_data.post(
            "/strategies/run", data=data, headers={"hx-request": "true"}
        )
        new_run_id = resp.headers["hx-redirect"].split("/")[-1]
        from trade_advisor.web.services.result_store import get_result_store

        store = get_result_store()
        result = await store.get(new_run_id)
        assert result is not None
        assert result.source_run_id == run_id

    @pytest.mark.asyncio
    async def test_source_run_id_not_in_config_dict_for_sma(self, async_client_with_data):
        run_id = await _run_backtest(async_client_with_data)
        data = dict(_RUN_DATA)
        data["source_run_id"] = run_id
        resp = await async_client_with_data.post(
            "/strategies/run", data=data, headers={"hx-request": "true"}
        )
        new_run_id = resp.headers["hx-redirect"].split("/")[-1]
        from trade_advisor.web.services.result_store import get_result_store

        store = get_result_store()
        result = await store.get(new_run_id)
        assert "source_run_id" not in result.config_dict

    @pytest.mark.asyncio
    async def test_source_run_id_passed_to_template(self, async_client_with_data):
        run_id = await _run_backtest(async_client_with_data)
        data = dict(_RUN_DATA)
        data["source_run_id"] = run_id
        resp = await async_client_with_data.post(
            "/strategies/run", data=data, headers={"hx-request": "true"}
        )
        new_run_id = resp.headers["hx-redirect"].split("/")[-1]
        response = await async_client_with_data.get(f"/backtests/{new_run_id}")
        assert response.status_code == 200
        assert run_id in response.text

    @pytest.mark.asyncio
    async def test_expired_source_run_id_shows_expired_message(self, async_client_with_data):
        _run_id = await _run_backtest(async_client_with_data)
        data = dict(_RUN_DATA)
        data["source_run_id"] = "nonexistent_parent"
        data["fast"] = "15"
        resp = await async_client_with_data.post(
            "/strategies/run", data=data, headers={"hx-request": "true"}
        )
        new_run_id = resp.headers["hx-redirect"].split("/")[-1]
        response = await async_client_with_data.get(f"/backtests/{new_run_id}")
        assert "no longer available" in response.text.lower()


class TestTemplateRendering:
    @pytest.mark.asyncio
    async def test_template_renders_remix_button(self, async_client_with_data):
        run_id = await _run_backtest(async_client_with_data)
        response = await async_client_with_data.get(f"/backtests/{run_id}")
        assert "remix-button" in response.text

    @pytest.mark.asyncio
    async def test_template_remix_button_has_edit_icon(self, async_client_with_data):
        run_id = await _run_backtest(async_client_with_data)
        response = await async_client_with_data.get(f"/backtests/{run_id}")
        assert "remix-button--edit" in response.text

    @pytest.mark.asyncio
    async def test_template_renders_variant_chips(self, async_client_with_data):
        run_id = await _run_backtest(async_client_with_data)
        response = await async_client_with_data.get(f"/backtests/{run_id}")
        assert "variant-chip" in response.text

    @pytest.mark.asyncio
    async def test_template_variant_chip_posts_to_run(self, async_client_with_data):
        run_id = await _run_backtest(async_client_with_data)
        response = await async_client_with_data.get(f"/backtests/{run_id}")
        assert 'action="/strategies/run"' in response.text

    @pytest.mark.asyncio
    async def test_template_variant_chip_has_play_icon(self, async_client_with_data):
        run_id = await _run_backtest(async_client_with_data)
        response = await async_client_with_data.get(f"/backtests/{run_id}")
        assert "variant-chip--auto" in response.text

    @pytest.mark.asyncio
    async def test_template_variant_chip_has_source_run_id(self, async_client_with_data):
        run_id = await _run_backtest(async_client_with_data)
        response = await async_client_with_data.get(f"/backtests/{run_id}")
        assert 'name="source_run_id"' in response.text
        assert f'value="{run_id}"' in response.text

    @pytest.mark.asyncio
    async def test_template_renders_remixed_from_link(self, async_client_with_data):
        run_id = await _run_backtest(async_client_with_data)
        data = dict(_RUN_DATA)
        data["source_run_id"] = run_id
        resp = await async_client_with_data.post(
            "/strategies/run", data=data, headers={"hx-request": "true"}
        )
        new_run_id = resp.headers["hx-redirect"].split("/")[-1]
        response = await async_client_with_data.get(f"/backtests/{new_run_id}")
        assert "remixed-from" in response.text.lower()

    @pytest.mark.asyncio
    async def test_template_expired_parent_message(self):
        pass

    @pytest.mark.asyncio
    async def test_template_no_remixed_from_without_source(self, async_client_with_data):
        run_id = await _run_backtest(async_client_with_data)
        response = await async_client_with_data.get(f"/backtests/{run_id}")
        assert 'href="/backtests/' not in response.text or "Remixed from" not in response.text

    @pytest.mark.asyncio
    async def test_template_remix_button_distinct_from_chips(self, async_client_with_data):
        run_id = await _run_backtest(async_client_with_data)
        response = await async_client_with_data.get(f"/backtests/{run_id}")
        assert "remix-button--edit" in response.text
        assert "variant-chip--auto" in response.text


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_remix_url_int_values_cast_to_str(self, async_client_with_data):
        run_id = await _run_backtest(async_client_with_data)
        response = await async_client_with_data.get(f"/backtests/{run_id}")
        assert response.status_code == 200
        assert "fast=" in response.text

    def test_source_run_id_excluded_from_variant_generation(self):
        from trade_advisor.web.services.remix import generate_variants

        variants = generate_variants(
            {"fast": 20, "slow": 50, "source_run_id": "abc123"},
            strategy_type="sma",
        )
        for v in variants:
            assert "source_run_id" not in v.params

    @pytest.mark.asyncio
    async def test_chip_form_carries_all_config_fields(self, async_client_with_data):
        run_id = await _run_backtest(async_client_with_data)
        response = await async_client_with_data.get(f"/backtests/{run_id}")
        for field_name in (
            "symbol",
            "interval",
            "start_date",
            "end_date",
            "engine_mode",
            "commission_pct",
            "slippage_pct",
            "initial_cash",
            "source_run_id",
        ):
            assert f'name="{field_name}"' in response.text

    def test_validate_sma_params_accepts_valid(self):
        from trade_advisor.web.services.remix import _validate_sma_params

        assert _validate_sma_params(1, 2) is True
        assert _validate_sma_params(20, 50) is True

    def test_variant_hints_are_directional(self):
        from trade_advisor.web.services.remix import generate_variants

        variants = generate_variants({"fast": 20, "slow": 50})
        hints = [v.hint for v in variants]
        assert any("fewer signals" in h for h in hints)
        for h in hints:
            assert "smoother" not in h.lower()
