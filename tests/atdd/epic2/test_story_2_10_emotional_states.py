"""ATDD red-phase: Story 2.10 — ResultCard Emotional States.

Tests assert the expected end-state AFTER full Story 2.10 implementation.
All tests are SKIPPED (TDD red phase).

Remove @pytest.mark.skip when implementing Story 2.10.
"""

from __future__ import annotations

import pytest


class TestStory210ResultCardEmotionalStates:
    """Story 2.10: Backtest results communicate honestly through visual design."""

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.10 not yet implemented")
    def test_pressed_flower_pattern_css_vars_exist(self):
        from pathlib import Path

        static = Path(__file__).resolve().parents[3] / "src" / "trade_advisor" / "web" / "static"
        css_files = list(static.rglob("*.css"))
        all_css = " ".join(f.read_text() for f in css_files) if css_files else ""
        assert "degraded-soft" in all_css or "pressed" in all_css.lower()

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.10 not yet implemented")
    def test_productive_suspicion_triggered_for_high_sharpe(self):
        from trade_advisor.web.components.result_card import emotional_state

        state = emotional_state(sharpe=2.5, win_rate=0.70)
        assert state == "productive_suspicion"

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.10 not yet implemented")
    def test_pressed_flower_triggered_for_underperformance(self):
        from trade_advisor.web.components.result_card import emotional_state

        state = emotional_state(sharpe=-0.5, win_rate=0.30, baseline_sharpe=0.5)
        assert state == "pressed_flower"

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.10 not yet implemented")
    def test_mourning_beat_800ms_delay(self):
        from trade_advisor.web.components.result_card import MOURNING_BEAT_MS

        assert MOURNING_BEAT_MS == 800

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.10 not yet implemented")
    def test_mourning_beat_reduced_motion_200ms(self):
        from trade_advisor.web.components.result_card import MOURNING_BEAT_REDUCED_MS

        assert MOURNING_BEAT_REDUCED_MS == 200

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.10 not yet implemented")
    def test_all_states_meet_wcag_aa_contrast(self):
        from trade_advisor.web.components.result_card import EMOTIONAL_COLORS

        for _state_name, colors in EMOTIONAL_COLORS.items():
            assert "bg" in colors
            assert "fg" in colors

    @pytest.mark.skip(reason="ATDD red-phase: Story 2.10 not yet implemented")
    def test_ambiguous_state_exists(self):
        from trade_advisor.web.components.result_card import emotional_state

        state = emotional_state(sharpe=0.8, win_rate=0.50)
        assert state == "ambiguous"
