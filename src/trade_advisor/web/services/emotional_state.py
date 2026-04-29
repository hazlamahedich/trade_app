"""Server-side emotional state classification for backtest results."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class EmotionalState(StrEnum):
    UNDERPERFORMING = "underperforming"
    SUSPICIOUS = "suspicious"
    MIXED = "mixed"
    NEUTRAL = "neutral"
    INSUFFICIENT_DATA = "insufficient_data"


class ClassificationThresholds(BaseModel):
    suspicion_sharpe: float = Field(default=2.0, gt=0)
    suspicion_profit_factor: float = Field(default=2.0, gt=0)
    mixed_sharpe_floor: float = Field(default=0.5, ge=0)
    mixed_drawdown_ceiling: float = Field(default=0.3, gt=0, le=1)
    min_trade_count: int = Field(default=30, ge=1)


DEFAULT_THRESHOLDS = ClassificationThresholds()

STRESS_TEST_SUGGESTIONS = [
    "Double transaction costs — does the edge survive?",
    "Exclude the best month — is alpha concentrated?",
    "Try on a different symbol — does the signal generalize?",
]


def compute_profit_factor(gross_wins: float, gross_losses: float) -> float:
    if gross_losses <= 0.0:
        return 0.0 if gross_wins <= 0.0 else float("inf")
    return gross_wins / gross_losses


def _insufficient_data_diagnosis(trade_count: int) -> dict:
    return {
        "heading": "Insufficient data",
        "comparison_text": (
            f"Insufficient trade count ({trade_count}) for reliable"
            " classification — results may be statistical noise."
        ),
        "suggestions": [
            "Run with a longer date range to generate more trades",
            "Try a faster signal period to increase trade frequency",
        ],
        "metrics_used": {"trade_count": trade_count},
    }


def _underperforming_diagnosis(
    strategy_return: float,
    baseline_return: float,
    strategy_sharpe: float,
    baseline_sharpe: float,
    max_drawdown: float,
) -> dict:
    delta_pct = (strategy_return - baseline_return) * 100
    return {
        "heading": "Why this underperformed",
        "comparison_text": (
            f"Strategy returned {strategy_return * 100:.2f}% vs buy-and-hold "
            f"{baseline_return * 100:.2f}% (Sharpe: {strategy_sharpe:.2f} vs "
            f"{baseline_sharpe:.2f}, Max DD: {max_drawdown * 100:.1f}%)"
        ),
        "suggestions": [
            "Consider reducing position size to limit drawdown exposure",
            "Try widening the signal period for fewer but higher-quality trades",
        ],
        "metrics_used": {
            "strategy_total_return": strategy_return,
            "baseline_total_return": baseline_return,
            "strategy_sharpe": strategy_sharpe,
            "baseline_sharpe": baseline_sharpe,
            "max_drawdown": max_drawdown,
            "delta_pct": delta_pct,
        },
    }


def _suspicious_diagnosis(
    sharpe: float,
    profit_factor: float,
) -> dict:
    pf_display = profit_factor if profit_factor != float("inf") else 999.0
    return {
        "heading": "These results look unusually good",
        "comparison_text": (
            f"Sharpe ratio ({sharpe:.2f}) or profit factor ({pf_display:.1f}) "
            "exceeds typical thresholds. Verify these results hold under stress."
        ),
        "suggestions": STRESS_TEST_SUGGESTIONS,
        "metrics_used": {
            "sharpe": sharpe,
            "profit_factor": profit_factor,
        },
    }


def _mixed_diagnosis(sharpe: float, max_drawdown: float) -> dict:
    return {
        "heading": "Results show some risk",
        "comparison_text": (
            f"Sharpe ratio is low ({sharpe:.2f}) and max drawdown is high "
            f"({max_drawdown * 100:.1f}%) — consider comparing against"
            " different parameters."
        ),
        "suggestions": [
            "Try adjusting signal periods to improve risk-adjusted returns",
            "Reduce position sizing to manage drawdown exposure",
        ],
        "metrics_used": {
            "sharpe": sharpe,
            "max_drawdown": max_drawdown,
        },
    }


def classify_emotional_state(
    strategy_total_return: float | None,
    baseline_total_return: float | None,
    sharpe: float | None,
    profit_factor: float | None,
    max_drawdown: float | None,
    trade_count: int = 0,
    baseline_sharpe: float | None = None,
    thresholds: ClassificationThresholds = DEFAULT_THRESHOLDS,
) -> tuple[EmotionalState, dict]:
    try:
        if trade_count < thresholds.min_trade_count:
            return (
                EmotionalState.INSUFFICIENT_DATA,
                _insufficient_data_diagnosis(trade_count),
            )

        strat_ret = strategy_total_return if strategy_total_return is not None else 0.0
        base_ret = baseline_total_return if baseline_total_return is not None else 0.0
        s = sharpe if sharpe is not None else 0.0
        dd = max_drawdown if max_drawdown is not None else 0.0
        b_sharpe = baseline_sharpe if baseline_sharpe is not None else 0.0
        pf = profit_factor if profit_factor is not None else 0.0

        if s >= thresholds.suspicion_sharpe or pf >= thresholds.suspicion_profit_factor:
            return EmotionalState.SUSPICIOUS, _suspicious_diagnosis(s, pf)

        if strat_ret < base_ret:
            return EmotionalState.UNDERPERFORMING, _underperforming_diagnosis(
                strat_ret, base_ret, s, b_sharpe, dd
            )

        if s < thresholds.mixed_sharpe_floor and dd > thresholds.mixed_drawdown_ceiling:
            return EmotionalState.MIXED, _mixed_diagnosis(s, dd)

        return EmotionalState.NEUTRAL, {}
    except (TypeError, ValueError, AttributeError):
        return EmotionalState.NEUTRAL, {}
