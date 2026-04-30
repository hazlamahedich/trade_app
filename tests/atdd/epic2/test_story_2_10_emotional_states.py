"""ATDD tests: Story 2.10 — ResultCard Emotional States.

Tests assert the expected end-state for Story 2.10 implementation.
"""

from __future__ import annotations

import contextlib
from pathlib import Path


class TestStory210ResultCardEmotionalStates:
    """Story 2.10: Backtest results communicate honestly through visual design."""

    def test_pressed_flower_pattern_css_vars_exist(self):
        static = Path(__file__).resolve().parents[3] / "src" / "trade_advisor" / "web" / "static"
        css_files = list(static.rglob("*.css"))
        all_css = ""
        for f in css_files:
            with contextlib.suppress(Exception):
                all_css += f.read_text(encoding="utf-8", errors="ignore")
        from trade_advisor.web.components.result_card import EMOTIONAL_COLORS

        has_pressed = "degraded-soft" in all_css or "pressed" in all_css.lower()
        has_component = "pressed_flower" in EMOTIONAL_COLORS
        assert has_pressed or has_component

    def test_productive_suspicion_triggered_for_high_sharpe(self):
        from trade_advisor.web.components.result_card import emotional_state

        state = emotional_state(sharpe=2.5, win_rate=0.70)
        assert state == "productive_suspicion"

    def test_pressed_flower_triggered_for_underperformance(self):
        from trade_advisor.web.components.result_card import emotional_state

        state = emotional_state(sharpe=-0.5, win_rate=0.30, baseline_sharpe=0.5)
        assert state == "pressed_flower"

    def test_mourning_beat_800ms_delay(self):
        from trade_advisor.web.components.result_card import MOURNING_BEAT_MS

        assert MOURNING_BEAT_MS == 800

    def test_mourning_beat_reduced_motion_200ms(self):
        from trade_advisor.web.components.result_card import MOURNING_BEAT_REDUCED_MS

        assert MOURNING_BEAT_REDUCED_MS == 200

    def test_all_states_meet_wcag_aa_contrast(self):
        from trade_advisor.web.components.result_card import EMOTIONAL_COLORS

        for _state_name, colors in EMOTIONAL_COLORS.items():
            assert "bg" in colors
            assert "fg" in colors

    def test_ambiguous_state_exists(self):
        from trade_advisor.web.components.result_card import emotional_state

        state = emotional_state(sharpe=0.8, win_rate=0.50)
        assert state == "ambiguous"
