from fastapi import APIRouter, status

from app.api.deps import DB, CurrentHousehold
from app.models.enums import StorageLocation
from app.schemas.planning import (
    CheckoutOut,
    OptimizeOut,
    OptimizeRequest,
    ShoppingItemIn,
    ShoppingItemOut,
    ShoppingItemUpdate,
    ShoppingListOut,
)
from app.core.config import get_settings
from app.services import marketfiyati, places_service, pricing_service, recipe_service
from app.services.errors import BadRequest
from app.services import shopping_service as svc
from app.services.mappers import shopping_item_out

router = APIRouter(prefix="/shopping", tags=["Alışveriş Listesi & Fiyat"])


@router.get("", response_model=ShoppingListOut)
def get_list(db: DB, household: CurrentHousehold):
    return svc.get_list(db, household)


@router.post("/items", response_model=ShoppingItemOut, status_code=status.HTTP_201_CREATED)
def add_item(data: ShoppingItemIn, db: DB, household: CurrentHousehold):
    return shopping_item_out(svc.add_item(db, household, data))


@router.patch("/items/{item_id}", response_model=ShoppingItemOut)
def update_item(item_id: int, data: ShoppingItemUpdate, db: DB, household: CurrentHousehold):
    return shopping_item_out(svc.update_item(db, household, item_id, data))


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int, db: DB, household: CurrentHousehold):
    svc.delete_item(db, household, item_id)


@router.post("/checkout", response_model=CheckoutOut)
def checkout(db: DB, household: CurrentHousehold, location: StorageLocation = StorageLocation.fridge):
    """Alındı işaretli ürünleri envantere (SKT tahminiyle) aktarır ve listeden kaldırır."""
    return svc.checkout(db, household, location)


@router.post("/optimize", response_model=OptimizeOut)
def optimize(data: OptimizeRequest, db: DB, household: CurrentHousehold):
    """Eksik malzemeleri market fiyatlarıyla eşleştirir; istenirse listeye ekler."""
    missing = recipe_service.missing_for(db, household, data.selections, data.plan_from, data.plan_to, data.plan_dates)
    settings = get_settings()
    lat = data.lat if data.lat is not None else household.home_lat
    lon = data.lon if data.lon is not None else household.home_lon

    nearby_chains = None
    if data.nearby_only:
        if lat is None or lon is None:
            raise BadRequest("Yakındaki marketler için konum verin veya profilde ev konumunu kaydedin")
        nearby_chains = places_service.nearby_chain_ids(db, lat, lon, data.radius_m or household.search_radius_m)

    live_area, note = None, None
    if data.live_prices and settings.live_prices_enabled and missing:
        if lat is None or lon is None:  # konum yoksa pilot bölge fiyatları
            lat, lon = settings.pilot_lat, settings.pilot_lon
            note = f"Ev konumu kayıtlı olmadığından {settings.pilot_name} fiyatları kullanıldı."
        radius_km = max(1, round((data.radius_m or household.search_radius_m) / 1000))
        try:
            live_area = marketfiyati.refresh(db, [m.ingredient.id for m in missing], lat, lon, radius_km)["area_key"]
        except marketfiyati.LivePricesUnavailable as exc:
            live_area = marketfiyati.area_key(lat, lon, radius_km)  # önbellekte eski veri varsa kullan
            note = f"{exc}. Önbellekteki fiyatlar kullanıldı."
    return pricing_service.optimize_missing(
        db, household, missing, data.strategy, data.store_ids, data.add_to_list, nearby_chains,
        live_area=live_area, price_note=note,
    )
