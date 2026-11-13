from fastapi import APIRouter, Response, status

from app.api.deps import DB, CurrentHousehold
from app.models.enums import StorageLocation
from app.schemas.inventory import AlertsOut, InventoryItemIn, InventoryItemOut, InventoryItemUpdate
from app.services import clock
from app.services import inventory_service as svc
from app.services.mappers import inventory_out

router = APIRouter(prefix="/inventory", tags=["Envanter & SKT"])


@router.get("", response_model=list[InventoryItemOut])
def list_items(db: DB, household: CurrentHousehold, location: StorageLocation | None = None):
    today = clock.today()
    return [inventory_out(i, today) for i in svc.list_items(db, household, location)]


@router.post("", response_model=InventoryItemOut, status_code=status.HTTP_201_CREATED)
def add_item(data: InventoryItemIn, db: DB, household: CurrentHousehold):
    """SKT girilmezse ürünün saklama yerine ve açık olup olmadığına göre raf ömrü tahmin edilir."""
    return inventory_out(svc.add_item(db, household, data), clock.today())


@router.patch("/{item_id}", response_model=InventoryItemOut | None)
def update_item(item_id: int, data: InventoryItemUpdate, db: DB, household: CurrentHousehold, response: Response):
    item = svc.update_item(db, household, item_id, data)
    if item is None:
        response.status_code = status.HTTP_204_NO_CONTENT
        return None
    return inventory_out(item, clock.today())


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int, db: DB, household: CurrentHousehold):
    svc.delete_item(db, household, item_id)


@router.get("/alerts", response_model=AlertsOut)
def alerts(db: DB, household: CurrentHousehold):
    """SKT'si geçmiş, kritik (≤1 gün) ve yaklaşan (≤3 gün) ürün uyarıları."""
    return svc.alerts(db, household)
