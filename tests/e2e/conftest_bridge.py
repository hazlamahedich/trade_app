from __future__ import annotations

import contextlib
import socket
import threading
import time
from urllib.request import urlopen

import pytest
import uvicorn

from trade_advisor.main import app


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_server(url: str, timeout: int = 10) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with contextlib.closing(urlopen(url, timeout=2)) as resp:
                _ = resp.read(1)
            return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError(f"Server not reachable at {url} after {timeout}s")


@pytest.fixture(scope="session")
def fastapi_server():
    port = _find_free_port()
    url = f"http://127.0.0.1:{port}"
    server = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    thread = threading.Thread(target=uvicorn.Server(server).run, daemon=True)
    thread.start()
    _wait_for_server(url)
    yield url
