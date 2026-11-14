"""ORM nesnelerini API şemalarına dönüştüren yardımcılar."""

from datetime import date

from app.domain.recommender import RecipeMatch, recipe_macros_per_serving
from app.domain.requirements import MissingLine
from app.domain.shelf_life import classify, days_left
from app.domain.units import humanize
from app.core.config import get_settings
from app.models import InventoryItem, Recipe, ShoppingItem
from app.schemas.catalog import IngredientOut
from app.schemas.common import MacrosOut
from app.schemas.inventory import InventoryItemOut
from app.schemas.planning import ShoppingItemOut
from app.schemas.recipe import (
    ExpiringUseOut,
    MissingLineOut,
    RecipeIngredientOut,
    RecipeOut,
    RecommendationOut,
)


def inventory_out(item: InventoryItem, today: date) -> InventoryItemOut:
    s = get_settings()
    return InventoryItemOut(
        id=item.id,
        ingredient=IngredientOut.model_validate(item.ingredient),
        location=item.location,
        quantity=round(item.quantity, 2),
        quantity_label=humanize(item.quantity, item.ingredient.base_unit),
        added_on=item.added_on,
        expiry_date=item.expiry_date,
        expiry_estimated=item.expiry_estimated,
        opened=item.opened,
        days_left=days_left(item.expiry_date, today),
        status=classify(item.expiry_date, today, s.expiry_critical_days, s.expiry_warning_days),
    )


def recipe_out(recipe: Recipe) -> RecipeOut:
    macros = recipe_macros_per_serving(recipe)
    return RecipeOut(
        id=recipe.id,
        name=recipe.name,
        description=recipe.description,
        instructions=recipe.instructions,
        servings=recipe.servings,
        prep_minutes=recipe.prep_minutes,
        meal_type=recipe.meal_type,
        tags=[t for t in recipe.tags.split(",") if t],
        equipment=[t for t in (recipe.equipment or "").split(",") if t],
        source=recipe.source or "seed",
        course=recipe.course or "main",
        own=recipe.household_id is not None,
        per_serving=MacrosOut(**macros.__dict__),
        ingredients=[
            RecipeIngredientOut(
                ingredient=IngredientOut.model_validate(line.ingredient),
                quantity=line.quantity,
                quantity_label=humanize(line.quantity, line.ingredient.base_unit),
                optional=line.optional,
            )
            for line in recipe.ingredients
        ],
    )


def missing_out(line: MissingLine) -> MissingLineOut:
    unit = line.ingredient.base_unit
    return MissingLineOut(
        ingredient=IngredientOut.model_validate(line.ingredient),
        required=round(line.required, 2),
        available=round(line.available, 2),
        missing=round(line.missing, 2),
        missing_label=humanize(line.missing, unit),
        recipes=line.recipes,
    )


def recommendation_out(match: RecipeMatch) -> RecommendationOut:
    return RecommendationOut(
        recipe=recipe_out(match.recipe),
        servings=match.servings,
        score=match.score,
        coverage=match.coverage,
        urgency=match.urgency,
        nutrition_fit=match.nutrition_fit,
        uses_expiring=[ExpiringUseOut(ingredient_name=e.ingredient_name, days_left=e.days_left) for e in match.uses_expiring],
        missing=[missing_out(m) for m in match.missing],
        ai_reason=match.ai_reason,
    )


def shopping_item_out(item: ShoppingItem) -> ShoppingItemOut:
    return ShoppingItemOut(
        id=item.id,
        ingredient_id=item.ingredient_id,
        name=item.name,
        emoji=item.ingredient.emoji if item.ingredient else "🛒",
        category=item.category,
        quantity=item.quantity,
        unit=item.unit,
        note=item.note,
        checked=item.checked,
        checked_at=item.checked_at,
        store_id=item.store_id,
        store_name=item.store.name if item.store else None,
        estimated_price=item.estimated_price,
        source=item.source,
    )
