from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader

from trade_advisor.core.config import DatabaseConfig
from trade_advisor.infra.db import DatabaseManager


def _web_dir() -> Path:
    return Path(__file__).resolve().parent / "web"


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = DatabaseConfig()
    db = DatabaseManager(config)
    async with db:
        app.state.db = db
        yield


app = FastAPI(title="Quant Trade Advisor", version="0.1.0", lifespan=lifespan)

_templates_dir = _web_dir() / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_templates_dir)),
    autoescape=True,
    cache_size=0,
)
_templates = Jinja2Templates(env=_env)

_static_dir = _web_dir() / "static"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


async def get_db(request: Request) -> DatabaseManager:
    db: DatabaseManager | None = getattr(request.app.state, "db", None)
    if db is None:
        raise RuntimeError("Database not initialized — is the application lifespan configured?")
    return db


def get_templates() -> Jinja2Templates:
    return _templates


from trade_advisor.web.routes.data import router as data_router  # noqa: E402

app.include_router(data_router)  # type: ignore[has-type]

from trade_advisor.web.routes.strategies import router as strategies_router  # noqa: E402

app.include_router(strategies_router)  # type: ignore[has-type]

from trade_advisor.web.routes.backtests import router as backtests_router  # noqa: E402

app.include_router(backtests_router)  # type: ignore[has-type]


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
