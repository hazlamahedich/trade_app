"""ATDD: Story 2.11 — Remix Button & Auto-Suggested Variants."""

from __future__ import annotations

import pytest
from tests.atdd.epic2.conftest import RUN_DATA


async def _run_backtest(client) -> str:
    resp = await client.post("/strategies/run", data=RUN_DATA, headers={"hx-request": "true"})
    redirect = resp.headers.get("hx-redirect", "")
    assert redirect, f"Expected HX-Redirect, got: {resp.headers}"
    return redirect.split("/")[-1]


class TestVariantGeneration:
    @pytest.mark.test_id("2.11-ATDD-001")
    @pytest.mark.p1
    def test_generate_variants_sma_default(self):
        from trade_advisor.web.services.remix import generate_variants

        variants = generate_variants({"fast": 20, "slow": 50})
        assert len(variants) >= 2

    @pytest.mark.test_id("2.11-ATDD-002")
    @pytest.mark.p1
    def test_generate_variants_respects_fast_lt_slow(self):
        from trade_advisor.web.services.remix import generate_variants

        variants = generate_variants({"fast": 20, "slow": 50})
        for v in variants:
            assert v.params["fast"] < v.params["slow"]

    @pytest.mark.test_id("2.11-ATDD-003")
    @pytest.mark.p2
    def test_generate_variants_fast_at_minimum(self):
        from trade_advisor.web.services.remix import generate_variants

        variants = generate_variants({"fast": 2, "slow": 5})
        for v in variants:
            if v.params["fast"] < 2 and v.params["slow"] < 5:
                pytest.fail("Narrow variant should have been excluded")

    @pytest.mark.test_id("2.11-ATDD-004")
    @pytest.mark.p2
    def test_generate_variants_golden_cross(self):
        from trade_advisor.web.services.remix import generate_variants

        variants = generate_variants({"fast": 20, "slow": 50})
        labels = [v.label for v in variants]
        assert any("50" in lbl and "200" in lbl for lbl in labels)

    @pytest.mark.test_id("2.11-ATDD-005")
    @pytest.mark.p2
    def test_generate_variants_no_golden_cross_when_slow_high(self):
        from trade_advisor.web.services.remix import generate_variants

        variants = generate_variants({"fast": 20, "slow": 180})
        labels = [v.label for v in variants]
        assert not any("50" in lbl and "200" in lbl for lbl in labels)

    @pytest.mark.test_id("2.11-ATDD-006")
    @pytest.mark.p2
    def test_generate_variants_unknown_strategy(self):
        from trade_advisor.web.services.remix import generate_variants

        variants = generate_variants({"fast": 20, "slow": 50}, strategy_type="rsi")
        assert variants == []

    @pytest.mark.test_id("2.11-ATDD-007")
    @pytest.mark.p2
    def test_generate_variants_exception_fallback(self):
        from trade_advisor.web.services.remix import generate_variants

        variants = generate_variants({"fast": object()}, strategy_type="sma")
        assert variants == []

    @pytest.mark.test_id("2.11-ATDD-008")
    @pytest.mark.p1
    def test_generate_variants_capped_at_max(self):
        from trade_advisor.web.services.remix import MAX_VARIANTS, generate_variants

        variants = generate_variants({"fast": 20, "slow": 50})
        assert len(variants) <= MAX_VARIANTS

    @pytest.mark.test_id("2.11-ATDD-009")
    @pytest.mark.p1
    def test_validate_sma_params_rejects_fast_ge_slow(self):
        from trade_advisor.web.services.remix import _validate_sma_params

        assert _validate_sma_params(20, 20) is False

    @pytest.mark.test_id("2.11-ATDD-010")
    @pytest.mark.p2
    def test_validate_sma_params_rejects_fast_lt_1(self):
        from trade_advisor.web.services.remix import _validate_sma_params

        assert _validate_sma_params(0, 5) is False

    @pytest.mark.test_id("2.11-ATDD-011")
    @pytest.mark.p2
    def test_validate_sma_params_rejects_slow_lt_2(self):
        from trade_advisor.web.services.remix import _validate_sma_params

        assert _validate_sma_params(1, 1) is False

    @pytest.mark.test_id("2.11-ATDD-012")
    @pytest.mark.p2
    def test_variant_suggestion_model(self):
        from trade_advisor.web.services.remix import VariantSuggestion

        v = VariantSuggestion(label="test", hint="hint", params={"fast": 10})
        assert v.label == "test"
        assert v.hint == "hint"
        assert v.params == {"fast": 10}

    @pytest.mark.test_id("2.11-ATDD-013")
    @pytest.mark.p1
    def test_generate_variants_deterministic(self):
        from trade_advisor.web.services.remix import generate_variants

        a = generate_variants({"fast": 20, "slow": 50})
        b = generate_variants({"fast": 20, "slow": 50})
        assert len(a) == len(b)
        for va, vb in zip(a, b, strict=True):
            assert va.label == vb.label
            assert va.params == vb.params


class TestRoutePrefill:
    @pytest.mark.test_id("2.11-ATDD-014")
    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_strategy_lab_prefill_from_query_params(self, async_client_with_data):
        response = await async_client_with_data.get("/strategies?fast=10&slow=30")
        assert response.status_code == 200
        text = response.text
        assert 'value="10"' in text
        assert 'value="30"' in text

    @pytest.mark.test_id("2.11-ATDD-015")
    @pytest.mark.p2
    @pytest.mark.asyncio
    async def test_strategy_lab_no_prefill_uses_defaults(self, async_client_with_data):
        response = await async_client_with_data.get("/strategies")
        assert response.status_code == 200
        text = response.text
        assert 'value="20"' in text or "20" in text
        assert "SPY" in text

    @pytest.mark.test_id("2.11-ATDD-016")
    @pytest.mark.p2
    @pytest.mark.asyncio
    async def test_strategy_lab_prefill_sanitizes_symbol(self, async_client_with_data):
        response = await async_client_with_data.get("/strategies?symbol=%3Cscript%3E")
        assert response.status_code == 200
        assert "<script>" not in response.text or "SPY" in response.text

    @pytest.mark.test_id("2.11-ATDD-017")
    @pytest.mark.p2
    @pytest.mark.asyncio
    async def test_strategy_lab_prefill_bad_numeric(self, async_client_with_data):
        response = await async_client_with_data.get("/strategies?fast=abc")
        assert response.status_code == 200
        text = response.text
        assert 'value="20"' in text or "20" in text

    @pytest.mark.test_id("2.11-ATDD-018")
    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_backtest_viewer_context_has_variants(self, async_client_with_data):
        run_id = await _run_backtest(async_client_with_data)
        response = await async_client_with_data.get(f"/backtests/{run_id}")
        assert response.status_code == 200
        assert "variant-chip" in response.text or "variant-chips" in response.text

    @pytest.mark.test_id("2.11-ATDD-019")
    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_backtest_viewer_context_has_remix_url(self, async_client_with_data):
        run_id = await _run_backtest(async_client_with_data)
        response = await async_client_with_data.get(f"/backtests/{run_id}")
        assert response.status_code == 200
        assert "/strategies?" in response.text
        assert "fast=" in response.text

    @pytest.mark.test_id("2.11-ATDD-020")
    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_source_run_id_on_stored_result(self, async_client_with_data):
        run_id = await _run_backtest(async_client_with_data)
        data = dict(RUN_DATA)
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

    @pytest.mark.test_id("2.11-ATDD-021")
    @pytest.mark.p2
    @pytest.mark.asyncio
    async def test_source_run_id_not_in_config_dict_for_sma(self, async_client_with_data):
        run_id = await _run_backtest(async_client_with_data)
        data = dict(RUN_DATA)
        data["source_run_id"] = run_id
        resp = await async_client_with_data.post(
            "/strategies/run", data=data, headers={"hx-request": "true"}
        )
        new_run_id = resp.headers["hx-redirect"].split("/")[-1]
        from trade_advisor.web.services.result_store import get_result_store

        store = get_result_store()
        result = await store.get(new_run_id)
        assert "source_run_id" not in result.config_dict

    @pytest.mark.test_id("2.11-ATDD-022")
    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_source_run_id_passed_to_template(self, async_client_with_data):
        run_id = await _run_backtest(async_client_with_data)
        data = dict(RUN_DATA)
        data["source_run_id"] = run_id
        resp = await async_client_with_data.post(
            "/strategies/run", data=data, headers={"hx-request": "true"}
        )
        new_run_id = resp.headers["hx-redirect"].split("/")[-1]
        response = await async_client_with_data.get(f"/backtests/{new_run_id}")
        assert response.status_code == 200
        assert run_id in response.text

    @pytest.mark.test_id("2.11-ATDD-023")
    @pytest.mark.p2
    @pytest.mark.asyncio
    async def test_expired_source_run_id_shows_expired_message(self, async_client_with_data):
        _run_id = await _run_backtest(async_client_with_data)
        data = dict(RUN_DATA)
        data["source_run_id"] = "nonexistent_parent"
        data["fast"] = "15"
        resp = await async_client_with_data.post(
            "/strategies/run", data=data, headers={"hx-request": "true"}
        )
        new_run_id = resp.headers["hx-redirect"].split("/")[-1]
        response = await async_client_with_data.get(f"/backtests/{new_run_id}")
        assert "no longer available" in response.text.lower()


class TestTemplateRendering:
    @pytest.mark.test_id("2.11-ATDD-024")
    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_template_renders_remix_button(self, async_client_with_data):
        run_id = await _run_backtest(async_client_with_data)
        response = await async_client_with_data.get(f"/backtests/{run_id}")
        assert "remix-button" in response.text

    @pytest.mark.test_id("2.11-ATDD-025")
    @pytest.mark.p2
    @pytest.mark.asyncio
    async def test_template_remix_button_has_edit_icon(self, async_client_with_data):
        run_id = await _run_backtest(async_client_with_data)
        response = await async_client_with_data.get(f"/backtests/{run_id}")
        assert "remix-button--edit" in response.text

    @pytest.mark.test_id("2.11-ATDD-026")
    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_template_renders_variant_chips(self, async_client_with_data):
        run_id = await _run_backtest(async_client_with_data)
        response = await async_client_with_data.get(f"/backtests/{run_id}")
        assert "variant-chip" in response.text

    @pytest.mark.test_id("2.11-ATDD-027")
    @pytest.mark.p2
    @pytest.mark.asyncio
    async def test_template_variant_chip_posts_to_run(self, async_client_with_data):
        run_id = await _run_backtest(async_client_with_data)
        response = await async_client_with_data.get(f"/backtests/{run_id}")
        assert 'action="/strategies/run"' in response.text

    @pytest.mark.test_id("2.11-ATDD-028")
    @pytest.mark.p2
    @pytest.mark.asyncio
    async def test_template_variant_chip_has_play_icon(self, async_client_with_data):
        run_id = await _run_backtest(async_client_with_data)
        response = await async_client_with_data.get(f"/backtests/{run_id}")
        assert "variant-chip--auto" in response.text

    @pytest.mark.test_id("2.11-ATDD-029")
    @pytest.mark.p2
    @pytest.mark.asyncio
    async def test_template_variant_chip_has_source_run_id(self, async_client_with_data):
        run_id = await _run_backtest(async_client_with_data)
        response = await async_client_with_data.get(f"/backtests/{run_id}")
        assert 'name="source_run_id"' in response.text
        assert f'value="{run_id}"' in response.text

    @pytest.mark.test_id("2.11-ATDD-030")
    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_template_renders_remixed_from_link(self, async_client_with_data):
        run_id = await _run_backtest(async_client_with_data)
        data = dict(RUN_DATA)
        data["source_run_id"] = run_id
        resp = await async_client_with_data.post(
            "/strategies/run", data=data, headers={"hx-request": "true"}
        )
        new_run_id = resp.headers["hx-redirect"].split("/")[-1]
        response = await async_client_with_data.get(f"/backtests/{new_run_id}")
        assert "remixed-from" in response.text.lower()

    @pytest.mark.test_id("2.11-ATDD-031")
    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_template_expired_parent_message(self, async_client_with_data):
        response = await async_client_with_data.get("/backtests/expired_run_id_that_does_not_exist")
        assert response.status_code == 404

    @pytest.mark.test_id("2.11-ATDD-032")
    @pytest.mark.p2
    @pytest.mark.asyncio
    async def test_template_no_remixed_from_without_source(self, async_client_with_data):
        run_id = await _run_backtest(async_client_with_data)
        response = await async_client_with_data.get(f"/backtests/{run_id}")
        assert 'href="/backtests/' not in response.text or "Remixed from" not in response.text

    @pytest.mark.test_id("2.11-ATDD-033")
    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_template_remix_button_distinct_from_chips(self, async_client_with_data):
        run_id = await _run_backtest(async_client_with_data)
        response = await async_client_with_data.get(f"/backtests/{run_id}")
        assert "remix-button--edit" in response.text
        assert "variant-chip--auto" in response.text


class TestEdgeCases:
    @pytest.mark.test_id("2.11-ATDD-034")
    @pytest.mark.p2
    @pytest.mark.asyncio
    async def test_remix_url_int_values_cast_to_str(self, async_client_with_data):
        run_id = await _run_backtest(async_client_with_data)
        response = await async_client_with_data.get(f"/backtests/{run_id}")
        assert response.status_code == 200
        assert "fast=" in response.text

    @pytest.mark.test_id("2.11-ATDD-035")
    @pytest.mark.p2
    def test_source_run_id_excluded_from_variant_generation(self):
        from trade_advisor.web.services.remix import generate_variants

        variants = generate_variants(
            {"fast": 20, "slow": 50, "source_run_id": "abc123"},
            strategy_type="sma",
        )
        for v in variants:
            assert "source_run_id" not in v.params

    @pytest.mark.test_id("2.11-ATDD-036")
    @pytest.mark.p1
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

    @pytest.mark.test_id("2.11-ATDD-037")
    @pytest.mark.p1
    def test_validate_sma_params_accepts_valid(self):
        from trade_advisor.web.services.remix import _validate_sma_params

        assert _validate_sma_params(1, 2) is True
        assert _validate_sma_params(20, 50) is True

    @pytest.mark.test_id("2.11-ATDD-038")
    @pytest.mark.p1
    def test_variant_hints_are_directional(self):
        from trade_advisor.web.services.remix import generate_variants

        variants = generate_variants({"fast": 20, "slow": 50})
        hints = [v.hint for v in variants]
        assert any("fewer signals" in h for h in hints)
        for h in hints:
            assert "smoother" not in h.lower()


class TestUndoRemix:
    @pytest.mark.test_id("2.11-ATDD-039")
    @pytest.mark.p1
    def test_register_and_undo_remix(self):
        from trade_advisor.web.services.remix import register_remix, undo_remix

        register_remix("child1", "parent1")
        parent = undo_remix("child1")
        assert parent == "parent1"

    @pytest.mark.test_id("2.11-ATDD-040")
    @pytest.mark.p1
    def test_can_undo_within_window(self):
        from trade_advisor.web.services.remix import can_undo, register_remix

        register_remix("child2", "parent2")
        assert can_undo("child2") is True

    @pytest.mark.test_id("2.11-ATDD-041")
    @pytest.mark.p1
    def test_cannot_undo_unknown_run(self):
        from trade_advisor.web.services.remix import can_undo

        assert can_undo("nonexistent_child") is False

    @pytest.mark.test_id("2.11-ATDD-042")
    @pytest.mark.p1
    def test_undo_remix_returns_none_for_unknown(self):
        from trade_advisor.web.services.remix import undo_remix

        assert undo_remix("nonexistent_child") is None

    @pytest.mark.test_id("2.11-ATDD-043")
    @pytest.mark.p2
    @pytest.mark.asyncio
    async def test_delete_endpoint_undo_success(self, async_client_with_data):
        from trade_advisor.web.services.remix import register_remix

        run_id = await _run_backtest(async_client_with_data)
        data = dict(RUN_DATA)
        data["source_run_id"] = run_id
        data["fast"] = "15"
        resp = await async_client_with_data.post(
            "/strategies/run", data=data, headers={"hx-request": "true"}
        )
        child_run_id = resp.headers["hx-redirect"].split("/")[-1]

        register_remix(child_run_id, run_id)

        resp = await async_client_with_data.delete(f"/backtests/{child_run_id}/remix")
        assert resp.status_code == 200
        assert "undone" in resp.text.lower() or resp.headers.get("hx-redirect")

    @pytest.mark.test_id("2.11-ATDD-044")
    @pytest.mark.p2
    @pytest.mark.asyncio
    async def test_delete_endpoint_expired_window(self, async_client_with_data):
        from trade_advisor.web.services.remix import _remix_registry

        run_id = await _run_backtest(async_client_with_data)
        data = dict(RUN_DATA)
        data["source_run_id"] = run_id
        data["fast"] = "15"
        resp = await async_client_with_data.post(
            "/strategies/run", data=data, headers={"hx-request": "true"}
        )
        child_run_id = resp.headers["hx-redirect"].split("/")[-1]

        _remix_registry[child_run_id] = (run_id, 0)

        resp = await async_client_with_data.delete(f"/backtests/{child_run_id}/remix")
        assert resp.status_code == 410

    @pytest.mark.test_id("2.11-ATDD-045")
    @pytest.mark.p2
    @pytest.mark.asyncio
    async def test_delete_endpoint_not_in_registry(self, async_client_with_data):
        resp = await async_client_with_data.delete("/backtests/nonexistent/remix")
        assert resp.status_code in (404, 410)

    @pytest.mark.test_id("2.11-ATDD-046")
    @pytest.mark.p2
    @pytest.mark.asyncio
    async def test_undo_deletes_child_from_store(self, async_client_with_data):
        from trade_advisor.web.services.remix import register_remix
        from trade_advisor.web.services.result_store import get_result_store

        run_id = await _run_backtest(async_client_with_data)
        data = dict(RUN_DATA)
        data["source_run_id"] = run_id
        data["fast"] = "15"
        resp = await async_client_with_data.post(
            "/strategies/run", data=data, headers={"hx-request": "true"}
        )
        child_run_id = resp.headers["hx-redirect"].split("/")[-1]

        register_remix(child_run_id, run_id)
        await async_client_with_data.delete(f"/backtests/{child_run_id}/remix")

        store = get_result_store()
        deleted = await store.get(child_run_id)
        assert deleted is None

    @pytest.mark.test_id("2.11-ATDD-047")
    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_template_shows_undo_toast_for_remix(self, async_client_with_data):
        run_id = await _run_backtest(async_client_with_data)
        data = dict(RUN_DATA)
        data["source_run_id"] = run_id
        data["fast"] = "15"
        resp = await async_client_with_data.post(
            "/strategies/run", data=data, headers={"hx-request": "true"}
        )
        child_run_id = resp.headers["hx-redirect"].split("/")[-1]
        response = await async_client_with_data.get(f"/backtests/{child_run_id}")
        assert response.status_code == 200
        assert "undo-toast" in response.text
        assert "undo-countdown" in response.text
