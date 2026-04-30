from __future__ import annotations

import logging
import time
from collections.abc import Callable

from pydantic import BaseModel

log = logging.getLogger(__name__)

MAX_VARIANTS: int = 6
UNDO_WINDOW_SEC: int = 10

_remix_registry: dict[str, tuple[str, float]] = {}

_EXCLUDED_PARAM_KEYS = frozenset({
    "fast", "slow", "source_run_id",
    "strategy_type", "symbol", "interval",
    "start_date", "end_date", "engine_mode",
    "commission_pct", "slippage_pct", "initial_cash",
})


class VariantSuggestion(BaseModel):
    label: str
    hint: str
    params: dict[str, object]


def _validate_sma_params(fast: int, slow: int) -> bool:
    return fast >= 1 and slow >= 2 and fast < slow


def _sma_variants(config_dict: dict[str, object]) -> list[VariantSuggestion]:
    _fast = config_dict.get("fast", 20)
    _slow = config_dict.get("slow", 50)
    if not isinstance(_fast, (int, float)):
        raise TypeError(f"Expected numeric fast, got {type(_fast).__name__}")
    if not isinstance(_slow, (int, float)):
        raise TypeError(f"Expected numeric slow, got {type(_slow).__name__}")
    fast = int(_fast)
    slow = int(_slow)
    if not _validate_sma_params(fast, slow):
        return []
    base = {
        k: v for k, v in config_dict.items()
        if k not in _EXCLUDED_PARAM_KEYS and isinstance(v, (str, int, float)) and not isinstance(v, bool)
    }
    results: list[VariantSuggestion] = []

    widen_fast = fast + 5
    widen_slow = slow + 5
    if _validate_sma_params(widen_fast, widen_slow):
        results.append(
            VariantSuggestion(
                label=f"fast={widen_fast} slow={widen_slow}",
                hint="fewer signals, longer holds",
                params={**base, "fast": widen_fast, "slow": widen_slow},
            )
        )

    if fast > 6:
        narrow_fast = fast - 5
        narrow_slow = slow - 5
        if _validate_sma_params(narrow_fast, narrow_slow):
            results.append(
                VariantSuggestion(
                    label=f"fast={narrow_fast} slow={narrow_slow}",
                    hint="more signals, higher turnover",
                    params={**base, "fast": narrow_fast, "slow": narrow_slow},
                )
            )

    if slow < 150:
        golden_fast = 50
        golden_slow = 200
        if _validate_sma_params(golden_fast, golden_slow):
            results.append(
                VariantSuggestion(
                    label=f"fast={golden_fast} slow={golden_slow}",
                    hint="long-term trend following",
                    params={**base, "fast": golden_fast, "slow": golden_slow},
                )
            )

    return results


_VARIANT_DISPATCH: dict[str, Callable[[dict[str, object]], list[VariantSuggestion]]] = {
    "sma": _sma_variants,
}


def generate_variants(config_dict: dict[str, object], strategy_type: str = "sma") -> list[VariantSuggestion]:
    try:
        generator = _VARIANT_DISPATCH.get(strategy_type)
        if generator is None:
            return []
        variants = generator(config_dict)
        return variants[:MAX_VARIANTS]
    except Exception:
        log.warning("Variant generation failed", exc_info=True)
        return []


def register_remix(child_run_id: str, parent_run_id: str) -> None:
    _remix_registry[child_run_id] = (parent_run_id, time.monotonic())


def can_undo(child_run_id: str) -> bool:
    if child_run_id not in _remix_registry:
        return False
    _, created_at = _remix_registry[child_run_id]
    return (time.monotonic() - created_at) <= UNDO_WINDOW_SEC


def undo_remix(child_run_id: str) -> str | None:
    entry = _remix_registry.pop(child_run_id, None)
    if entry is None:
        return None
    parent_run_id, created_at = entry
    if (time.monotonic() - created_at) > UNDO_WINDOW_SEC:
        return None
    return parent_run_id
