from __future__ import annotations

import subprocess


def test_imports() -> None:
    for mod in [
        "pandas",
        "numpy",
        "pydantic",
        "yaml",
        "fastapi",
        "structlog",
    ]:
        __import__(mod)


def test_cli_help() -> None:
    result = subprocess.run(["ta", "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "fetch" in result.stdout
    assert "backtest" in result.stdout
    assert "dashboard" in result.stdout


def test_conftest_fixture(synthetic_ohlcv):  # type: ignore[no-untyped-def]
    assert len(synthetic_ohlcv) == 500
    assert {"open", "high", "low", "close", "volume"}.issubset(
        set(synthetic_ohlcv.columns.str.lower())
    )


def test_fastapi_health() -> None:
    from fastapi.testclient import TestClient

    from trade_advisor.api import app

    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
