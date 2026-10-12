"""Entrée locale : uvicorn services.api_gateway.app.main:app --host 127.0.0.1."""

import os
import sqlite3
import threading
from contextlib import asynccontextmanager
from services.stock_service.app.services.collection.worker import serve
from services.stock_service.app.api.routes.actions import router as actions_router
from services.stock_service.app.api.routes.collection import router as collection_router
from urllib.parse import urlsplit
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware
from libs.common.database import ROOT, default_path, initialize
from services.api_gateway.app.api.routes.maintenance import router as maintenance_router
from services.auth_service.app.api.routes.auth import router as auth_router
from services.auth_service.app.api.routes.users import router as users_router
from services.auth_service.app.api.routes.mobile import router as mobile_router
from services.stock_service.app.api.routes.products import router as products_router
from services.stock_service.app.api.routes.stock import router as movements_router
from services.stock_service.app.api.routes.imports import router as imports_router
from services.stock_service.app.api.routes.inventories import (
    router as inventories_router,
)
from services.stock_service.app.api.routes.replenishment import (
    router as replenishment_router,
)
from services.stock_service.app.api.routes.insights import router as insights_router
from services.stock_service.app.api.routes.purchases import router as purchases_router
from services.stock_service.app.api.routes.commerce import router as commerce_router
from services.stock_service.app.api.routes.opportunities import (
    router as opportunities_router,
)
from services.stock_service.app.api.routes.crm import router as crm_router
from services.stock_service.app.api.routes.market import router as market_router
from services.stock_service.app.api.routes.analysis import router as analysis_router
from services.alerts_service.app.api.routes.alerts import router as alerts_router
from services.api_gateway.app.api.routes.recommendations import (
    router as recommendations_router,
)


def origin_tuple(value):
    parsed = urlsplit(value)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        return None
    return (
        parsed.scheme,
        parsed.hostname,
        parsed.port or (443 if parsed.scheme == "https" else 80),
    )


def create_app(db_path=None):
    dev = os.getenv("SMART_STOCK_DEV") == "1"

    @asynccontextmanager
    async def lifespan(app):
        stop = threading.Event()
        worker = None
        if os.getenv("SMART_STOCK_COLLECTION", "1") == "1":
            worker = threading.Thread(
                target=serve,
                args=(app.state.db_path, stop),
                daemon=True,
                name="public-price-monitor",
            )
            app.state.collection_thread = worker
            worker.start()
        yield
        stop.set()
        if worker:
            worker.join(timeout=15)

    app = FastAPI(
        lifespan=lifespan,
        title="Smart Stock Management & Pricing",
        docs_url="/design/api" if dev else None,
        redoc_url=None,
        openapi_url="/design/openapi.json" if dev else None,
    )
    app.state.db_path = str(db_path or default_path())
    initialize(app.state.db_path)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )

    @app.middleware("http")
    async def protection(request: Request, call_next):
        if request.url.path.startswith("/api") and request.method in (
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
        ):
            origin = request.headers.get("origin")
            if origin:
                try:
                    valid = (
                        origin_tuple(origin) == origin_tuple(str(request.base_url))
                        and origin_tuple(origin) is not None
                    )
                except ValueError:
                    valid = False
                if not valid:
                    return JSONResponse(
                        {"detail": "Origine de requête non autorisée."}, status_code=403
                    )
            elif request.headers.get("sec-fetch-site") not in (
                None,
                "same-origin",
                "none",
            ):
                return JSONResponse(
                    {"detail": "Origine de requête non autorisée."}, status_code=403
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, exc):
        return JSONResponse(
            {"detail": "Données invalides. Vérifiez les champs et leurs formats."},
            status_code=422,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, exc):
        detail = exc.detail
        if detail == "Not Found":
            detail = "Ressource introuvable."
        return JSONResponse(
            {"detail": str(detail)}, status_code=exc.status_code, headers=exc.headers
        )

    @app.exception_handler(sqlite3.OperationalError)
    async def storage_error(request, exc):
        return JSONResponse(
            {
                "detail": "Le stockage local est temporairement indisponible. Réessayez après vérification du fichier de base."
            },
            status_code=503,
        )

    @app.get("/api/health")
    def health():
        return {
            "status": "ok",
            "storage": "sqlite",
            "mode": "local",
            "demo": os.getenv("SMART_STOCK_DEMO") == "1",
        }

    for router in (
        auth_router,
        maintenance_router,
        users_router,
        mobile_router,
        products_router,
        movements_router,
        imports_router,
        analysis_router,
        market_router,
        collection_router,
        actions_router,
        crm_router,
        opportunities_router,
        commerce_router,
        purchases_router,
        insights_router,
        replenishment_router,
        inventories_router,
        alerts_router,
        recommendations_router,
    ):
        app.include_router(router, prefix="/api")

    frontend = ROOT / "frontend" / "dist"
    if frontend.is_dir():
        assets = frontend / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if (
                path == "api"
                or path.startswith("api/")
                or (path.startswith("design") and not dev)
            ):
                raise HTTPException(404, "Ressource introuvable.")
            candidate = (frontend / path).resolve()
            if candidate.is_relative_to(frontend.resolve()) and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(frontend / "index.html")

    return app


app = create_app()
