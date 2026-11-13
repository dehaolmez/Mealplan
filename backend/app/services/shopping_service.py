"""Bring! tarzı alışveriş listesi: reyonlara göre gruplu, tek dokunuşla al/geri al,
son alınanlardan hızlı ekleme ve alınanları envantere aktarma."""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.price_optimizer import OptimizationResult
from app.domain.requirements import MissingLine
from app.domain.units import UnitConversionError, to_base_quantity
from app.models import Household, Ingredient, ShoppingItem
from app.models.enums import Category, StorageLocation
from app.schemas.inventory import InventoryItemIn
from app.schemas.planning import (
    CheckoutOut,
    ShoppingCategoryOut,
    ShoppingItemIn,
    ShoppingItemUpdate,
    ShoppingListOut,
)
from app.services import inventory_service
from app.services.errors import BadRequest, NotFound
from app.services.mappers import shopping_item_out

CATEGORY_ORDER = list(Category)
RECENT_DAYS = 30
RECENT_LIMIT = 24


def _open_items(db: Session, household: Household) -> list[ShoppingItem]:
    return list(
        db.scalars(
            select(ShoppingItem)
            .where(ShoppingItem.household_id == household.id, ShoppingItem.archived.is_(False))
            .order_by(ShoppingItem.created_at)
        )
    )


def get_list(db: Session, household: Household) -> ShoppingListOut:
    items = _open_items(db, household)
    grouped: dict[Category, list] = {}
    for item in items:
        grouped.setdefault(item.category, []).append(shopping_item_out(item))
    categories = [
        ShoppingCategoryOut(category=c, items=sorted(grouped[c], key=lambda i: (i.checked, i.name)))
        for c in CATEGORY_ORDER
        if c in grouped
    ]

    since = datetime.now() - timedelta(days=RECENT_DAYS)
    recent_rows = db.scalars(
        select(ShoppingItem)
        .where(
            ShoppingItem.household_id == household.id,
            ShoppingItem.archived.is_(True),
            ShoppingItem.checked_at >= since,
        )
        .order_by(ShoppingItem.checked_at.desc())
    )
    open_names = {i.name.lower() for i in items if not i.checked}
    recent, seen = [], set()
    for row in recent_rows:
        key = row.name.lower()
        if key in seen or key in open_names:
            continue
        seen.add(key)
        recent.append(shopping_item_out(row))
        if len(recent) >= RECENT_LIMIT:
            break

    open_items = [i for i in items if not i.checked]
    return ShoppingListOut(
        open_count=len(open_items),
        estimated_total=round(sum(i.estimated_price or 0 for i in open_items), 2),
        categories=categories,
        recently_bought=recent,
    )


def _find_open_duplicate(db: Session, household: Household, ingredient_id: int | None, name: str) -> ShoppingItem | None:
    for item in _open_items(db, household):
        if item.checked:
            continue
        if ingredient_id is not None and item.ingredient_id == ingredient_id:
            return item
        if ingredient_id is None and item.ingredient_id is None and item.name.lower() == name.lower():
            return item
    return None


def add_item(db: Session, household: Household, data: ShoppingItemIn, source: str = "manual") -> ShoppingItem:
    ingredient = None
    if data.ingredient_id is not None:
        ingredient = db.get(Ingredient, data.ingredient_id)
        if ingredient is None:
            raise NotFound("Malzeme", data.ingredient_id)
    elif data.name:
        # Serbest metin katalogdaki bir malzemeyle birebir eşleşiyorsa ona bağla (reyon/emoji için)
        ingredient = db.scalar(select(Ingredient).where(Ingredient.name.ilike(data.name.strip())))
    if ingredient is None and not data.name:
        raise BadRequest("Ürün adı veya malzeme seçin")

    name = ingredient.name if ingredient else data.name.strip()
    unit = data.unit or (ingredient.base_unit.value if ingredient and data.quantity else None)

    existing = _find_open_duplicate(db, household, ingredient.id if ingredient else None, name)
    if existing is not None:
        # Bring! davranışı: aynı ürün tekrar eklenirse yeni satır açma, miktarı birleştir
        if data.quantity:
            existing.quantity = _merge_qty(ingredient, existing, data.quantity, unit)
        if data.note:
            existing.note = data.note
        db.commit()
        return existing

    item = ShoppingItem(
        household_id=household.id,
        ingredient_id=ingredient.id if ingredient else None,
        name=name,
        category=ingredient.category if ingredient else Category.other,
        quantity=data.quantity,
        unit=unit,
        note=data.note,
        source=source,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _merge_qty(ingredient: Ingredient | None, existing: ShoppingItem, qty: float, unit: str | None) -> float | None:
    if existing.quantity is None:
        return qty
    if unit == existing.unit or ingredient is None:
        return existing.quantity + qty
    try:  # farklı birimler: mevcut kaleme çevir
        add = to_base_quantity(ingredient, qty, unit)
        base_existing = to_base_quantity(ingredient, existing.quantity, existing.unit)
        existing.unit = ingredient.base_unit.value
        return base_existing + add
    except UnitConversionError:
        return existing.quantity + qty


def _get(db: Session, household: Household, item_id: int) -> ShoppingItem:
    item = db.get(ShoppingItem, item_id)
    if item is None or item.household_id != household.id:
        raise NotFound("Liste kalemi", item_id)
    return item


def update_item(db: Session, household: Household, item_id: int, data: ShoppingItemUpdate) -> ShoppingItem:
    item = _get(db, household, item_id)
    fields = data.model_dump(exclude_unset=True)
    if "checked" in fields:
        item.checked = bool(fields.pop("checked"))
        item.checked_at = datetime.now() if item.checked else None
    for key, value in fields.items():
        setattr(item, key, value)
    db.commit()
    return item


def delete_item(db: Session, household: Household, item_id: int) -> None:
    db.delete(_get(db, household, item_id))
    db.commit()


def add_purchases(
    db: Session, household: Household, result: OptimizationResult, by_id: dict[int, MissingLine]
) -> int:
    count = 0
    for p in result.purchases:
        line = by_id[p.need.ingredient_id]
        qty = p.packages * p.offer.package_size if p.offer else round(line.missing, 2)
        item = add_item(
            db,
            household,
            ShoppingItemIn(ingredient_id=line.ingredient.id, quantity=qty, unit=line.ingredient.base_unit.value,
                           note=", ".join(line.recipes)[:200]),
            source="plan",
        )
        if p.offer:
            item.store_id = p.offer.store_id
            item.estimated_price = round((item.estimated_price or 0) + p.cost, 2)
        count += 1
    db.commit()
    return count


def checkout(db: Session, household: Household, location: StorageLocation = StorageLocation.fridge) -> CheckoutOut:
    """İşaretlenen (alınan) kalemleri envantere ekler ve listeden arşivler."""
    moved = cleared = 0
    for item in _open_items(db, household):
        if not item.checked:
            continue
        if item.ingredient_id is not None and item.quantity:
            ing = item.ingredient
            target = StorageLocation.freezer if ing.category == Category.frozen else location
            try:
                inventory_service.add_item(
                    db,
                    household,
                    InventoryItemIn(ingredient_id=ing.id, location=target, quantity=item.quantity, unit=item.unit),
                )
                moved += 1
            except BadRequest:
                pass
        item.archived = True
        cleared += 1
    db.commit()
    return CheckoutOut(moved_to_inventory=moved, cleared=cleared)
