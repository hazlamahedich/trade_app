from __future__ import annotations

from trade_advisor.web.events import TAEventMap


class TestTAEventMap:
    def test_events_populated(self):
        em = TAEventMap()
        assert len(em.events) > 0

    def test_strategy_forked_exists(self):
        em = TAEventMap()
        assert "ta:strategy:forked" in em.events

    def test_has_event(self):
        em = TAEventMap()
        assert em.has_event("ta:data:fetched")
        assert not em.has_event("ta:nonexistent:action")

    def test_get_event(self):
        em = TAEventMap()
        event = em.get_event("ta:data:fetched")
        assert event is not None
        assert "payload" in event

    def test_get_event_returns_none_for_unknown(self):
        em = TAEventMap()
        assert em.get_event("ta:unknown:event") is None

    def test_register_event(self):
        em = TAEventMap()
        em.register_event("ta:custom:new_action", "CustomPayload")
        assert em.has_event("ta:custom:new_action")
        assert em.get_event("ta:custom:new_action")["payload"] == "CustomPayload"
