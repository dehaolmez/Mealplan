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
    course: str = "main"


@dataclass
class WeekPlan:
    meals: list[PlannedMeal] = field(default_factory=list)
    est_cost: float = 0.0
    warnings: list[str] = field(default_factory=list)


# Menüdeki yan tabakların öğün kalorisinden aldığı pay (geri kalanı ana yemeğin)
COURSE_SHARE = {"soup": 0.15, "side": 0.25, "salad": 0.10}
EXTRA_REPEAT_LIMIT = 2  # yan tabaklar haftada en fazla iki kez


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


def has_carb(recipe: Recipe) -> bool:
    from app.domain.diet import tags_of

    return any("carb" in tags_of(l.ingredient.diet_tags) for l in recipe.ingredients if not l.optional)


def menu_courses(structure: str, main: Recipe) -> list[str]:
    """Ana yemeğin yanına eklenecek tabaklar."""
    if structure == "main":
        return []
    extra = ["salad"] if has_carb(main) else ["side"]
    if structure == "full":
        extra = ["soup"] + (["salad"] if has_carb(main) else ["side", "salad"])
    return extra


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
    meal_structure: str = "main",
    extras: dict[str, list[Recipe]] | None = None,
) -> WeekPlan:
    """recipes_by_slot: öğün başına ana tabak adayları; extras: "soup"/"side"/"salad" adayları."""
    rng = random.Random(seed)
    extras = extras or {}
    targets = meal_targets(daily_kcal, meal_modes)
    slots = [m for m in ("breakfast", "lunch", "dinner", "snack") if meal_modes.get(m, {}).get("mode") == "plan"]
    total_meals = len(slots) * len(days) or 1
    per_meal_budget = (weekly_budget / total_meals) if weekly_budget else None

    sim = deepcopy(stock)
    used: Counter[int] = Counter()
    last_day_used: dict[int, int] = {}
    protein_used: Counter[str] = Counter()
    last_protein: dict[str, str] = {}
    plan = WeekPlan()
    batch_lunch: Recipe | None = None
    leftover_from: dict[str, PlannedMeal] = {}

    def cost_of(recipe: Recipe, day_stock: Stock, n: int) -> float:
        match = evaluate_recipe(recipe, day_stock, n)
        return sum(m.missing * unit_prices.get(m.ingredient.id, 0.0) for m in match.missing)

    def pick(pool: list[Recipe], *, day: date, di: int, slot: str, target: float | None, day_stock: Stock,
             exclude: set[int], batch_days: int, limit: int, budget_share: float, use_protein: bool) -> PlannedMeal | None:
        best: tuple[float, PlannedMeal] | None = None
        for recipe in pool:
            if recipe.id in exclude or used[recipe.id] >= limit or last_day_used.get(recipe.id) == di - 1:
                continue
            base = evaluate_recipe(recipe, {}, recipe.servings)
            factor = portion_factor(base.per_serving.kcal, target)
            n = max(1, round(servings * factor)) * batch_days
            match = evaluate_recipe(recipe, day_stock, n, target)
            eaten = match.per_serving.kcal * n / batch_days / servings
            fit = max(0.0, 1 - abs(eaten - target) / target) if target else 0.5
            cost = sum(m.missing * unit_prices.get(m.ingredient.id, 0.0) for m in match.missing)
            score = 0.35 * match.coverage + 0.25 * match.urgency + 0.40 * fit
            if per_meal_budget:
                score -= 0.35 * min(1.5, cost / (per_meal_budget * budget_share * batch_days))
            if use_protein:
                pk = protein_key(recipe)
                if pk != "veg" and last_protein.get(slot) == pk:
                    score -= 0.12
                if pk != "veg":
                    score -= 0.06 * protein_used[pk]
            score += rng.uniform(0, 0.08)  # çeşitlilik için küçük rastgelelik (aynı tohum = aynı plan)
            if best is None or score > best[0]:
                best = (score, PlannedMeal(day, slot, recipe, n, est_cost=round(cost, 2), kcal_per_serving=round(eaten)))
        return best[1] if best else None

    def commit(meal: PlannedMeal, di: int, today_ids: set[int]) -> None:
        plan.meals.append(meal)
        plan.est_cost += meal.est_cost
        used[meal.recipe.id] += 1
        last_day_used[meal.recipe.id] = di
        today_ids.add(meal.recipe.id)
        _consume(sim, meal.recipe, meal.servings)

    for di, day in enumerate(days):
        today_ids: set[int] = set()
        for slot in slots:
            day_stock = _shift(sim, di)
            target = targets.get(slot)
            main: PlannedMeal | None = None

            # Kalan yemek (balanced: dünkü öğle yemeği bugün tekrar) / toplu pişirme
            prev = leftover_from.pop(slot, None)
            if prev and repeat_policy == "balanced" and slot == "lunch":
                main = PlannedMeal(day, slot, prev.recipe, prev.servings // 2, is_leftover=True,
                                   kcal_per_serving=prev.kcal_per_serving)
                plan.meals.append(main)
                today_ids.add(prev.recipe.id)
            elif repeat_policy == "batch" and slot == "lunch" and batch_lunch is not None:
                first = next(m for m in plan.meals if m.recipe is batch_lunch and not m.is_leftover)
                main = PlannedMeal(day, slot, batch_lunch, first.servings // len(days), is_leftover=True,
                                   kcal_per_serving=first.kcal_per_serving)
                plan.meals.append(main)
            else:
                candidates = recipes_by_slot.get(slot, [])
                # Havuz genişse aynı tarif haftada bir kez (tekrar isteyenler için kalan yemek mekanizması var)
                limit = 1 if len(candidates) >= 3 * len(days) else 2
                batch_days = len(days) if (repeat_policy == "batch" and slot == "lunch") else 1
                courses_for_target = 1.0
                if slot in ("lunch", "dinner") and meal_structure != "main":
                    # yan tabakların payı düşülmüş ana yemek hedefi (yaklaşık; karbonhidrat durumuna göre değişir)
                    courses_for_target = 1 - (0.25 if meal_structure == "main_side" else 0.45)
                main = pick(candidates, day=day, di=di, slot=slot,
                            target=target * courses_for_target if target else None, day_stock=day_stock,
                            exclude=today_ids, batch_days=batch_days, limit=limit, budget_share=courses_for_target,
                            use_protein=True)
                if main is None:
                    plan.warnings.append(f"{day.isoformat()} {slot}: kurallara uyan tarif bulunamadı")
                    continue
                commit(main, di, today_ids)
                pk = protein_key(main.recipe)
                protein_used[pk] += 1
                last_protein[slot] = pk
                if repeat_policy == "batch" and slot == "lunch":
                    batch_lunch = main.recipe
                if repeat_policy == "balanced" and slot == "lunch" and di + 1 < len(days):
                    extra = main.servings
                    extra_cost = cost_of(main.recipe, _shift(sim, di), extra)
                    _consume(sim, main.recipe, extra)  # ertesi günün payı da bugün pişer
                    main.est_cost = round(main.est_cost + extra_cost, 2)
                    plan.est_cost += extra_cost
                    main.servings = extra * 2
                    leftover_from[slot] = main

            # Menü: çorba / yan yemek / salata
            if slot in ("lunch", "dinner") and main is not None:
                for course in menu_courses(meal_structure, main.recipe):
                    pool = extras.get(course, [])
                    share = COURSE_SHARE[course]
                    extra_meal = pick(pool, day=day, di=di, slot=slot, target=target * share if target else None,
                                      day_stock=_shift(sim, di), exclude=today_ids, batch_days=1,
                                      limit=EXTRA_REPEAT_LIMIT, budget_share=share, use_protein=False)
                    if extra_meal is not None:
                        extra_meal.course = course
                        commit(extra_meal, di, today_ids)

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


MAIN_COURSES = {"breakfast": {"breakfast"}, "lunch": {"main"}, "dinner": {"main"}, "snack": {"snack", "salad"}}


def by_slot(recipes: list[Recipe]) -> dict[str, list[Recipe]]:
    """Öğün başına ana tabak adayları (öğle/akşam: ana yemekler; kahvaltı: kahvaltılıklar)."""
    out: dict[str, list[Recipe]] = defaultdict(list)
    for slot, kinds in SLOT_RECIPE_TYPES.items():
        out[slot] = [r for r in recipes if r.meal_type.value in kinds and r.course in MAIN_COURSES[slot]]
    out["breakfast"] = [r for r in recipes if r.course == "breakfast"]
    return out


def extras_by_course(recipes: list[Recipe]) -> dict[str, list[Recipe]]:
    return {c: [r for r in recipes if r.course == c] for c in ("soup", "side", "salad")}
