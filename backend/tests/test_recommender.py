from datetime import timedelta

from sqlalchemy import select

from app.domain.recommender import evaluate_recipe, recommend
from app.domain.requirements import aggregate_requirements, find_missing
from app.domain.stock import build_stock
from app.models import Ingredient, InventoryItem, Recipe
from app.models.enums import StorageLocation


def _recipe(db, name):
    return db.scalar(select(Recipe).where(Recipe.name == name))


def _ing(db, name):
    return db.scalar(select(Ingredient).where(Ingredient.name == name))


def _stock(db, today, rows):
    items = []
    for i, (name, qty, days) in enumerate(rows, start=1):
        items.append(InventoryItem(id=i, household_id=1, ingredient_id=_ing(db, name).id, quantity=qty,
                                   location=StorageLocation.fridge, added_on=today,
                                   expiry_date=today + timedelta(days=days)))
    return build_stock(items, today)


def test_missing_scales_with_servings_and_skips_staples_and_optional(db, fixed_today):
    menemen = _recipe(db, "Menemen")  # 2 porsiyon: 4 yumurta, 300 g domates ...
    stock = _stock(db, fixed_today, [("Yumurta", 2, 5), ("Domates", 1000, 5)])
    reqs = aggregate_requirements([(menemen, 4)])
    missing = {m.ingredient.name: m.missing for m in find_missing(reqs, stock)}
    assert missing["Yumurta"] == 6  # 8 gerekli - 2 var
    assert "Domates" not in missing  # 600 gerekli, 1000 var
    assert "Tuz" not in missing  # temel ürün
    assert "Beyaz peynir" not in missing  # opsiyonel


def test_expired_items_are_not_counted_as_stock(db, fixed_today):
    stock = _stock(db, fixed_today, [("Yumurta", 10, -1)])
    reqs = aggregate_requirements([(_recipe(db, "Menemen"), 2)])
    assert any(m.ingredient.name == "Yumurta" for m in find_missing(reqs, stock))


def test_expiring_ingredients_boost_ranking(db, fixed_today):
    recipes = [_recipe(db, "Menemen"), _recipe(db, "Ispanaklı Yumurta")]
    base = [("Yumurta", 6, 20), ("Domates", 600, 20), ("Sivri biber", 200, 20), ("Tereyağı", 200, 60),
            ("Kuru soğan", 500, 20)]
    fresh_spinach = _stock(db, fixed_today, base + [("Ispanak", 400, 10)])
    rotting_spinach = _stock(db, fixed_today, base + [("Ispanak", 400, 0)])

    m_fresh = evaluate_recipe(recipes[1], fresh_spinach)
    m_rot = evaluate_recipe(recipes[1], rotting_spinach)
    assert m_rot.urgency > m_fresh.urgency == 0
    assert m_rot.uses_expiring[0].ingredient_name == "Ispanak"

    ranked = recommend(recipes, rotting_spinach)
    assert ranked[0].recipe.name == "Ispanaklı Yumurta"


def test_full_coverage_beats_partial(db, fixed_today):
    stock = _stock(db, fixed_today, [("Yumurta", 4, 20), ("Domates", 300, 20), ("Sivri biber", 100, 20),
                                      ("Tereyağı", 50, 20)])
    ranked = recommend([_recipe(db, "Karnıyarık"), _recipe(db, "Menemen")], stock)
    assert ranked[0].recipe.name == "Menemen" and ranked[0].coverage == 1.0
    assert ranked[1].missing


def test_nutrition_per_serving_is_computed(db):
    m = evaluate_recipe(_recipe(db, "Menemen"), {})
    # 4 yumurta (240 g) + 300 g domates + 100 g biber + 15 g tereyağı ... / 2 porsiyon
    assert 250 < m.per_serving.kcal < 400
    assert m.per_serving.protein_g > 15
