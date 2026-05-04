from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from trade_advisor.core.config import DatabaseConfig
from trade_advisor.infra.db import DatabaseManager
from trade_advisor.main import app

@pytest_asyncio.fixture
async def db_with_wf_run():
    config = DatabaseConfig(path=':memory:')
    db = DatabaseManager(config)
    now = datetime.now(UTC)

    async with db:
        # Correct schema according to migrate.py ExperimentAdditiveColumns:
        # results_json is NOT in experiments table.
        # trade_analysis_json is present and likely stores the result payload.
        await db.write(
            'INSERT INTO experiments (run_id, config_hash, strategy, metrics_json, seed, status, created_at, completed_at, config_json, trade_analysis_json) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (
                'run_api_001',
                'hash_api_001',
                'SmaCross',
                json.dumps({'wfe': 0.85, 'wfe_status': 'healthy'}),
                42,
                'completed',
                now,
                now,
                json.dumps({'mode': 'rolling', 'is_bars': 60, 'oos_bars': 20}),
                json.dumps({
                    'stitched_equity': [{'time': '2020-01-01', 'value': 100.0}],
                    'baseline_equity': [{'time': '2020-01-01', 'value': 100.0}],
                    'windows': [
                        {
                            'is_start': '2020-01-01', 'is_end': '2020-03-01',
                            'oos_start': '2020-03-02', 'oos_end': '2020-04-01',
                            'is_sharpe': 1.5, 'oos_sharpe': 1.2,
                            'is_return': 0.1, 'oos_return': 0.08,
                            'params': {'fast': 20, 'slow': 50}
                        }
                    ]
                })
            ),
        )
        yield db

@pytest_asyncio.fixture
async def wf_app_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_get_wf_results_success(wf_app_client, db_with_wf_run, monkeypatch):
    # Mock the get_db function used by the app
    async def mock_get_db(request):
        return db_with_wf_run
    
    monkeypatch.setattr("trade_advisor.main.get_db", mock_get_db)
    
    response = await wf_app_client.get("/api/walkforward/run_api_001")
    assert response.status_code == 200
    data = response.json()
    assert data["wfe"] == 0.85
    assert data["wfe_status"] == "healthy"
    assert len(data["windows"]) == 1

@pytest.mark.asyncio
async def test_get_wf_results_not_found(wf_app_client, db_with_wf_run, monkeypatch):
    async def mock_get_db(request):
        return db_with_wf_run
        
    monkeypatch.setattr("trade_advisor.main.get_db", mock_get_db)
    
    response = await wf_app_client.get("/api/walkforward/nonexistent")
    assert response.status_code == 404
