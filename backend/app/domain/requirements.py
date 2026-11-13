"""Tarif ihtiyaçlarının toplanması ve envanterle kıyaslanarak eksiklerin bulunması."""

from collections.abc import Iterable
from dataclasses import dataclass

from app.domain.stock import Stock, available
from app.models.catalog import Ingredient
from app.models.recipe import Recipe

EPSILON = 1e-6


@dataclass
class Requirement:
    ingredient: Ingredient
    quantity: float  # temel birimde
    recipes: list[str]


@dataclass
class MissingLine:
    ingredient: Ingredient
    required: float
    available: float
    missing: float
    recipes: list[str]


def scale_factor(recipe: Recipe, servings: int | None) -> float:
    if not servings or recipe.servings <= 0:
        return 1.0
    return servings / recipe.servings


def aggregate_requirements(
    selections: Iterable[tuple[Recipe, int | None]], include_optional: bool = False
) -> dict[int, Requirement]:
    """Birden çok tarifin (porsiyona göre ölçeklenmiş) malzeme ihtiyaçlarını tek listede toplar."""
    totals: dict[int, Requirement] = {}
    for recipe, servings in selections:
        factor = scale_factor(recipe, servings)
        for line in recipe.ingredients:
            if line.optional and not include_optional:
                continue
            req = totals.get(line.ingredient_id)
            if req is None:
                req = totals[line.ingredient_id] = Requirement(line.ingredient, 0.0, [])
            req.quantity += line.quantity * factor
            if recipe.name not in req.recipes:
                req.recipes.append(recipe.name)
    return totals


def find_missing(requirements: dict[int, Requirement], stock: Stock) -> list[MissingLine]:
    """Gereken - mevcut > 0 olan malzemeleri döner. Temel (staple) ürünler evde var kabul edilir."""
    missing: list[MissingLine] = []
    for ingredient_id, req in requirements.items():
        if req.ingredient.is_staple:
            continue
        have = available(stock, ingredient_id)
        deficit = req.quantity - have
        if deficit > EPSILON:
            missing.append(MissingLine(req.ingredient, req.quantity, have, deficit, list(req.recipes)))
    missing.sort(key=lambda m: (m.ingredient.category.value, m.ingredient.name))
    return missing
