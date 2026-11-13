"""Örnek veriyi idempotent biçimde yükler: katalog boşsa doldurur, hane boşsa demo envanter ekler."""

import logging
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.shelf_life import resolve_expiry
from app.models import Chain, Household, Ingredient, InventoryItem, Member, Recipe, RecipeIngredient, Store, StorePrice
from app.models.enums import ActivityLevel, ChainKind, Goal, Sex, StorageLocation
from app.seed import data
from app.services import clock

log = logging.getLogger(__name__)


def seed(db: Session) -> None:
    """Ortak katalog verisi: zincirler, malzemeler, tarifler, demo marketler/fiyatlar."""
    if db.scalar(select(func.count(Chain.id))) == 0:
        _seed_chains(db)
    if db.scalar(select(func.count(Ingredient.id))) == 0:
        _seed_catalog(db)
        log.info("Katalog, tarifler ve fiyatlar yüklendi")
    db.commit()


def _seed_catalog(db: Session) -> None:
    ingredients: dict[str, Ingredient] = {}
    for (name, cat, unit, gpp, dens, kcal, p, c, f, fridge, freezer, opened, staple, emoji) in data.INGREDIENTS:
        ing = Ingredient(
            name=name, category=cat, base_unit=unit, grams_per_piece=gpp, density_g_per_ml=dens,
            kcal_per_100g=kcal, protein_per_100g=p, carbs_per_100g=c, fat_per_100g=f,
            shelf_life_fridge_days=fridge, shelf_life_freezer_days=freezer, shelf_life_opened_days=opened,
            is_staple=staple, emoji=emoji,
        )
        db.add(ing)
        ingredients[name] = ing
    db.flush()

    for name, meal, servings, minutes, tags, desc, steps, lines in data.RECIPES:
        recipe = Recipe(name=name, meal_type=meal, servings=servings, prep_minutes=minutes, tags=tags,
                        description=desc, instructions=steps)
        recipe.ingredients = [
            RecipeIngredient(ingredient_id=ingredients[ing].id, quantity=qty, optional=opt) for ing, qty, opt in lines
        ]
        db.add(recipe)

    stores = []
    for name, color in data.STORES:
        store = Store(name=name, color=color, is_demo=True)
        db.add(store)
        stores.append(store)
    db.flush()

    today = clock.today()
    for ing_name, (pack, *prices) in data.PRICES.items():
        for store, price in zip(stores, prices, strict=True):
            if price is None:
                continue
            db.add(StorePrice(store_id=store.id, ingredient_id=ingredients[ing_name].id, package_size=pack,
                              price=price, source="demo", updated_on=today))


def seed_sample_household(db: Session, household: Household, with_members: bool = True) -> None:
    """Yeni hesaba örnek envanter (ve sağlık verisine rıza varsa örnek bireyler) ekler."""
    store_ids = list(db.scalars(select(Store.id).where(Store.is_demo.is_(True)).order_by(Store.id)))
    household.selected_store_ids = ",".join(map(str, store_ids))
    household.preferred_store_id = store_ids[0] if store_ids else None
    if with_members:
        for name, birth, sex, height, weight, activity, goal in data.DEMO_MEMBERS:
            db.add(Member(household_id=household.id, name=name, birth_date=date.fromisoformat(birth), sex=Sex(sex),
                          height_cm=height, weight_kg=weight, activity_level=ActivityLevel(activity), goal=Goal(goal)))

    by_name = {i.name: i for i in db.scalars(select(Ingredient))}
    today = clock.today()
    for name, loc, qty, days_ago, label_days in data.DEMO_INVENTORY:
        ing = by_name[name]
        location = StorageLocation(loc)
        added = today - timedelta(days=days_ago)
        label = today + timedelta(days=label_days) if label_days is not None else None
        est = resolve_expiry(ing, location, added, label, opened=False)
        db.add(InventoryItem(household_id=household.id, ingredient_id=ing.id, location=location, quantity=qty,
                             added_on=added, expiry_date=est.expiry_date, expiry_estimated=est.estimated))


def _seed_chains(db: Session) -> None:
    for slug, name, kind, parent, aliases, website, color, in_mf in data.CHAINS:
        db.add(Chain(slug=slug, name=name, kind=ChainKind(kind), parent=parent, aliases=aliases,
                     website=website, color=color, in_market_fiyati=in_mf))
    db.flush()
