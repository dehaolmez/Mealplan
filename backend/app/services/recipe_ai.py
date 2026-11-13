"""Gemini ile tarif üretimi: toplu katalog betiği (scripts/generate_recipes.py) ve uygulama içi
"buzdolabımdakilerle tarif üret" aynı kuralları ve doğrulamayı kullanır."""

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.diet import recipe_violations
from app.domain.shelf_life import days_left
from app.domain.units import UnitConversionError, humanize, to_base_quantity
from app.models import Household, Ingredient, Recipe, RecipeIngredient
from app.models.enums import MealType
from app.services import clock, gemini, inventory_service
from app.services.errors import BadRequest

EQUIPMENT = ["stovetop", "oven", "microwave", "airfryer", "blender", "grill", "pressure_cooker", "none"]
MEALS = ["breakfast", "lunch", "dinner", "snack"]
TAGS = ["vejetaryen", "vegan", "pratik", "ekonomik", "geleneksel", "yüksek-protein", "hafif", "çorba",
        "çocuk-dostu", "glutensiz", "zeytinyağlı", "fırın", "salata", "tatlı", "toplu-pişirme"]

SYSTEM_RECIPE = """Bir ev yemekleri uygulaması için ÖZGÜN tarifler yazıyorsun. Kurallar:
- Malzemeler YALNIZ verilen katalogdan seçilir (ingredient alanı şemadaki listeden). Katalogda olmayan bir malzeme
  gerekiyorsa en yakın katalog karşılığını kullan ya da tarifin özünü bozmuyorsa çıkar.
- Miktarlar gerçekçi olsun; birim g, ml veya adet (adet yalnız yumurta, limon, sarımsak dişi, soğan gibi sayılanlar için).
  Tuz, karabiber gibi baharatlar için de küçük gram ver.
- servings: tarifin kaç kişilik olduğu (2-6).
- steps: 4-8 kısa, açık, Türkçe adım. Kendi cümlelerinle yaz; herhangi bir siteden metin kopyalama.
- description: tek cümle, iştah açıcı.
- equipment: gereken aletler (ocak=stovetop, fırın=oven, mikrodalga=microwave, airfryer, blender, ızgara=grill,
  düdüklü=pressure_cooker; hiç pişirme yoksa none).
- tags: uygun etiketler. vejetaryen/vegan etiketini yalnız gerçekten uygunsa koy.
- prep_minutes: toplam hazırlık + pişirme süresi."""


def piece_weights_note(catalog: dict[str, dict]) -> str:
    """Modelin 'adet'i doğru kullanması için adetle ölçülebilen malzemelerin gram karşılıkları."""
    parts = [f"{n}={c['grams_per_piece']:g} g" for n, c in sorted(catalog.items()) if c.get("grams_per_piece")]
    return ("Adet karşılıkları (1 adet): " + ", ".join(parts) +
            ". Ekmek 1 adet = bütün somun; dilim/yarım gibi miktarları gram olarak yaz.")


def recipe_schema(catalog: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {"recipes": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "name": {"type": "string"}, "description": {"type": "string"},
                "meal_type": {"type": "string", "enum": MEALS},
                "servings": {"type": "integer"}, "prep_minutes": {"type": "integer"},
                "equipment": {"type": "array", "items": {"type": "string", "enum": EQUIPMENT}},
                "tags": {"type": "array", "items": {"type": "string", "enum": TAGS}},
                "ingredients": {"type": "array", "items": {
                    "type": "object",
                    "properties": {
                        "ingredient": {"type": "string", "enum": catalog},
                        "quantity": {"type": "number"},
                        "unit": {"type": "string", "enum": ["g", "ml", "adet"]},
                        "optional": {"type": "boolean"},
                    },
                    "required": ["ingredient", "quantity", "unit", "optional"],
                }},
                "steps": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["name", "description", "meal_type", "servings", "prep_minutes", "equipment", "tags",
                         "ingredients", "steps"],
        }}},
        "required": ["recipes"],
    }


def _grams(item: dict, qty: float, unit: str) -> float | None:
    if unit == "g":
        return qty
    if unit == "ml":
        return qty * (item["density_g_per_ml"] or 1.0)
    return qty * item["grams_per_piece"] if item["grams_per_piece"] else None


def validate(r: dict, catalog: dict[str, dict]) -> str | None:
    """Model çıktısı için akıl sağlığı kontrolü. Hata metni ya da None döner."""
    if not 1 <= r["servings"] <= 8:
        return "porsiyon"
    if len(r["steps"]) < 3:
        return "adım az"
    kcal, main = 0.0, 0
    for line in r["ingredients"]:
        item = catalog.get(line["ingredient"])
        if item is None or line["quantity"] <= 0:
            return f"malzeme/miktar: {line['ingredient']}"
        if item["base_unit"] == "adet" and line["unit"] == "ml":
            return f"birim uyumsuz: {line['ingredient']}"
        if item["base_unit"] != "adet" and line["unit"] == "adet" and not item["grams_per_piece"]:
            return f"birim uyumsuz: {line['ingredient']}"
        g = _grams(item, line["quantity"], line["unit"])
        if g is None:
            return f"çevrilemedi: {line['ingredient']}"
        kcal += item["kcal"] * g / 100
        main += 0 if item["is_staple"] else 1
    per = kcal / r["servings"]
    if main < 2:
        return "ana malzeme az"
    if not 60 <= per <= 1400:
        return f"porsiyon kalorisi {per:.0f}"
    return None


def catalog_from_db(db: Session) -> dict[str, dict]:
    return {
        i.name: {"base_unit": i.base_unit.value, "grams_per_piece": i.grams_per_piece,
                 "density_g_per_ml": i.density_g_per_ml, "kcal": i.kcal_per_100g, "is_staple": i.is_staple, "obj": i}
        for i in db.scalars(select(Ingredient))
    }


def build_recipe(r: dict, catalog: dict[str, dict], household_id: int | None, source: str) -> Recipe:
    merged: dict[int, RecipeIngredient] = {}
    for line in r["ingredients"]:
        ing: Ingredient = catalog[line["ingredient"]]["obj"]
        try:
            qty = round(to_base_quantity(ing, line["quantity"], line["unit"]), 2)
        except UnitConversionError as exc:
            raise BadRequest(f"Tarif birimleri çevrilemedi: {exc}") from exc
        if ing.id in merged:
            merged[ing.id].quantity += qty
        else:
            merged[ing.id] = RecipeIngredient(ingredient_id=ing.id, ingredient=ing, quantity=qty,
                                              optional=bool(line.get("optional")))
    recipe = Recipe(
        name=r["name"][:120], description=r["description"], instructions="\n".join(r["steps"]),
        servings=r["servings"], prep_minutes=r["prep_minutes"], meal_type=MealType(r["meal_type"]),
        tags=",".join(r["tags"]), equipment=",".join(r["equipment"]) or "stovetop", source=source,
        household_id=household_id,
    )
    recipe.ingredients = list(merged.values())
    return recipe


def generate_for_household(db: Session, household: Household, meal_type: str | None, wish: str | None) -> Recipe:
    """Hanenin envanterine (önce bozulacaklar) ve kurallarına göre tek bir özgün tarif üretip kaydeder."""
    from app.services import preferences_service

    prefs = preferences_service.to_schema(preferences_service.get(db, household))
    rules = preferences_service.rules_for(prefs)
    catalog = catalog_from_db(db)
    today = clock.today()
    items = sorted(inventory_service.list_items(db, household), key=lambda i: i.expiry_date)
    inventory = [f"{i.ingredient.name} ({humanize(i.quantity, i.ingredient.base_unit)}, {days_left(i.expiry_date, today)} gün)"
                 for i in items if days_left(i.expiry_date, today) >= 0][:40]
    disliked = [i.name for i in db.scalars(select(Ingredient).where(Ingredient.id.in_(rules.disliked)))] if rules.disliked else []
    constraints = {
        "diyet": prefs.diet, "düşük_karbonhidrat": prefs.low_carb, "kesinlikle_olmayacaklar": prefs.exclusions,
        "sevilmeyen_malzemeler": disliked, "mutfak_aletleri": prefs.equipment, "en_fazla_dakika": prefs.max_prep_minutes,
    }
    user = (
        f"{piece_weights_note(catalog)}\n"
        f"Evdeki malzemeler (parantezde miktar ve bozulmaya kalan gün): {', '.join(inventory) or 'bilinmiyor'}.\n"
        f"Kurallar (kesin uy): {json.dumps(constraints, ensure_ascii=False)}.\n"
        f"Öğün: {meal_type or 'herhangi'}. İstek: {(wish or 'yok')[:200]}.\n"
        "Evdekileri, özellikle bozulmaya yakın olanları, mümkün olduğunca kullanan TEK bir tarif yaz. "
        "Eksik malzeme sayısı az olsun."
    )
    data = gemini.generate_json(SYSTEM_RECIPE, user, recipe_schema(sorted(catalog)), name="recipes", timeout=120, rounds=2)
    errors = []
    for r in data.get("recipes", [])[:3]:
        if meal_type:
            r["meal_type"] = meal_type
        err = validate(r, catalog)
        if err:
            errors.append(err)
            continue
        recipe = build_recipe(r, catalog, household.id, "gemini")
        problems = recipe_violations(recipe, rules, recipe.meal_type.value)
        if problems:
            errors.append("kurala aykırı: " + ", ".join(problems))
            continue
        db.add(recipe)
        db.commit()
        db.refresh(recipe)
        return recipe
    raise BadRequest("Yapay zekâ uygun bir tarif üretemedi" + (f" ({errors[0]})" if errors else "") + ". Tekrar deneyin.")
