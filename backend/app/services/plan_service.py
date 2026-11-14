from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.recommender import recipe_macros_per_serving
from app.domain.requirements import aggregate_requirements
from app.domain.units import humanize
from app.models import Household, MealPlanEntry
from app.schemas.planning import CookOut, MealPlanIn, MealPlanOut
from app.services import inventory_service, recipe_service
from app.services.errors import BadRequest, NotFound


def entry_out(entry: MealPlanEntry) -> MealPlanOut:
    return MealPlanOut(
        id=entry.id,
        day=entry.day,
        meal_type=entry.meal_type,
        recipe_id=entry.recipe_id,
        recipe_name=entry.recipe.name,
        servings=entry.servings,
        cooked=entry.cooked,
        status=entry.status,
        is_leftover=entry.is_leftover,
        auto_generated=entry.auto_generated,
        course=entry.recipe.course,
        kcal_per_serving=recipe_macros_per_serving(entry.recipe).kcal,
    )


def list_entries(db: Session, household: Household, start: date, end: date) -> list[MealPlanEntry]:
    return list(
        db.scalars(
            select(MealPlanEntry)
            .where(MealPlanEntry.household_id == household.id, MealPlanEntry.day >= start, MealPlanEntry.day <= end)
            .order_by(MealPlanEntry.day, MealPlanEntry.meal_type)
        )
    )


def add_entry(db: Session, household: Household, data: MealPlanIn) -> MealPlanEntry:
    recipe_service.get_recipe(db, data.recipe_id, household)
    entry = MealPlanEntry(household_id=household.id, **data.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def _get(db: Session, household: Household, entry_id: int) -> MealPlanEntry:
    entry = db.get(MealPlanEntry, entry_id)
    if entry is None or entry.household_id != household.id:
        raise NotFound("Plan kaydı", entry_id)
    return entry


def delete_entry(db: Session, household: Household, entry_id: int) -> None:
    db.delete(_get(db, household, entry_id))
    db.commit()


def cook(db: Session, household: Household, entry_id: int) -> CookOut:
    """Tarifi pişirildi olarak işaretler ve malzemeleri envanterden (FEFO) düşer."""
    entry = _get(db, household, entry_id)
    if entry.cooked:
        raise BadRequest("Bu öğün zaten pişirildi olarak işaretli")
    if entry.is_leftover:  # kalan yemek: malzemeler ilk pişirmede düşüldü
        entry.cooked, entry.status = True, "cooked"
        db.commit()
        return CookOut(entry_id=entry.id, consumed=[], shortages=[])
    consumed, shortages = [], []
    for ingredient_id, req in aggregate_requirements([(entry.recipe, entry.servings)]).items():
        if req.ingredient.is_staple:
            continue
        short = inventory_service.consume(db, household, ingredient_id, req.quantity)
        used = req.quantity - short
        unit = req.ingredient.base_unit
        if used > 0:
            consumed.append(f"{req.ingredient.name}: {humanize(used, unit)}")
        if short > 1e-6:
            shortages.append(f"{req.ingredient.name}: {humanize(short, unit)} eksikti")
    entry.cooked, entry.status = True, "cooked"
    db.commit()
    return CookOut(entry_id=entry.id, consumed=consumed, shortages=shortages)


def set_status(db: Session, household: Household, entry_id: int, status: str) -> MealPlanEntry:
    """Öğünü "yapılmadı" / "dışarıda yendi" olarak işaretler (veya geri alır). Pişirilmiş öğün değiştirilemez."""
    entry = _get(db, household, entry_id)
    if entry.cooked:
        raise BadRequest("Pişirilmiş öğünün durumu değiştirilemez")
    entry.status = status
    db.commit()
    return entry
