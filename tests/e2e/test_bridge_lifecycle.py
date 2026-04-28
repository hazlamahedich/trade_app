from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


def _wait_for_island_stable(page, timeout_ms: int = 3000, interval_ms: int = 200) -> None:
    import time

    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        statuses = page.evaluate(
            "() => Array.from(document.querySelectorAll('[data-preact-mount]')).map(el => el.getAttribute('data-island-status'))"
        )
        if statuses and all(s in ("hydrated", "error") for s in statuses):
            return
        time.sleep(interval_ms / 1000)


@pytest.fixture
def page_with_server(browser, fastapi_server):
    page = browser.new_page()
    page.goto(fastapi_server + "/data", wait_until="networkidle")
    _wait_for_island_stable(page)
    yield page, fastapi_server
    page.close()


class TestBridgeLifecycle:
    def test_hydration_signal_appears(self, page_with_server):
        page, _ = page_with_server
        islands = page.query_selector_all("[data-preact-mount]")
        for island in islands:
            status = island.get_attribute("data-island-status")
            assert status in ("pending", "hydrated"), (
                f"Island should have status pending or hydrated, got: {status}"
            )

    def test_no_console_errors_on_load(self, page_with_server):
        page, server = page_with_server
        errors = []
        page.on("console", lambda msg: errors.append(msg) if msg.type == "error" else None)
        page.goto(server + "/data", wait_until="networkidle")
        _wait_for_island_stable(page)
        severe = [e for e in errors if "bridge" in e.text.lower()]
        assert len(severe) == 0, f"Bridge-related console errors: {[e.text for e in severe]}"

    def test_navigate_away_and_back_no_errors(self, page_with_server):
        page, server = page_with_server
        errors = []
        page.on("console", lambda msg: errors.append(msg) if msg.type == "error" else None)

        page.goto(server + "/data", wait_until="networkidle")
        _wait_for_island_stable(page)
        page.goto("about:blank")
        page.wait_for_timeout(100)
        errors.clear()
        page.goto(server + "/data", wait_until="networkidle")
        _wait_for_island_stable(page)
        severe = [e for e in errors if "bridge" in e.text.lower()]
        assert len(severe) == 0, f"Errors after navigation: {[e.text for e in severe]}"

    def test_mount_unmount_cycles_no_leak(self, page_with_server):
        page, server = page_with_server
        page.goto(server + "/data", wait_until="networkidle")
        _wait_for_island_stable(page)

        initial_count = page.evaluate(
            "() => document.querySelectorAll('[data-preact-mount]').length"
        )

        for _ in range(10):
            page.goto("about:blank")
            page.wait_for_timeout(50)
            page.goto(server + "/data", wait_until="networkidle")
            _wait_for_island_stable(page)

        final_count = page.evaluate("() => document.querySelectorAll('[data-preact-mount]').length")
        assert final_count == initial_count, (
            f"DOM leak: {final_count} islands vs initial {initial_count}"
        )
