import threading
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.api.deps import DB, CurrentUser
from app.core.config import get_settings
from app.models import Household, InventoryItem, LivePriceFetch, MarketProduct, Store, User
from app.services.auth_service import Unauthorized

_refresh_lock = threading.Lock()
_refresh_state: dict = {"running": False, "last_result": None, "last_error": None, "finished_at": None}


def require_admin(user: CurrentUser) -> None:
    if not user.is_admin:
        raise Unauthorized("Bu işlem için yönetici yetkisi gerekli")


router = APIRouter(prefix="/admin", tags=["Yönetim"], dependencies=[Depends(require_admin)])


@router.get("/stats")
def stats(db: DB):
    """Sistem durumu (kişisel veri içermez; yalnız sayılar)."""
    s = get_settings()
    count = lambda model: db.scalar(select(func.count()).select_from(model))  # noqa: E731
    last_fetch = db.scalar(select(func.max(LivePriceFetch.fetched_at)))
    per_store = db.execute(
        select(Store.name, func.count(MarketProduct.id)).join(MarketProduct, MarketProduct.store_id == Store.id)
        .group_by(Store.name).order_by(Store.name)
    ).all()
    return {
        "users": count(User),
        "households": count(Household),
        "inventory_items": count(InventoryItem),
        "live_products": count(MarketProduct),
        "live_products_by_store": {name: n for name, n in per_store},
        # Saat dilimli ISO: tarayıcı Türkiye saatine doğru çevirsin (sunucu UTC'de çalışabilir)
        "live_last_fetch": last_fetch.astimezone().isoformat() if last_fetch else None,
        "live_prices_enabled": s.live_prices_enabled,
        "ai_available": s.ai_available,
        "ai_provider": s.ai_provider,
        "pilot": s.pilot_name,
        "refresh": _refresh_state,
    }


@router.post("/live-prices/refresh", status_code=202)
def refresh_pilot_prices():
    """Pilot bölgenin tüm katalog fiyatlarını arka planda zorla tazeler (~1-2 dk)."""
    if not _refresh_lock.acquire(blocking=False):
        return {"started": False, "message": "Zaten çalışıyor"}

    def run():
        from app.core.database import SessionLocal
        from app.models import Ingredient
        from app.services import marketfiyati

        _refresh_state.update(running=True, last_error=None)
        s = get_settings()
        try:
            with SessionLocal() as db:
                ids = list(db.scalars(select(Ingredient.id).where(Ingredient.is_staple.is_(False))))
                _refresh_state["last_result"] = marketfiyati.refresh(db, ids, s.pilot_lat, s.pilot_lon, force=True)
        except Exception as exc:  # noqa: BLE001
            _refresh_state["last_error"] = str(exc)
        finally:
            _refresh_state.update(running=False, finished_at=datetime.now().astimezone().isoformat())
            _refresh_lock.release()

    threading.Thread(target=run, daemon=True).start()
    return {"started": True}
