import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import admin, auth, catalog, household, inventory, places, plan, preferences, receipts, recipes, shopping
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
            if settings.admin_email and settings.admin_password:
                from app.services.auth_service import ensure_admin

                _, created = ensure_admin(db, settings.admin_email, settings.admin_password)
                if created:
                    logging.getLogger(__name__).info("Yönetici hesabı oluşturuldu: %s", settings.admin_email)
            if settings.load_test_prices:
                from app.services.price_import import load_test_prices_once

                load_test_prices_once(db)
    if settings.live_prices_enabled and settings.live_prices_prefetch_pilot:
        threading.Thread(target=_prefetch_pilot_prices, name="pilot-prices", daemon=True).start()
    yield


def _prefetch_pilot_prices() -> None:
    """Pilot bölgenin katalog fiyatlarını arka planda tazeler (önbellek tazeyse hiç istek atmaz)."""
    from sqlalchemy import select

    from app.models import Ingredient
    from app.services import marketfiyati

    s = get_settings()
    try:
        with SessionLocal() as db:
            ids = list(db.scalars(select(Ingredient.id).where(Ingredient.is_staple.is_(False))))
            summary = marketfiyati.refresh(db, ids, s.pilot_lat, s.pilot_lon)
            logging.getLogger(__name__).info("Pilot bölge canlı fiyatları: %s", summary)
    except Exception as exc:  # arka plan işi uygulamayı düşürmemeli
        logging.getLogger(__name__).warning("Pilot fiyatları alınamadı: %s", exc)


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

    for module in (auth, household, catalog, inventory, recipes, plan, preferences, shopping, places, receipts, admin):
        app.include_router(module.router, prefix="/api")
    app.include_router(auth.legal_router, prefix="/api")

    @app.get("/api/health", tags=["Sistem"])
    def health():
        s = get_settings()
        return {"status": "ok", "ai_available": s.ai_available, "ai_provider": s.ai_provider,
                "live_prices": s.live_prices_enabled}

    if settings.static_dir and Path(settings.static_dir, "index.html").exists():
        _mount_frontend(app, Path(settings.static_dir))
    return app


class _NoCacheSW(StaticFiles):
    """Servis çalışanı ve manifest her zaman tazelensin; diğer dosyalar (hash'li) uzun süre önbelleklenir."""

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if path in ("sw.js", "manifest.webmanifest", "index.html", ".", ""):
            response.headers["Cache-Control"] = "no-cache"
        elif path.startswith("assets/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


def _mount_frontend(app: FastAPI, directory: Path) -> None:
    app.mount("/", _NoCacheSW(directory=directory, html=True), name="frontend")


app = create_app()
