"""Kural tabanlı "Buzdolabında ne var?" tarif öneri motoru.

Her tarif üç bileşenle puanlanır:
  * coverage   – tarifin (zorunlu, temel olmayan) malzemelerinin evde ne kadarının karşılandığı
  * urgency    – tarifin, bozulmaya yakın ürünleri ne ölçüde tükettiği (israfı azaltma)
  * nutrition  – porsiyon kalorisinin hanenin öğün başı hedefine yakınlığı

Toplam puan = W_COVERAGE*coverage + W_URGENCY*urgency + W_NUTRITION*nutrition  (0..1)
Bu motor deterministiktir; yapay zekâ katmanı (ai_planner) bunun çıktısını yeniden sıralar/açıklar.
"""

from dataclasses import dataclass, field

from app.domain.nutrition import Macros
from app.domain.requirements import MissingLine, aggregate_requirements, find_missing
from app.domain.stock import Stock, allocate_fefo, available
from app.domain.units import to_grams
from app.models.recipe import Recipe

W_COVERAGE = 0.55
W_URGENCY = 0.30
W_NUTRITION = 0.15

# Bu kadar gün veya daha azı kalan ürünler "acil" sayılır; 0 gün = en yüksek aciliyet
URGENCY_HORIZON_DAYS = 7


@dataclass
class ExpiringUse:
    ingredient_name: str
    days_left: int
    quantity: float


@dataclass
class RecipeMatch:
    recipe: Recipe
    servings: int
    score: float
    coverage: float
    urgency: float
    nutrition_fit: float
    per_serving: Macros
    uses_expiring: list[ExpiringUse] = field(default_factory=list)
    missing: list[MissingLine] = field(default_factory=list)
    ai_reason: str | None = None


def recipe_macros_per_serving(recipe: Recipe) -> Macros:
    total = Macros()
    for line in recipe.ingredients:
        ing = line.ingredient
        grams = to_grams(ing, line.quantity)
        total = total + Macros(
            ing.kcal_per_100g * grams / 100,
            ing.protein_per_100g * grams / 100,
            ing.carbs_per_100g * grams / 100,
            ing.fat_per_100g * grams / 100,
        )
    return total.scaled(1 / max(recipe.servings, 1)).rounded()


def _urgency_weight(days: int) -> float:
    if days >= URGENCY_HORIZON_DAYS:
        return 0.0
    return 1 - max(days, 0) / URGENCY_HORIZON_DAYS


def evaluate_recipe(
    recipe: Recipe,
    stock: Stock,
    servings: int | None = None,
    meal_kcal_target: float | None = None,
) -> RecipeMatch:
    servings = servings or recipe.servings
    reqs = aggregate_requirements([(recipe, servings)])

    weights_total = 0.0
    covered_total = 0.0
    urgency_sum = 0.0
    expiring: list[ExpiringUse] = []

    for ingredient_id, req in reqs.items():
        if req.ingredient.is_staple:
            continue
        weights_total += 1
        have = available(stock, ingredient_id)
        covered_total += min(1.0, have / req.quantity) if req.quantity > 0 else 1.0

        for lot, used in allocate_fefo(stock.get(ingredient_id, []), req.quantity):
            weight = _urgency_weight(lot.days_left)
            if weight > 0:
                urgency_sum += weight
                expiring.append(ExpiringUse(req.ingredient.name, lot.days_left, used))

    coverage = covered_total / weights_total if weights_total else 1.0
    urgency = min(1.0, urgency_sum)

    per_serving = recipe_macros_per_serving(recipe)
    if meal_kcal_target and meal_kcal_target > 0:
        nutrition_fit = max(0.0, 1 - abs(per_serving.kcal - meal_kcal_target) / meal_kcal_target)
    else:
        nutrition_fit = 0.5  # profil yoksa nötr

    score = W_COVERAGE * coverage + W_URGENCY * urgency + W_NUTRITION * nutrition_fit
    expiring.sort(key=lambda e: e.days_left)

    return RecipeMatch(
        recipe=recipe,
        servings=servings,
        score=round(score, 4),
        coverage=round(coverage, 4),
        urgency=round(urgency, 4),
        nutrition_fit=round(nutrition_fit, 4),
        per_serving=per_serving,
        uses_expiring=expiring,
        missing=find_missing(reqs, stock),
    )


def recommend(
    recipes: list[Recipe],
    stock: Stock,
    *,
    servings: int | None = None,
    meal_kcal_target: float | None = None,
    min_coverage: float = 0.0,
    limit: int = 10,
) -> list[RecipeMatch]:
    matches = [evaluate_recipe(r, stock, servings, meal_kcal_target) for r in recipes]
    matches = [m for m in matches if m.coverage >= min_coverage]
    matches.sort(key=lambda m: (m.score, m.coverage, -len(m.missing)), reverse=True)
    return matches[:limit]
