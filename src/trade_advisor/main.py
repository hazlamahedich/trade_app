from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader, pass_context

from trade_advisor.core.config import DatabaseConfig
from trade_advisor.infra.db import DatabaseManager
from trade_advisor.web.csrf import CSRFMiddleware


@pass_context
def _csrf_token(context: dict[str, Any]) -> str:
    request: Any = context.get("request")
    if request is not None:
        token: Any = getattr(request.state, "_csrf_token", None)
        if token is not None:
            return str(token)
        cookie_val: Any = request.cookies.get("csrf_token", "")
        return str(cookie_val)
    return ""


def _web_dir() -> Path:
    return Path(__file__).resolve().parent / "web"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    config = DatabaseConfig()
    db = DatabaseManager(config)
    async with db:
        app.state.db = db
        yield


app = FastAPI(title="Quant Trade Advisor", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CSRFMiddleware,
    secret_key="ta-dev-csrf-secret-change-in-production",
    cookie_secure=False,
    cookie_samesite="Lax",
)

_templates_dir = _web_dir() / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_templates_dir)),
    autoescape=True,
    cache_size=0,
)
_env.globals["csrf_token"] = _csrf_token
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

app.include_router(strategies_router)

from trade_advisor.web.routes.backtests import router as backtests_router  # noqa: E402

app.include_router(backtests_router)

from trade_advisor.web.routes.experiments import api_router as experiments_api_router  # noqa: E402
from trade_advisor.web.routes.experiments import router as experiments_router  # noqa: E402

app.include_router(experiments_router)
app.include_router(experiments_api_router)

from trade_advisor.web.routes.walkforward import router as walkforward_router  # noqa: E402

app.include_router(walkforward_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
