from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.shelf_life import ExpiryStatus, classify, days_left, resolve_expiry
from app.domain.stock import Stock, allocate_fefo, build_stock
from app.domain.units import UnitConversionError, humanize, to_base_quantity
from app.models import Household, Ingredient, InventoryItem
from app.models.enums import StorageLocation
from app.schemas.inventory import AlertsOut, ExpiryAlert, InventoryItemIn, InventoryItemUpdate
from app.services import clock
from app.services.errors import BadRequest, NotFound


def list_items(db: Session, household: Household, location: StorageLocation | None = None) -> list[InventoryItem]:
    stmt = select(InventoryItem).where(InventoryItem.household_id == household.id)
    if location is not None:
        stmt = stmt.where(InventoryItem.location == location)
    return list(db.scalars(stmt.order_by(InventoryItem.expiry_date, InventoryItem.id)))


def current_stock(db: Session, household: Household) -> Stock:
    return build_stock(list_items(db, household), clock.today())


def _ingredient(db: Session, ingredient_id: int) -> Ingredient:
    ing = db.get(Ingredient, ingredient_id)
    if ing is None:
        raise NotFound("Malzeme", ingredient_id)
    return ing


def _convert(ing: Ingredient, quantity: float, unit: str | None) -> float:
    try:
        return to_base_quantity(ing, quantity, unit)
    except UnitConversionError as exc:
        raise BadRequest(str(exc)) from exc


def add_item(db: Session, household: Household, data: InventoryItemIn) -> InventoryItem:
    ing = _ingredient(db, data.ingredient_id)
    added_on = data.added_on or clock.today()
    expiry = resolve_expiry(ing, data.location, added_on, data.expiry_date, data.opened)
    item = InventoryItem(
        household_id=household.id,
        ingredient_id=ing.id,
        location=data.location,
        quantity=_convert(ing, data.quantity, data.unit),
        added_on=added_on,
        expiry_date=expiry.expiry_date,
        expiry_estimated=expiry.estimated,
        opened=data.opened,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def get_item(db: Session, household: Household, item_id: int) -> InventoryItem:
    item = db.get(InventoryItem, item_id)
    if item is None or item.household_id != household.id:
        raise NotFound("Envanter kalemi", item_id)
    return item


def update_item(db: Session, household: Household, item_id: int, data: InventoryItemUpdate) -> InventoryItem | None:
    """Miktar 0'a inerse kalem silinir ve None döner."""
    item = get_item(db, household, item_id)
    ing = item.ingredient
    today = clock.today()

    if data.quantity is not None:
        item.quantity = _convert(ing, data.quantity, data.unit)
    if data.expiry_date is not None:
        item.expiry_date = data.expiry_date
        item.expiry_estimated = False

    if data.location is not None and data.location != item.location:
        # Buzluğa alınan ürünün ömrü dondurucu kuralına göre yeniden başlar; çözülen ürün kısa ömürlüdür.
        item.location = data.location
        new_expiry = resolve_expiry(ing, data.location, today, None, opened=data.location == StorageLocation.fridge)
        item.expiry_date = new_expiry.expiry_date
        item.expiry_estimated = True

    if data.opened is True and not item.opened:
        item.opened = True
        opened_expiry = resolve_expiry(ing, item.location, today, item.expiry_date, opened=True)
        item.expiry_date = opened_expiry.expiry_date
        item.expiry_estimated = item.expiry_estimated or opened_expiry.estimated
    elif data.opened is False:
        item.opened = False

    if item.quantity <= 1e-9:
        db.delete(item)
        db.commit()
        return None
    db.commit()
    return item


def delete_item(db: Session, household: Household, item_id: int) -> None:
    db.delete(get_item(db, household, item_id))
    db.commit()


def consume(db: Session, household: Household, ingredient_id: int, quantity: float) -> float:
    """İlk bozulacak partiden başlayarak tüketir. Karşılanamayan miktarı döner."""
    items = {i.id: i for i in list_items(db, household) if i.ingredient_id == ingredient_id}
    stock = build_stock(items.values(), clock.today())
    remaining = quantity
    for lot, used in allocate_fefo(stock.get(ingredient_id, []), quantity):
        item = items[lot.item_id]
        item.quantity -= used
        remaining -= used
        if item.quantity <= 1e-9:
            db.delete(item)
    return max(0.0, remaining)


def alerts(db: Session, household: Household, today: date | None = None) -> AlertsOut:
    s = get_settings()
    today = today or clock.today()
    result: list[ExpiryAlert] = []
    counts = {ExpiryStatus.expired: 0, ExpiryStatus.critical: 0, ExpiryStatus.warning: 0}
    for item in list_items(db, household):
        status = classify(item.expiry_date, today, s.expiry_critical_days, s.expiry_warning_days)
        if status == ExpiryStatus.ok:
            continue
        counts[status] += 1
        left = days_left(item.expiry_date, today)
        name = item.ingredient.name
        qty = humanize(item.quantity, item.ingredient.base_unit)
        if status == ExpiryStatus.expired:
            msg = f"{name} ({qty}) {-left} gün önce bozulmuş olabilir — kontrol edin."
        elif left == 0:
            msg = f"{name} ({qty}) bugün tüketilmeli!"
        elif left == 1:
            msg = f"{name} ({qty}) yarın bozulacak."
        else:
            msg = f"{name} ({qty}) {left} gün içinde tüketilmeli."
        if item.expiry_estimated:
            msg += " (tahmini)"
        result.append(
            ExpiryAlert(
                item_id=item.id,
                ingredient_name=name,
                emoji=item.ingredient.emoji,
                location=item.location,
                days_left=left,
                status=status,
                message=msg,
            )
        )
    result.sort(key=lambda a: a.days_left)
    return AlertsOut(
        expired=counts[ExpiryStatus.expired],
        critical=counts[ExpiryStatus.critical],
        warning=counts[ExpiryStatus.warning],
        alerts=result,
    )
