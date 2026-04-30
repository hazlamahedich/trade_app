"""ResultCard emotional states for backtest result visualization.

Implements UX-DR5 (Pressed Flower), UX-DR6 (Mourning Beat), UX-DR7 (Productive Suspicion),
and an ambiguous state for mixed results.
"""

from __future__ import annotations

MOURNING_BEAT_MS: int = 800
MOURNING_BEAT_REDUCED_MS: int = 200

EMOTIONAL_COLORS: dict[str, dict[str, str]] = {
    "pressed_flower": {
        "bg": "#f5f0eb",
        "fg": "#4a4a4a",
        "border": "#b8a9a0",
        "icon": "flower-2",
    },
    "productive_suspicion": {
        "bg": "#fef9f0",
        "fg": "#5c4a1a",
        "border": "#e6c84a",
        "icon": "alert-triangle",
    },
    "ambiguous": {
        "bg": "#faf8f5",
        "fg": "#6b6b6b",
        "border": "#d4c9b8",
        "icon": "help-circle",
    },
    "neutral": {
        "bg": "#ffffff",
        "fg": "#1a1a1a",
        "border": "#e0e0e0",
        "icon": "bar-chart-2",
    },
}


def emotional_state(
    sharpe: float = 0.0,
    win_rate: float = 0.0,
    baseline_sharpe: float | None = None,
    max_drawdown_pct: float = 0.0,
) -> str:
    """Determine the emotional state for a backtest result card.

    Parameters
    ----------
    sharpe : float
        Strategy Sharpe ratio.
    win_rate : float
        Strategy win rate (0.0 to 1.0).
    baseline_sharpe : float | None
        Buy-and-hold baseline Sharpe ratio for comparison.
    max_drawdown_pct : float
        Maximum drawdown percentage.

    Returns
    -------
    str
        One of: ``"productive_suspicion"``, ``"pressed_flower"``,
        ``"ambiguous"``, or ``"neutral"``.
    """
    if sharpe > 2.0 or win_rate > 0.65:
        return "productive_suspicion"

    if baseline_sharpe is not None and sharpe < baseline_sharpe - 0.3:
        return "pressed_flower"

    if sharpe < 0.0 or max_drawdown_pct > 40.0:
        return "pressed_flower"

    if abs(sharpe) < 1.0 and 0.35 <= win_rate <= 0.55:
        return "ambiguous"

    return "neutral"
