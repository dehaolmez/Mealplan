import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import auth, catalog, household, inventory, places, plan, recipes, shopping
from app.core.config import get_settings
from app.core.database import SessionLocal, engine
from app.services.auth_service import Unauthorized
from app.services.errors import BadRequest, NotFound

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    import app.models  # noqa: F401  - tabloları metadata'ya kaydet
    from app.core.migrations import upgrade_database

    settings = get_settings()
    if settings.auto_migrate:
        upgrade_database(engine)  # yeni şema/migrasyonlar otomatik; eski SQLite yedeklenip yenilenir
    if settings.seed_on_startup:
        from app.seed.loader import seed

        with SessionLocal() as db:
            seed(db)
            if settings.load_test_prices:
                from app.services.price_import import load_test_prices_once

                load_test_prices_once(db)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.3.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(NotFound)
    async def _not_found(_: Request, exc: NotFound):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(Unauthorized)
    async def _unauthorized(_: Request, exc: Unauthorized):
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    @app.exception_handler(BadRequest)
    async def _bad_request(_: Request, exc: BadRequest):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    for module in (auth, household, catalog, inventory, recipes, plan, shopping, places):
        app.include_router(module.router, prefix="/api")
    app.include_router(auth.legal_router, prefix="/api")

    @app.get("/api/health", tags=["Sistem"])
    def health():
        return {"status": "ok", "ai_enabled": settings.ai_enabled}

    return app


app = create_app()
