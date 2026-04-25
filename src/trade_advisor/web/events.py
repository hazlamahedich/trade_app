from __future__ import annotations

from typing import Any


class TAEventMap:
    def __init__(self) -> None:
        self.events: dict[str, dict[str, Any]] = {
            "ta:data:fetched": {"payload": "DataFetchedPayload"},
            "ta:data:validated": {"payload": "DataValidatedPayload"},
            "ta:strategy:forked": {"payload": "StrategyForkedPayload"},
            "ta:strategy:run_started": {"payload": "RunStartedPayload"},
            "ta:strategy:run_completed": {"payload": "RunCompletedPayload"},
            "ta:backtest:progress": {"payload": "BacktestProgressPayload"},
            "ta:backtest:completed": {"payload": "BacktestCompletedPayload"},
            "ta:experiment:created": {"payload": "ExperimentCreatedPayload"},
        }

    def has_event(self, event_type: str) -> bool:
        return event_type in self.events

    def get_event(self, event_type: str) -> dict[str, Any] | None:
        return self.events.get(event_type)

    def register_event(self, event_type: str, payload_type: str) -> None:
        self.events[event_type] = {"payload": payload_type}
