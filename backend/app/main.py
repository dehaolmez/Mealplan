import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import catalog, household, inventory, plan, recipes, shopping
from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.services.errors import BadRequest, NotFound

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    import app.models  # noqa: F401  - tabloları metadata'ya kaydet

    Base.metadata.create_all(engine)
    if get_settings().seed_on_startup:
        from app.seed.loader import seed

        with SessionLocal() as db:
            seed(db)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(NotFound)
    async def _not_found(_: Request, exc: NotFound):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(BadRequest)
    async def _bad_request(_: Request, exc: BadRequest):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    for module in (household, catalog, inventory, recipes, plan, shopping):
        app.include_router(module.router, prefix="/api")

    @app.get("/api/health", tags=["Sistem"])
    def health():
        return {"status": "ok", "ai_enabled": settings.ai_enabled}

    return app


app = create_app()
