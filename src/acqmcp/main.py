from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from starlette.types import ASGIApp, Receive, Scope, Send

from acqmcp.alma_client import AlmaAcquisitionsClient
from acqmcp.mcp_server import build_mcp_server
from acqmcp.openapi_catalog import AcqOpenAPICatalog
from acqmcp.settings import Settings


class PathPrefixMiddleware:
    def __init__(self, app: ASGIApp, prefix: str) -> None:
        self.app = app
        self.prefix = prefix.rstrip("/")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and self.prefix:
            path = scope.get("path", "")
            if path == self.prefix:
                scope = {**scope, "root_path": self.prefix, "path": "/"}
            elif path.startswith(f"{self.prefix}/"):
                scope = {
                    **scope,
                    "root_path": self.prefix,
                    "path": path[len(self.prefix) :] or "/",
                }
        await self.app(scope, receive, send)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    catalog = AcqOpenAPICatalog.from_file(settings.acq_openapi_path)
    alma_client = AlmaAcquisitionsClient(
        base_url=settings.base_url,
        api_key=settings.acq_api_key,
        catalog=catalog,
        timeout=settings.request_timeout_seconds,
    )
    mcp = build_mcp_server(settings=settings, catalog=catalog, alma_client=alma_client)
    mcp_app = mcp.streamable_http_app()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        async with mcp.session_manager.run():
            yield

    app = FastAPI(
        title="Ex Libris Acquisitions MCP",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    if settings.public_path_prefix:
        app.add_middleware(PathPrefixMiddleware, prefix=settings.public_path_prefix)

    @app.get("/livez", include_in_schema=False)
    async def livez() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str | int]:
        return {
            "status": "ok",
            "operation_count": len(catalog.operations),
        }

    app.mount("/", mcp_app)
    return app


app = create_app()


def run() -> None:
    settings = Settings()
    uvicorn.run(
        "acqmcp.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        proxy_headers=True,
    )
