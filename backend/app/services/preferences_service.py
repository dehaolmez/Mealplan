import json
import random
from datetime import date, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain import planner
from app.domain.diet import DietRules
from app.models import Chain, Household, HouseholdPreferences, MealPlanEntry, Recipe
from app.models.enums import MealType
from app.schemas.preferences import GeneratedMealOut, GenerateIn, GenerateOut, MealSetting, PreferencesIn, default_meals
from app.services import household_service, inventory_service, marketfiyati, pricing_service
from app.services.errors import BadRequest

DEFAULT_DAILY_KCAL = 2000


def _csv(values) -> str:
    return ",".join(str(v) for v in values)


def _split(text: str) -> list[str]:
    return [t for t in (text or "").split(",") if t]


def get(db: Session, household: Household) -> HouseholdPreferences:
    prefs = db.get(HouseholdPreferences, household.id)
    if prefs is None:
        prefs = HouseholdPreferences(household_id=household.id, meals_json=json.dumps(
            {k: v.model_dump() for k, v in default_meals().items()}))
        db.add(prefs)
        db.commit()
    return prefs


def to_schema(prefs: HouseholdPreferences) -> PreferencesIn:
    meals = default_meals()
    if prefs.meals_json:
        meals.update({k: MealSetting(**v) for k, v in json.loads(prefs.meals_json).items()})
    return PreferencesIn(
        preferred_chains=_split(prefs.preferred_chains), goals=_split(prefs.goals), diet=prefs.diet, low_carb=prefs.low_carb, exclusions=_split(prefs.exclusions),
        disliked_ingredient_ids=[int(x) for x in _split(prefs.disliked_ingredient_ids)],
        equipment=_split(prefs.equipment), meals=meals, plan_days=[int(x) for x in _split(prefs.plan_days)],
        weekly_budget=prefs.weekly_budget, repeat_policy=prefs.repeat_policy, max_prep_minutes=prefs.max_prep_minutes,
        onboarding_done=prefs.onboarding_done,
    )


def update(db: Session, household: Household, data: PreferencesIn) -> HouseholdPreferences:
    if not any(m.mode == "plan" for m in data.meals.values()):
        raise BadRequest("En az bir öğün planlanmalı")
    if not data.plan_days or any(d < 0 or d > 6 for d in data.plan_days):
        raise BadRequest("Planlanacak günleri seçin")
    prefs = get(db, household)
    known = {c.slug for c in db.scalars(select(Chain))}
    unknown = set(data.preferred_chains) - known
    if unknown:
        raise BadRequest(f"Bilinmeyen zincir: {sorted(unknown)}")
    prefs.preferred_chains = _csv(sorted(set(data.preferred_chains)))
    prefs.goals, prefs.diet, prefs.low_carb = _csv(data.goals), data.diet, data.low_carb
    prefs.exclusions = _csv(sorted(set(data.exclusions)))
    prefs.disliked_ingredient_ids = _csv(sorted(set(data.disliked_ingredient_ids)))
    prefs.equipment = _csv(sorted(set(data.equipment) or {"stovetop"}))
    prefs.meals_json = json.dumps({k: v.model_dump() for k, v in data.meals.items()})
    prefs.plan_days = _csv(sorted(set(data.plan_days)))
    prefs.weekly_budget, prefs.repeat_policy = data.weekly_budget, data.repeat_policy
    prefs.max_prep_minutes, prefs.onboarding_done = data.max_prep_minutes, data.onboarding_done
    db.commit()
    return prefs


def rules_for(data: PreferencesIn) -> DietRules:
    return DietRules(diet=data.diet, low_carb=data.low_carb, exclusions=set(data.exclusions),
                     disliked=set(data.disliked_ingredient_ids), equipment=set(data.equipment) or {"stovetop"},
                     max_prep_minutes=data.max_prep_minutes)


def visible_recipes(db: Session, household: Household) -> list[Recipe]:
    """Ortak katalog + hanenin kendi (ör. Gemini ile ürettiği) tarifleri."""
    return list(db.scalars(select(Recipe).where(
        or_(Recipe.household_id.is_(None), Recipe.household_id == household.id))))


def generate_week(db: Session, household: Household, req: GenerateIn) -> GenerateOut:
    data = to_schema(get(db, household))
    rules = rules_for(data)
    start = date.fromisoformat(req.start) if req.start else date.today()
    days = [start + timedelta(days=i) for i in range(req.days) if (start + timedelta(days=i)).weekday() in data.plan_days]
    if not days:
        raise BadRequest("Seçilen aralıkta planlanacak gün yok")

    from app.domain.diet import allowed

    all_recipes = visible_recipes(db, household)
    slots = {}
    for slot, kinds in planner.SLOT_RECIPE_TYPES.items():
        slots[slot] = allowed([r for r in all_recipes if r.meal_type.value in kinds], rules, slot)

    targets = household_service.household_targets(db, household)
    members = max(1, len(targets.members))
    daily = (targets.total.calories / members) if targets.total else DEFAULT_DAILY_KCAL

    # Bütçe tahmini için birim fiyatlar (canlı fiyat varsa o bölge, yoksa demo/CSV)
    s = get_settings()
    area = None
    if s.live_prices_enabled:
        lat = household.home_lat if household.home_lat is not None else s.pilot_lat
        lon = household.home_lon if household.home_lon is not None else s.pilot_lon
        area = marketfiyati.area_key(lat, lon, s.live_prices_radius_km)
    ing_ids = {line.ingredient_id for r in all_recipes for line in r.ingredients}
    unit_prices = planner.unit_price_table(pricing_service.offers_for(db, list(ing_ids), area))

    seed = req.seed if req.seed is not None else random.randrange(1_000_000)
    week = planner.plan_week(
        days=days, meal_modes={k: v.model_dump() for k, v in data.meals.items()}, recipes_by_slot=slots,
        stock=inventory_service.current_stock(db, household), servings=members, daily_kcal=daily,
        unit_prices=unit_prices, weekly_budget=data.weekly_budget, repeat_policy=data.repeat_policy, seed=seed,
    )

    planned_slots = [MealType(k) for k, v in data.meals.items() if v.mode == "plan"]
    if req.replace:  # yalnız henüz pişirilmemiş/işaretlenmemiş kayıtlar değişir
        for e in db.scalars(select(MealPlanEntry).where(
                MealPlanEntry.household_id == household.id, MealPlanEntry.day.in_(days),
                MealPlanEntry.meal_type.in_(planned_slots), MealPlanEntry.status == "planned")):
            db.delete(e)
        db.flush()

    out = []
    for m in week.meals:
        entry = MealPlanEntry(household_id=household.id, day=m.day, meal_type=MealType(m.meal_type),
                              recipe_id=m.recipe.id, servings=m.servings, is_leftover=m.is_leftover,
                              auto_generated=True)
        db.add(entry)
        db.flush()
        out.append(GeneratedMealOut(entry_id=entry.id, day=m.day.isoformat(), meal_type=m.meal_type,
                                    recipe_id=m.recipe.id, recipe_name=m.recipe.name, servings=m.servings,
                                    is_leftover=m.is_leftover, est_cost=m.est_cost, kcal_per_serving=m.kcal_per_serving))
    db.commit()
    return GenerateOut(meals=out, est_cost=week.est_cost, weekly_budget=data.weekly_budget, warnings=week.warnings,
                       candidate_counts={k: len(v) for k, v in slots.items() if data.meals[k].mode == "plan"}, seed=seed)


def preferred_chain_ids(db: Session, household: Household) -> set[int] | None:
    prefs = db.get(HouseholdPreferences, household.id)
    slugs = set(_split(prefs.preferred_chains)) if prefs else set()
    if not slugs:
        return None
    return {c.id for c in db.scalars(select(Chain).where(Chain.slug.in_(slugs)))}
