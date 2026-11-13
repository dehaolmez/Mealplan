from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain import ai_planner
from app.domain.recommender import recommend
from app.domain.requirements import MissingLine, aggregate_requirements, find_missing
from app.domain.shelf_life import days_left
from app.domain.units import humanize
from app.models import Household, MealPlanEntry, Recipe
from app.models.enums import MealType
from app.schemas.recipe import RecipeSelection, RecommendationsOut
from app.services import clock, household_service, inventory_service
from app.services.errors import BadRequest, NotFound
from app.services.mappers import recommendation_out


def list_recipes(db: Session, meal_type: MealType | None = None, household: Household | None = None) -> list[Recipe]:
    """Ortak katalog + (varsa) hanenin kendi ürettiği tarifler. Başka hanelerin tarifleri asla dönmez."""
    owner = Recipe.household_id.is_(None)
    if household is not None:
        owner = or_(owner, Recipe.household_id == household.id)
    stmt = select(Recipe).where(owner).order_by(Recipe.name)
    if meal_type is not None:
        stmt = stmt.where(Recipe.meal_type == meal_type)
    return list(db.scalars(stmt))


def get_recipe(db: Session, recipe_id: int, household: Household | None = None) -> Recipe:
    recipe = db.get(Recipe, recipe_id)
    if recipe is None or (recipe.household_id is not None and (household is None or recipe.household_id != household.id)):
        raise NotFound("Tarif", recipe_id)
    return recipe


def recommendations(
    db: Session,
    household: Household,
    *,
    meal_type: MealType | None,
    servings: int | None,
    limit: int,
    use_ai: bool,
    ai_consent: bool = False,
) -> RecommendationsOut:
    stock = inventory_service.current_stock(db, household)
    targets = household_service.household_targets(db, household)
    servings = servings or (len(targets.members) or None)

    candidates = recommend(
        list_recipes(db, meal_type, household),
        stock,
        servings=servings,
        meal_kcal_target=targets.meal_kcal_target,
        # AI'ya daha geniş bir aday havuzu ver, o daraltsın
        limit=max(limit * 2, 12) if use_ai else limit,
    )

    settings = get_settings()
    ai_used, ai_error = False, None
    if use_ai and not settings.ai_available:
        ai_error = "Yapay zekâ yapılandırılmamış (API anahtarı yok); kural tabanlı sıralama kullanıldı."
    elif use_ai and not ai_consent:
        ai_error = "Yapay zekâ önerisi için Profil › Gizlilik bölümünden izin vermelisiniz; kural tabanlı sıralama kullanıldı."
    elif use_ai:
        today = clock.today()
        inventory_summary = [
            {
                "item": i.ingredient.name,
                "quantity": humanize(i.quantity, i.ingredient.base_unit),
                "location": i.location.value,
                "days_left": days_left(i.expiry_date, today),
            }
            for i in inventory_service.list_items(db, household)
        ]
        if settings.ai_provider == "gemini":
            result = ai_planner.rerank_with_gemini(candidates, inventory_summary=inventory_summary, limit=limit)
        else:
            result = ai_planner.rerank_with_claude(
                candidates,
                inventory_summary=inventory_summary,
                limit=limit,
                model=settings.ai_model,
                effort=settings.ai_effort,
            )
        candidates, ai_used, ai_error = result.matches, result.used, result.error

    return RecommendationsOut(
        ai_requested=use_ai,
        ai_used=ai_used,
        ai_error=ai_error,
        meal_kcal_target=targets.meal_kcal_target,
        results=[recommendation_out(m) for m in candidates[:limit]],
    )


def resolve_selections(
    db: Session,
    household: Household,
    selections: list[RecipeSelection],
    plan_from: date | None,
    plan_to: date | None,
) -> list[tuple[Recipe, int | None]]:
    """Açık tarif seçimleri ve/veya bir tarih aralığındaki (pişirilmemiş) plan kayıtlarını birleştirir."""
    resolved: list[tuple[Recipe, int | None]] = [(get_recipe(db, s.recipe_id, household), s.servings) for s in selections]
    if plan_from or plan_to:
        start = plan_from or plan_to
        end = plan_to or plan_from
        if start > end:
            raise BadRequest("plan_from, plan_to'dan sonra olamaz")
        entries = db.scalars(
            select(MealPlanEntry).where(
                MealPlanEntry.household_id == household.id,
                MealPlanEntry.day >= start,
                MealPlanEntry.day <= end,
                MealPlanEntry.cooked.is_(False),
                MealPlanEntry.status == "planned",
                MealPlanEntry.is_leftover.is_(False),
            )
        )
        resolved.extend((e.recipe, e.servings) for e in entries)
    if not resolved:
        raise BadRequest("En az bir tarif seçin veya plan tarih aralığı verin")
    return resolved


def missing_for(
    db: Session,
    household: Household,
    selections: list[RecipeSelection],
    plan_from: date | None = None,
    plan_to: date | None = None,
) -> list[MissingLine]:
    resolved = resolve_selections(db, household, selections, plan_from, plan_to)
    stock = inventory_service.current_stock(db, household)
    return find_missing(aggregate_requirements(resolved), stock)
