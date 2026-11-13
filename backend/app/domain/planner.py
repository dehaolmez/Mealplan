"""Otomatik haftalık plan.

Her gün × planlanan öğün için aday tarifler puanlanır ve en iyisi seçilir:
  * envanter kapsaması ve bozulmak üzere olan ürünleri tüketme (recommender ile aynı motor),
  * öğün başı kalori hedefine uyum,
  * tahmini eksik malzeme maliyeti (haftalık bütçeye göre),
  * tekrar tercihi: variety (aynı tarif haftada ≤2, ardışık gün yok), balanced (öğle yemeği iki gün: bir pişir
    iki ye), batch (tek öğle yemeği bütün hafta).
Seçilen tarifin malzemeleri sanal envanterden düşülür; böylece ertesi günün planı güncel stoğa göre yapılır.
"""

import random
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date

from app.domain.recommender import evaluate_recipe
from app.domain.requirements import aggregate_requirements
from app.domain.stock import Stock, StockLot, allocate_fefo
from app.models.recipe import Recipe

MEAL_WEIGHTS = {"breakfast": 0.25, "lunch": 0.35, "dinner": 0.40, "snack": 0.10}
SLOT_RECIPE_TYPES = {
    "breakfast": {"breakfast"},
    "lunch": {"lunch", "dinner"},
    "dinner": {"dinner", "lunch"},
    "snack": {"snack", "breakfast"},
}


PROTEIN_ORDER = ("red_meat", "poultry", "fish", "shellfish")


def protein_key(recipe: Recipe) -> str:
    """Tarifin ana protein türü (çeşitlilik için): kırmızı et, tavuk, balık... yoksa "veg"."""
    from app.domain.diet import tags_of

    found = set()
    for line in recipe.ingredients:
        if not line.optional:
            found |= tags_of(line.ingredient.diet_tags)
    return next((k for k in PROTEIN_ORDER if k in found), "veg")


def portion_factor(kcal_per_serving: float, target: float | None) -> float:
    """Hedefe yaklaşmak için kişi başı porsiyon çarpanı (0,5'lik adımlarla 1–2 arası)."""
    if not target or kcal_per_serving <= 0:
        return 1.0
    return max(1.0, min(2.0, round(target / kcal_per_serving * 2) / 2))


@dataclass
class PlannedMeal:
    day: date
    meal_type: str
    recipe: Recipe
    servings: int
    is_leftover: bool = False
    est_cost: float = 0.0
    kcal_per_serving: float = 0.0


@dataclass
class WeekPlan:
    meals: list[PlannedMeal] = field(default_factory=list)
    est_cost: float = 0.0
    warnings: list[str] = field(default_factory=list)


def meal_targets(daily_kcal: float, meal_modes: dict[str, dict]) -> dict[str, float]:
    """Kendi hallettiği öğünlerin kalorisi düşüldükten sonra kalan enerji planlanan öğünlere ağırlıkla dağıtılır."""
    reserved = sum(float(m.get("kcal") or 0) for m in meal_modes.values() if m.get("mode") == "own")
    planned = [k for k, m in meal_modes.items() if m.get("mode") == "plan"]
    remaining = max(daily_kcal - reserved, daily_kcal * 0.3)
    weight_sum = sum(MEAL_WEIGHTS[k] for k in planned) or 1
    return {k: round(remaining * MEAL_WEIGHTS[k] / weight_sum) for k in planned}


def _shift(stock: Stock, days: int) -> Stock:
    return {iid: [StockLot(l.item_id, l.ingredient_id, l.quantity, l.days_left - days) for l in lots if l.days_left - days >= 0]
            for iid, lots in stock.items()}


def _consume(stock: Stock, recipe: Recipe, servings: int) -> None:
    for iid, req in aggregate_requirements([(recipe, servings)]).items():
        lots = stock.get(iid, [])
        for lot, used in allocate_fefo(lots, req.quantity):
            lot.quantity -= used
        stock[iid] = [l for l in lots if l.quantity > 1e-9]


def plan_week(
    *,
    days: list[date],
    meal_modes: dict[str, dict],
    recipes_by_slot: dict[str, list[Recipe]],
    stock: Stock,
    servings: int,
    daily_kcal: float,
    unit_prices: dict[int, float],
    weekly_budget: float | None,
    repeat_policy: str = "variety",
    seed: int = 0,
) -> WeekPlan:
    rng = random.Random(seed)
    targets = meal_targets(daily_kcal, meal_modes)
    slots = [m for m in ("breakfast", "lunch", "dinner", "snack") if meal_modes.get(m, {}).get("mode") == "plan"]
    total_meals = len(slots) * len(days) or 1
    per_meal_budget = (weekly_budget / total_meals) if weekly_budget else None

    sim = deepcopy(stock)
    used: Counter[int] = Counter()
    protein_used: Counter[str] = Counter()
    last_protein: dict[str, str] = {}
    last_day_used: dict[int, int] = {}
    plan = WeekPlan()
    batch_lunch: Recipe | None = None
    leftover_from: dict[str, PlannedMeal] = {}

    def cost_of(recipe: Recipe, day_stock: Stock, n: int) -> float:
        match = evaluate_recipe(recipe, day_stock, n)
        return sum(m.missing * unit_prices.get(m.ingredient.id, 0.0) for m in match.missing)

    for di, day in enumerate(days):
        today_ids: set[int] = set()
        day_stock = _shift(sim, di)
        for slot in slots:
            # Kalan yemek (balanced: dünkü öğle yemeği bugün tekrar)
            prev = leftover_from.pop(slot, None)
            if prev and repeat_policy == "balanced" and slot == "lunch":
                plan.meals.append(PlannedMeal(day, slot, prev.recipe, prev.servings // 2, is_leftover=True,
                                              kcal_per_serving=prev.kcal_per_serving))
                today_ids.add(prev.recipe.id)
                continue
            if repeat_policy == "batch" and slot == "lunch" and batch_lunch is not None:
                first = next(m for m in plan.meals if m.recipe is batch_lunch and not m.is_leftover)
                plan.meals.append(PlannedMeal(day, slot, batch_lunch, first.servings // len(days), is_leftover=True,
                                              kcal_per_serving=first.kcal_per_serving))
                continue

            candidates = recipes_by_slot.get(slot, [])
            best: tuple[float, PlannedMeal] | None = None
            batch_days = len(days) if (repeat_policy == "batch" and slot == "lunch") else 1
            for recipe in candidates:
                if recipe.id in today_ids:
                    continue
                # Havuz genişse aynı tarif haftada bir kez (tekrar isteyenler için kalan yemek mekanizması var)
                limit = 1 if len(candidates) >= 3 * len(days) else 2
                if used[recipe.id] >= limit or last_day_used.get(recipe.id) == di - 1:
                    continue
                base = evaluate_recipe(recipe, {}, recipe.servings)
                factor = portion_factor(base.per_serving.kcal, targets.get(slot))
                n = max(1, round(servings * factor)) * batch_days
                match = evaluate_recipe(recipe, day_stock, n, targets.get(slot))
                # Öğün başı kişi kalorisi (porsiyon çarpanıyla) hedefe ne kadar yakın?
                eaten = match.per_serving.kcal * n / batch_days / servings
                target = targets.get(slot)
                fit = max(0.0, 1 - abs(eaten - target) / target) if target else 0.5
                cost = sum(m.missing * unit_prices.get(m.ingredient.id, 0.0) for m in match.missing)
                score = 0.35 * match.coverage + 0.25 * match.urgency + 0.40 * fit
                if per_meal_budget:
                    score -= 0.35 * min(1.5, cost / (per_meal_budget * batch_days))
                pk = protein_key(recipe)
                if pk != "veg" and last_protein.get(slot) == pk:
                    score -= 0.12  # dün de aynı protein
                if pk != "veg":
                    score -= 0.06 * protein_used[pk]  # aynı protein türü haftada ne kadar çok, o kadar az tercih
                score += rng.uniform(0, 0.08)  # çeşitlilik için küçük rastgelelik (aynı tohum = aynı plan)
                if best is None or score > best[0]:
                    best = (score, PlannedMeal(day, slot, recipe, n, est_cost=round(cost, 2),
                                               kcal_per_serving=round(eaten)))
            if best is None:
                plan.warnings.append(f"{day.isoformat()} {slot}: kurallara uyan tarif bulunamadı")
                continue
            meal = best[1]
            plan.meals.append(meal)
            plan.est_cost += meal.est_cost
            used[meal.recipe.id] += 1
            last_day_used[meal.recipe.id] = di
            pk = protein_key(meal.recipe)
            protein_used[pk] += 1
            last_protein[slot] = pk
            today_ids.add(meal.recipe.id)
            _consume(sim, meal.recipe, meal.servings)
            day_stock = _shift(sim, di)
            # Toplu pişirme: ilk kayıt tüm günlerin porsiyonunu taşır (alışveriş ve envanter ondan hesaplanır),
            # sonraki günler "kalan yemek" olarak eklenir.
            if repeat_policy == "batch" and slot == "lunch":
                batch_lunch = meal.recipe
            if repeat_policy == "balanced" and slot == "lunch" and di + 1 < len(days):
                extra = meal.servings
                _consume(sim, meal.recipe, extra)  # ertesi günün payı da bugün pişer
                meal.est_cost = round(meal.est_cost + cost_of(meal.recipe, _shift(sim, di), extra), 2)
                meal.servings = extra * 2
                leftover_from[slot] = meal

    plan.est_cost = round(plan.est_cost, 2)
    if weekly_budget and plan.est_cost > weekly_budget:
        plan.warnings.append(f"Tahmini alışveriş ({plan.est_cost:.0f} ₺) bütçenin ({weekly_budget:.0f} ₺) üzerinde")
    return plan


def unit_price_table(offers: dict[int, list]) -> dict[int, float]:
    """Malzeme başına en ucuz birim fiyat (TL / temel birim) — bütçe tahmini için."""
    table: dict[int, float] = {}
    for iid, lst in offers.items():
        prices = [o.price / o.package_size for o in lst if o.package_size > 0]
        if prices:
            table[iid] = min(prices)
    return table


def by_slot(recipes: list[Recipe]) -> dict[str, list[Recipe]]:
    out: dict[str, list[Recipe]] = defaultdict(list)
    for slot, kinds in SLOT_RECIPE_TYPES.items():
        out[slot] = [r for r in recipes if r.meal_type.value in kinds]
    return out
