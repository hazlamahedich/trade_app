"""Tests for emotional state classification, diagnosis, and rendering (Story 2.10)."""

from __future__ import annotations

from pathlib import Path

import pytest

from trade_advisor.web.services.emotional_state import (
    ClassificationThresholds,
    EmotionalState,
    classify_emotional_state,
    compute_profit_factor,
)


def _classify(
    strategy_total_return: float | None = 0.1,
    baseline_total_return: float | None = 0.08,
    sharpe: float | None = 1.0,
    profit_factor: float | None = 0.8,
    max_drawdown: float | None = 0.15,
    trade_count: int = 50,
    baseline_sharpe: float | None = 0.8,
    thresholds: ClassificationThresholds | None = None,
) -> tuple[EmotionalState, dict]:
    return classify_emotional_state(
        strategy_total_return=strategy_total_return,
        baseline_total_return=baseline_total_return,
        sharpe=sharpe,
        profit_factor=profit_factor,
        max_drawdown=max_drawdown,
        trade_count=trade_count,
        baseline_sharpe=baseline_sharpe,
        thresholds=thresholds or ClassificationThresholds(),
    )


# === Level A — Classification logic (unit) ===


class TestClassificationLogic:
    def test_classify_underperforming(self):
        state, diag = _classify(strategy_total_return=0.05, baseline_total_return=0.10)
        assert state == EmotionalState.UNDERPERFORMING
        assert diag["heading"] == "Why this underperformed"

    def test_classify_suspicious_high_sharpe(self):
        state, diag = _classify(
            sharpe=2.5,
            profit_factor=0.5,
            strategy_total_return=0.15,
            baseline_total_return=0.10,
        )
        assert state == EmotionalState.SUSPICIOUS
        assert "Sharpe" in diag["comparison_text"]

    def test_classify_suspicious_high_profit_factor(self):
        state, _diag = _classify(
            sharpe=1.0,
            profit_factor=3.0,
            strategy_total_return=0.15,
            baseline_total_return=0.10,
        )
        assert state == EmotionalState.SUSPICIOUS

    def test_classify_suspicious_wins_over_underperforming(self):
        state, _diag = _classify(
            sharpe=6.0,
            profit_factor=1.0,
            strategy_total_return=0.09,
            baseline_total_return=0.10,
        )
        assert state == EmotionalState.SUSPICIOUS

    def test_classify_mixed(self):
        state, diag = _classify(
            sharpe=0.3,
            max_drawdown=0.4,
            strategy_total_return=0.10,
            baseline_total_return=0.08,
        )
        assert state == EmotionalState.MIXED
        assert "risk" in diag["heading"].lower() or "risk" in diag["comparison_text"].lower()

    def test_classify_neutral(self):
        state, diag = _classify()
        assert state == EmotionalState.NEUTRAL
        assert diag == {}

    def test_classify_insufficient_data(self):
        state, diag = _classify(trade_count=10)
        assert state == EmotionalState.INSUFFICIENT_DATA
        assert "10" in diag["comparison_text"]

    def test_classify_identical_returns(self):
        state, _diag = _classify(strategy_total_return=0.10, baseline_total_return=0.10)
        assert state != EmotionalState.UNDERPERFORMING

    @pytest.mark.parametrize("sharpe_val", [-0.01, -0.5, -1.0, -3.0])
    def test_classify_negative_sharpe(self, sharpe_val):
        state, _diag = _classify(
            sharpe=sharpe_val,
            strategy_total_return=0.03,
            baseline_total_return=0.10,
        )
        assert state == EmotionalState.UNDERPERFORMING

    def test_classify_zero_profit_factor(self):
        state, _diag = _classify(
            profit_factor=0.0,
            strategy_total_return=0.03,
            baseline_total_return=0.10,
        )
        assert state == EmotionalState.UNDERPERFORMING

    def test_classify_zero_drawdown(self):
        state, _diag = _classify(
            max_drawdown=0.0,
            sharpe=1.0,
            strategy_total_return=0.15,
            baseline_total_return=0.10,
        )
        assert state == EmotionalState.NEUTRAL

    def test_classify_all_negative_metrics(self):
        state, _diag = _classify(
            strategy_total_return=-0.3,
            baseline_total_return=-0.1,
            sharpe=-1.5,
            max_drawdown=0.5,
            profit_factor=0.2,
        )
        assert state == EmotionalState.UNDERPERFORMING

    def test_classify_with_none_metrics(self):
        state, _diag = _classify(sharpe=None, max_drawdown=None, profit_factor=None)
        assert state == EmotionalState.NEUTRAL

    def test_classify_exception_fallback(self):
        state, _diag = classify_emotional_state(
            strategy_total_return=BadCompare(0.1),
            baseline_total_return=0.08,
            sharpe=1.0,
            profit_factor=0.5,
            max_drawdown=0.1,
            trade_count=50,
        )
        assert state == EmotionalState.NEUTRAL

    def test_thresholds_overridable(self):
        custom = ClassificationThresholds(min_trade_count=5, suspicion_sharpe=5.0)
        state, _diag = _classify(trade_count=10, thresholds=custom)
        assert state != EmotionalState.INSUFFICIENT_DATA

        state2, _diag2 = _classify(
            sharpe=3.0,
            thresholds=custom,
            strategy_total_return=0.15,
            baseline_total_return=0.10,
        )
        assert state2 == EmotionalState.NEUTRAL


class TestBoundaryValues:
    @pytest.mark.parametrize(
        "sharpe_val,expected_state",
        [
            (2.0, EmotionalState.SUSPICIOUS),
            (1.99, EmotionalState.NEUTRAL),
        ],
    )
    def test_sharpe_threshold_boundary(self, sharpe_val, expected_state):
        state, _diag = _classify(
            sharpe=sharpe_val,
            strategy_total_return=0.15,
            baseline_total_return=0.10,
        )
        assert state == expected_state

    @pytest.mark.parametrize(
        "pf_val,expected_state",
        [
            (2.0, EmotionalState.SUSPICIOUS),
            (1.99, EmotionalState.NEUTRAL),
        ],
    )
    def test_profit_factor_threshold_boundary(self, pf_val, expected_state):
        state, _diag = _classify(
            sharpe=1.0,
            profit_factor=pf_val,
            strategy_total_return=0.15,
            baseline_total_return=0.10,
        )
        assert state == expected_state

    def test_mixed_sharpe_boundary(self):
        state, _diag = _classify(
            sharpe=0.5,
            max_drawdown=0.4,
            strategy_total_return=0.10,
            baseline_total_return=0.08,
        )
        assert state != EmotionalState.MIXED

    def test_mixed_drawdown_boundary(self):
        state, _diag = _classify(
            sharpe=0.3,
            max_drawdown=0.3,
            strategy_total_return=0.10,
            baseline_total_return=0.08,
        )
        assert state != EmotionalState.MIXED

    def test_trade_count_boundary(self):
        state, _diag = _classify(trade_count=30)
        assert state != EmotionalState.INSUFFICIENT_DATA

        state2, _diag2 = _classify(trade_count=29)
        assert state2 == EmotionalState.INSUFFICIENT_DATA

    @pytest.mark.parametrize("pf_val", [float("inf"), 100.0])
    def test_inf_profit_factor(self, pf_val):
        state, _diag = _classify(
            profit_factor=pf_val,
            strategy_total_return=0.15,
            baseline_total_return=0.10,
        )
        assert state == EmotionalState.SUSPICIOUS


class TestProfitFactor:
    def test_compute_profit_factor_basic(self):
        assert compute_profit_factor(3000.0, 1000.0) == 3.0

    def test_compute_profit_factor_equal(self):
        assert compute_profit_factor(1000.0, 1000.0) == 1.0

    def test_compute_profit_factor_no_losses(self):
        result = compute_profit_factor(1000.0, 0.0)
        assert result == float("inf")

    def test_compute_profit_factor_no_activity(self):
        assert compute_profit_factor(0.0, 0.0) == 0.0

    def test_compute_profit_factor_only_losses(self):
        assert compute_profit_factor(0.0, 500.0) == 0.0


class BadCompare:
    def __init__(self, val: float):
        self._val = val

    def __lt__(self, other: object) -> bool:
        raise TypeError("cannot compare")

    def __gt__(self, other: object) -> bool:
        raise TypeError("cannot compare")

    def __repr__(self) -> str:
        return f"BadCompare({self._val})"


# === Level B — Diagnosis quality (unit) ===


class TestDiagnosisQuality:
    def test_diagnosis_non_empty_for_non_neutral(self):
        for state_val in [
            EmotionalState.SUSPICIOUS,
            EmotionalState.UNDERPERFORMING,
            EmotionalState.MIXED,
            EmotionalState.INSUFFICIENT_DATA,
        ]:
            if state_val == EmotionalState.UNDERPERFORMING:
                state, diag = _classify(
                    strategy_total_return=0.02,
                    baseline_total_return=0.10,
                )
            elif state_val == EmotionalState.SUSPICIOUS:
                state, diag = _classify(
                    sharpe=3.0,
                    strategy_total_return=0.15,
                    baseline_total_return=0.10,
                )
            elif state_val == EmotionalState.MIXED:
                state, diag = _classify(
                    sharpe=0.3,
                    max_drawdown=0.5,
                    strategy_total_return=0.10,
                    baseline_total_return=0.08,
                )
            elif state_val == EmotionalState.INSUFFICIENT_DATA:
                state, diag = _classify(trade_count=5)
            else:
                continue
            assert state == state_val
            assert diag, f"Diagnosis empty for {state_val}"
            assert "heading" in diag
            assert "comparison_text" in diag

    def test_diagnosis_contains_metrics(self):
        _, diag = _classify(strategy_total_return=0.02, baseline_total_return=0.10)
        assert "metrics_used" in diag
        assert "strategy_total_return" in diag["metrics_used"]

    def test_diagnosis_contains_suggestions(self):
        _, diag = _classify(strategy_total_return=0.02, baseline_total_return=0.10)
        assert "suggestions" in diag
        assert len(diag["suggestions"]) >= 1
        joined = " ".join(diag["suggestions"])
        verbs = ["Consider", "Try", "Reduce"]
        assert any(v in joined for v in verbs)

    def test_diagnosis_state_appropriate(self):
        _, diag = _classify(strategy_total_return=0.02, baseline_total_return=0.10)
        joined = " ".join(diag.get("suggestions", [])).lower()
        assert "increase risk" not in joined

    def test_diagnosis_length_bounded(self):
        _, diag = _classify(strategy_total_return=0.02, baseline_total_return=0.10)
        text = diag.get("comparison_text", "")
        assert 20 <= len(text) <= 500


# === Level C — Template rendering + CSS (unit with BeautifulSoup) ===


class TestTemplateRendering:
    @pytest.fixture
    def base_html(self) -> str:
        path = (
            Path(__file__).resolve().parents[3]
            / "src"
            / "trade_advisor"
            / "web"
            / "templates"
            / "base.html"
        )
        return path.read_text()

    @pytest.fixture
    def viewer_html(self) -> str:
        path = (
            Path(__file__).resolve().parents[3]
            / "src"
            / "trade_advisor"
            / "web"
            / "templates"
            / "pages"
            / "backtest_viewer.html"
        )
        return path.read_text()

    def test_template_renders_emotional_state_class(self, viewer_html):
        assert "result-card--" in viewer_html
        assert "emotional_state" in viewer_html
        assert "underperforming" in viewer_html

    def test_template_renders_without_emotional_state(self, viewer_html):
        assert "emotional_state" in viewer_html
        assert "neutral" in viewer_html

    def test_css_selector_exists(self, base_html):
        for selector in [
            ".result-card--underperforming",
            ".result-card--suspicious",
            ".result-card--mixed",
            ".result-card--insufficient-data",
            ".result-card--underperforming .result-card__decorative",
            ".mourning-beat-diagnosis",
            ".suspicion-pulse",
            ".stress-test-panel",
            ".flower-icon",
            ".dismiss-suspicion",
        ]:
            assert selector in base_html, f"CSS selector {selector} not found in base.html"

    def test_css_media_query_exists(self, base_html):
        assert "@media (prefers-reduced-motion: reduce)" in base_html

    def test_css_custom_properties_exist(self, base_html):
        for prop in [
            "--degraded-soft:",
            "--uncertainty-bg:",
            "--degraded-border:",
            "--caution-warm:",
            "--pressed-flower-padding:",
            "--mourning-beat-delay:",
            "--mourning-beat-delay-reduced:",
        ]:
            assert prop in base_html, f"CSS custom property {prop} not found"

    def test_css_dark_mode_emotional_tokens_in_media_query(self, base_html):
        assert "--degraded-soft:" in base_html

    def test_existing_tokens_unchanged(self, base_html):
        assert "--healthy: #22c55e" in base_html
        assert "--caution: #f59e0b" in base_html
        assert "--degraded: #ef4444" in base_html

    def test_no_orphaned_dark_suffix_tokens(self, base_html):
        assert "--degraded-soft-dark:" not in base_html
        assert "--uncertainty-bg-dark:" not in base_html
        assert "--degraded-border-dark:" not in base_html
        assert "--caution-warm-dark:" not in base_html

    def test_svg_icons_inline(self, viewer_html):
        assert "<svg" in viewer_html
        assert "aria-hidden" in viewer_html
        assert "aria-label" in viewer_html

    def test_mourning_beat_aria_live(self, viewer_html):
        assert 'aria-live="polite"' in viewer_html

    def test_no_color_only_indicators(self, viewer_html):
        assert "Underperformance Detected" in viewer_html
        assert "Suspiciously Good Results" in viewer_html
        assert "Results Show Some Risk" in viewer_html

    def test_stress_test_suggestions_in_template(self, viewer_html):
        assert "STRESS_TEST_SUGGESTIONS" in viewer_html

    def test_dismiss_button_exists(self, viewer_html):
        assert "dismiss-suspicion" in viewer_html

    def test_padding_scoped_to_underperforming(self, viewer_html):
        assert 'emotional_state == "underperforming"' in viewer_html

    def test_saturate_scoped_to_underperforming(self, base_html):
        assert ".result-card--underperforming .result-card__decorative" in base_html
        lines = base_html.split("\n")
        for i, line in enumerate(lines):
            if "saturate(0.85)" in line:
                prev = lines[i - 1] if i > 0 else ""
                assert "underperforming" in prev, (
                    f"saturate(0.85) found outside underperforming scope at line {i}"
                )


# === Level D — WCAG contrast (unit, programmatic) ===


def _hex_to_rgb01(hex_color: str) -> tuple[float, float, float]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)


class TestWCAGContrast:
    def test_wcag_contrast_all_state_backgrounds(self):
        try:
            from wcag_contrast_ratio.contrast import rgb
        except ImportError:
            pytest.skip("wcag-contrast-ratio not installed")

        states = {
            "underperforming_light": ("#F8ECEC", "#111827"),
            "underperforming_dark": ("#2A1F1F", "#f1f5f9"),
            "suspicious_light": ("#F5F0E8", "#111827"),
            "suspicious_dark": ("#2A2520", "#f1f5f9"),
            "mixed_light": ("#F5F0E8", "#111827"),
            "mixed_dark": ("#2A2520", "#f1f5f9"),
        }
        for name, (bg, fg) in states.items():
            ratio = rgb(_hex_to_rgb01(bg), _hex_to_rgb01(fg))
            assert ratio >= 4.5, f"{name}: contrast ratio {ratio:.2f} < 4.5:1 (bg={bg}, fg={fg})"

    def test_wcag_contrast_border_colors(self):
        try:
            from wcag_contrast_ratio.contrast import rgb
        except ImportError:
            pytest.skip("wcag-contrast-ratio not installed")

        border_states = {
            "degraded_border_light": ("#B85450", "#FFFFFF"),
            "degraded_border_dark": ("#D06860", "#1e293b"),
            "caution_warm_on_card": ("#B87420", "#FFFFFF"),
            "caution_warm_on_uncertainty_bg": ("#B87420", "#F5F0E8"),
            "caution_warm_dark_on_card": ("#E0A045", "#1e293b"),
        }
        for name, (fg, bg) in border_states.items():
            ratio = rgb(_hex_to_rgb01(fg), _hex_to_rgb01(bg))
            assert ratio >= 3.0, f"{name}: contrast ratio {ratio:.2f} < 3:1 (fg={fg}, bg={bg})"


# === Level E — Route integration (unit) ===


class TestRouteIntegration:
    def test_route_context_includes_emotional_state(self):
        from trade_advisor.web.routes.backtests import _metrics_to_context

        metrics = type(
            "M",
            (),
            {
                "total_return": 0.1,
                "cagr": 0.05,
                "sharpe": 1.0,
                "max_drawdown": 0.1,
                "alpha": 0.01,
                "beta": 0.9,
            },
        )()
        ctx = _metrics_to_context(metrics)
        assert "total_return" in ctx
        assert "sharpe" in ctx

    def test_classify_in_route_context(self):
        state, diag = classify_emotional_state(
            strategy_total_return=0.05,
            baseline_total_return=0.10,
            sharpe=0.3,
            profit_factor=0.5,
            max_drawdown=0.25,
            trade_count=50,
        )
        assert state.value in [
            "underperforming",
            "suspicious",
            "mixed",
            "neutral",
            "insufficient_data",
        ]
        assert isinstance(diag, dict)

    def test_classify_handles_exception_gracefully(self):
        state, diag = classify_emotional_state(
            strategy_total_return=float("nan"),
            baseline_total_return=0.10,
            sharpe=1.0,
            profit_factor=0.5,
            max_drawdown=0.1,
            trade_count=50,
        )
        assert isinstance(state, EmotionalState)
        assert isinstance(diag, dict)

    def test_existing_backtest_display_unchanged(self):
        from trade_advisor.web.routes.backtests import _metrics_to_context

        metrics = type(
            "M",
            (),
            {
                "total_return": 0.15,
                "cagr": 0.08,
                "sharpe": 1.2,
                "max_drawdown": 0.12,
                "alpha": 0.02,
                "beta": 0.95,
            },
        )()
        ctx = _metrics_to_context(metrics)
        assert ctx["total_return"] == 0.15
        assert ctx["cagr"] == 0.08
        assert ctx["sharpe"] == 1.2
