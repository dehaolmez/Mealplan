"""Örnek veriyi idempotent biçimde yükler: katalog boşsa doldurur, hane boşsa demo envanter ekler."""

import json
import logging
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.shelf_life import resolve_expiry
from app.domain.units import UnitConversionError, to_base_quantity
from app.models import Chain, Household, Ingredient, InventoryItem, Member, Recipe, RecipeIngredient, Store, StorePrice
from app.models.enums import ActivityLevel, BaseUnit, Category, ChainKind, Goal, MealType, Sex, StorageLocation
from app.seed import data
from app.services import clock

log = logging.getLogger(__name__)


def seed(db: Session) -> None:
    """Ortak katalog verisi: zincirler, malzemeler, tarifler, demo marketler/fiyatlar.

    İlk kurulumdan sonra da her açılışta eksik malzeme/tarifler ad bazında eklenir (mevcut veriler korunur);
    böylece katalog büyüdüğünde var olan veritabanları da güncellenir."""
    if db.scalar(select(func.count(Chain.id))) == 0:
        _seed_chains(db)
    if db.scalar(select(func.count(Ingredient.id))) == 0:
        _seed_catalog(db)
        log.info("Katalog, tarifler ve fiyatlar yüklendi")
    added_i = _upsert_extra_ingredients(db)
    added_r = _upsert_manual_recipes(db) + _upsert_generated_recipes(db)
    _repair_empty_recipes(db)
    _backfill_courses(db)
    if added_i or added_r:
        log.info("Katalog güncellendi: +%d malzeme, +%d tarif", added_i, added_r)
    db.commit()


def _upsert_extra_ingredients(db: Session) -> int:
    existing = {i.name: i for i in db.scalars(select(Ingredient))}
    # Eski kayıtlara etiket ve (eksikse) adet ağırlığı ekle
    for name, tags in data.DIET_TAGS.items():
        if name in existing and not existing[name].diet_tags:
            existing[name].diet_tags = tags
    for row in data.INGREDIENTS:
        ing = existing.get(row[0])
        if ing is not None and ing.grams_per_piece is None and row[3]:
            ing.grams_per_piece = row[3]
    added = 0
    path = Path(__file__).with_name("catalog_extra.json")
    if not path.exists():
        return 0
    for item in json.loads(path.read_text(encoding="utf-8")):
        if item["name"] in existing:
            continue
        db.add(Ingredient(
            name=item["name"], category=Category(item["category"]),
            base_unit=BaseUnit.piece if item["base_unit"] == "adet" else BaseUnit(item["base_unit"]),
            grams_per_piece=item["grams_per_piece"], density_g_per_ml=item["density_g_per_ml"],
            kcal_per_100g=item["kcal"], protein_per_100g=item["protein"], carbs_per_100g=item["carbs"],
            fat_per_100g=item["fat"], shelf_life_fridge_days=item["shelf_life_fridge_days"],
            shelf_life_freezer_days=item["shelf_life_freezer_days"],
            shelf_life_opened_days=item["shelf_life_opened_days"], is_staple=item["is_staple"],
            emoji=item["emoji"][:8] or "🛒", diet_tags=",".join(item["diet_tags"]),
        ))
        added += 1
    db.flush()
    return added


def _upsert_generated_recipes(db: Session) -> int:
    files = sorted((Path(__file__).parent / "recipes").glob("*.json"))
    if not files:
        return 0
    ingredients = {i.name: i for i in db.scalars(select(Ingredient))}
    by_id = {i.id: i for i in ingredients.values()}
    public = {r.name.lower() for r in db.scalars(select(Recipe).where(Recipe.household_id.is_(None)))}
    added = 0
    rows = [r for f in files for r in json.loads(f.read_text(encoding="utf-8"))]
    for r in rows:
        if r["name"].lower() in public:
            continue
        lines = []
        try:
            for line in r["ingredients"]:
                ing = ingredients[line["ingredient"]]
                lines.append(RecipeIngredient(ingredient_id=ing.id, optional=bool(line.get("optional")),
                                              quantity=round(to_base_quantity(ing, line["quantity"], line["unit"]), 2)))
        except (KeyError, UnitConversionError):
            log.warning("Tarif atlandı (malzeme/birim uyumsuz): %s", r["name"])
            continue
        merged: dict[int, RecipeIngredient] = {}
        for ln in lines:  # aynı malzeme iki kez geçerse topla
            if ln.ingredient_id in merged:
                merged[ln.ingredient_id].quantity += ln.quantity
            else:
                merged[ln.ingredient_id] = ln
        recipe = Recipe(
            name=r["name"], description=r["description"], instructions="\n".join(r["steps"]),
            servings=r["servings"], prep_minutes=r["prep_minutes"], meal_type=MealType(r["meal_type"]),
            tags=",".join(r["tags"]), equipment=",".join(r["equipment"]) or "stovetop", source="gemini",
        )
        recipe.ingredients = list(merged.values())
        recipe.tags = ",".join(_diet_tags_fixed(r["tags"], recipe.ingredients, by_id))
        db.add(recipe)
        public.add(r["name"].lower())
        added += 1
    db.flush()
    return added


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


def _diet_tags_fixed(tags: list[str], lines: list[RecipeIngredient], by_id: dict[int, Ingredient]) -> list[str]:
    """Vejetaryen/vegan etiketini modelin yazdığına değil, zorunlu malzemelerin etiketlerine göre belirler."""
    from app.domain.diet import DIET_FORBIDS, tags_of

    used: set[str] = set()
    for line in lines:
        if not line.optional:
            used |= tags_of(by_id[line.ingredient_id].diet_tags)
    out = [t for t in tags if t not in ("vejetaryen", "vegan")]
    if not used & DIET_FORBIDS["vegetarian"]:
        out.append("vejetaryen")
    if not used & DIET_FORBIDS["vegan"]:
        out.append("vegan")
    return out


def _backfill_courses(db: Session) -> None:
    """Ortak katalogdaki tariflerin türünü (çorba/ana/yan/salata...) ada ve kategoriye göre belirler."""
    from app.domain.courses import classify

    groups: dict[str, str] = {}
    for f in (Path(__file__).parent / "recipes").glob("*.json"):
        for r in json.loads(f.read_text(encoding="utf-8")):
            groups[r["name"].lower()] = r.get("group", "")
    for recipe in db.scalars(select(Recipe).where(Recipe.household_id.is_(None))):
        course = classify(recipe.name, recipe.meal_type.value, groups.get(recipe.name.lower()))
        if recipe.course != course:
            recipe.course = course
    db.flush()


def _upsert_manual_recipes(db: Session) -> int:
    """Elle yazılmış tarifler (data.RECIPES): ad bazında eksik olanları ekler."""
    ingredients = {i.name: i for i in db.scalars(select(Ingredient))}
    public = {r.name.lower() for r in db.scalars(select(Recipe).where(Recipe.household_id.is_(None)))}
    added = 0
    for name, meal, servings, minutes, tags, desc, steps, lines in data.RECIPES:
        if name.lower() in public or any(ing not in ingredients for ing, _, _ in lines):
            continue
        recipe = Recipe(name=name, meal_type=meal, servings=servings, prep_minutes=minutes, tags=tags,
                        description=desc, instructions=steps,
                        equipment="oven" if ("fırın" in steps.lower() or "Fırın" in name) else "stovetop")
        recipe.ingredients = [
            RecipeIngredient(ingredient_id=ingredients[ing].id, quantity=qty, optional=opt) for ing, qty, opt in lines
        ]
        db.add(recipe)
        added += 1
    db.flush()
    return added


def _repair_empty_recipes(db: Session) -> int:
    """Malzemesi kaybolmuş ortak tarifleri kaynak tanımından yeniden kurar (plan kayıtları korunur).

    v0.5 öncesi bir SQLite migrasyonu, dolu veritabanlarında tarif malzemelerini silebiliyordu."""
    from sqlalchemy import exists

    empty = list(db.scalars(select(Recipe).where(
        Recipe.household_id.is_(None), ~exists().where(RecipeIngredient.recipe_id == Recipe.id))))
    if not empty:
        return 0
    ingredients = {i.name: i for i in db.scalars(select(Ingredient))}
    manual = {name.lower(): lines for name, _, _, _, _, _, _, lines in data.RECIPES}
    generated = {r["name"].lower(): r for f in (Path(__file__).parent / "recipes").glob("*.json")
                 for r in json.loads(f.read_text(encoding="utf-8"))}
    fixed = 0
    for recipe in empty:
        key = recipe.name.lower()
        lines: list[RecipeIngredient] = []
        try:
            if key in manual:
                lines = [RecipeIngredient(ingredient_id=ingredients[n].id, quantity=q, optional=o) for n, q, o in manual[key]]
            elif key in generated:
                for line in generated[key]["ingredients"]:
                    ing = ingredients[line["ingredient"]]
                    lines.append(RecipeIngredient(ingredient_id=ing.id, optional=bool(line.get("optional")),
                                                  quantity=round(to_base_quantity(ing, line["quantity"], line["unit"]), 2)))
        except (KeyError, UnitConversionError):
            continue
        merged: dict[int, RecipeIngredient] = {}
        for ln in lines:
            if ln.ingredient_id in merged:
                merged[ln.ingredient_id].quantity += ln.quantity
            else:
                merged[ln.ingredient_id] = ln
        if merged:
            recipe.ingredients = list(merged.values())
            fixed += 1
    db.flush()
    if fixed:
        log.warning("Malzemesi eksik %d tarif onarıldı", fixed)
    return fixed
