"""FastAPI app: API under /api, built React app served from backend/static/."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from backend.api import courses, jobs, lectures, maps, ollama, settings
from backend.core.context import AppContext
from backend.core.courses import NotFound
from backend.core.paths import PathError
from backend.core.settings import SettingsStore
from backend.core.storage import MigrationError
from backend.llm.base import LLMError, LLMProvider

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(
    settings_store: SettingsStore | None = None,
    provider: LLMProvider | None = None,
    static_dir: Path | None = None,
) -> FastAPI:
    ctx = AppContext(settings_store or SettingsStore(), provider=provider)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        ctx.jobs.shutdown()

    app = FastAPI(
        title="Nodebook", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan
    )
    app.state.ctx = ctx

    @app.exception_handler(NotFound)
    async def _nf(_: Request, exc: NotFound) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.exception_handler(PathError)
    async def _pe(_: Request, exc: PathError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(LLMError)
    async def _le(_: Request, exc: LLMError) -> JSONResponse:
        return JSONResponse({"detail": str(exc), "kind": "llm"}, status_code=502)

    @app.exception_handler(MigrationError)
    async def _me(_: Request, exc: MigrationError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=500)

    api = APIRouter(prefix="/api")

    @api.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    for r in (courses.router, lectures.router, maps.router, settings.router, jobs.router, ollama.router):
        api.include_router(r)
    app.include_router(api)

    sdir = static_dir or STATIC_DIR
    if (sdir / "index.html").exists():
        if (sdir / "assets").is_dir():
            app.mount("/assets", StaticFiles(directory=sdir / "assets"), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str) -> Response:
            if full_path.startswith("api/"):
                return JSONResponse({"detail": "not found"}, status_code=404)
            candidate = (sdir / full_path).resolve()
            if full_path and sdir.resolve() in candidate.parents and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(sdir / "index.html")

    return app
