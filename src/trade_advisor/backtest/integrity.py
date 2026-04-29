"""Integrity checks for backtest equity curves.

Detects impossible or suspicious results — negative portfolio values,
single-bar returns exceeding ±100%, NaN gaps, zero-wipeout events,
and statistical anomalies (low trade count, degenerate signals, extreme Sharpe).

Returns an :class:`IntegrityResult` report; never raises on check failure.
The caller decides whether to halt display.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class IntegrityResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    should_halt_display: bool = False


def check_integrity(
    equity: pd.Series,
    *,
    trade_count: int | None = None,
    signal_entropy: float | None = None,
    sharpe: float | None = None,
) -> IntegrityResult:
    errors: list[str] = []
    warnings: list[str] = []

    if equity.empty or len(equity) < 2:
        nan_mask = equity.isna()
        if nan_mask.any():
            nan_idx = equity.index[nan_mask.values].tolist()
            errors.append(f"Equity curve contains NaN gaps at bar(s) {nan_idx}")
        return IntegrityResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=[],
            should_halt_display=len(errors) > 0,
        )

    neg_mask = equity < 0
    if neg_mask.any():
        neg_idx = equity.index[neg_mask.values].tolist()
        errors.append(f"Negative portfolio value detected at bar(s) {neg_idx}")

    returns = equity.pct_change(fill_method=None).dropna()
    if len(returns) > 0:
        abs_ret = returns.abs()
        spike_mask = abs_ret > 1.0
        if spike_mask.any():
            spike_idx = returns.index[spike_mask.values].tolist()
            errors.append(f"Single-bar return exceeds ±100% at bar(s) {spike_idx}")

    nan_mask = equity.isna()
    if nan_mask.any():
        nan_idx = equity.index[nan_mask.values].tolist()
        errors.append(f"Equity curve contains NaN gaps at bar(s) {nan_idx}")

    zero_mask = equity == 0
    if zero_mask.any():
        zero_idx = equity.index[zero_mask.values].tolist()
        warnings.append(
            f"Total wipeout detected at bar(s) {zero_idx} — portfolio value reached zero"
        )

    if len(returns) > 0:
        max_abs = float(returns.abs().max())
        if max_abs > 0.5 and not (returns.abs() > 1.0).any():
            warnings.append(f"Large single-bar move detected ({max_abs:.1%}) — verify data quality")

    if trade_count is not None and trade_count < 30:
        warnings.append(
            f"Insufficient trade count ({trade_count}) — results lack statistical significance (minimum 30)"
        )

    if signal_entropy is not None and signal_entropy < 0.5:
        warnings.append(
            "Signal appears degenerate (low entropy) — strategy may be leveraged buy-and-hold"
        )

    if sharpe is not None and sharpe > 4.0:
        warnings.append(
            f"Sharpe ratio ({sharpe:.1f}) exceeds plausible bounds — verify no lookahead bias"
        )

    is_valid = len(errors) == 0
    should_halt = len(errors) > 0

    return IntegrityResult(
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
        should_halt_display=should_halt,
    )
