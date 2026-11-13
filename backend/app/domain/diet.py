"""Diyet, alerji, sevilmeyen malzeme ve mutfak aleti filtreleri."""

from collections.abc import Iterable
from dataclasses import dataclass, field

from app.models.recipe import Recipe

ANIMAL_FLESH = {"red_meat", "poultry", "fish", "shellfish", "pork"}
DIET_FORBIDS: dict[str, set[str]] = {
    "none": set(),
    "vegetarian": ANIMAL_FLESH,
    "vegan": ANIMAL_FLESH | {"dairy", "egg", "honey"},
    "pescatarian": {"red_meat", "poultry", "pork"},
}
EXCLUSION_TAGS = {"pork", "red_meat", "gluten", "dairy", "egg", "nuts", "peanut", "fish", "shellfish", "sesame", "soy"}


@dataclass
class DietRules:
    diet: str = "none"
    low_carb: bool = False
    exclusions: set[str] = field(default_factory=set)
    disliked: set[int] = field(default_factory=set)
    equipment: set[str] = field(default_factory=lambda: {"stovetop", "oven"})
    max_prep_minutes: int | None = None

    @property
    def forbidden_tags(self) -> set[str]:
        return DIET_FORBIDS.get(self.diet, set()) | (self.exclusions & EXCLUSION_TAGS)


def tags_of(text: str) -> set[str]:
    return {t for t in (text or "").split(",") if t}


def recipe_violations(recipe: Recipe, rules: DietRules, meal_type: str | None = None) -> list[str]:
    """Tarifin kurallara aykırılıklarını döner (boş liste = uygun). İsteğe bağlı malzemeler engel sayılmaz."""
    problems: list[str] = []
    forbidden = rules.forbidden_tags
    for line in recipe.ingredients:
        if line.optional:
            continue
        ing = line.ingredient
        hit = tags_of(ing.diet_tags) & forbidden
        if hit:
            problems.append(f"{ing.name} ({', '.join(sorted(hit))})")
        if ing.id in rules.disliked:
            problems.append(f"{ing.name} (sevilmiyor)")
        if rules.low_carb and meal_type in ("lunch", "dinner") and "carb" in tags_of(ing.diet_tags):
            problems.append(f"{ing.name} (düşük karbonhidrat)")
    needed = tags_of(recipe.equipment) - {"none"}
    missing_eq = needed - rules.equipment
    if missing_eq:
        problems.append("alet: " + ", ".join(sorted(missing_eq)))
    if rules.max_prep_minutes and recipe.prep_minutes > rules.max_prep_minutes:
        problems.append("süre")
    return problems


def allowed(recipes: Iterable[Recipe], rules: DietRules, meal_type: str | None = None) -> list[Recipe]:
    return [r for r in recipes if not recipe_violations(r, rules, meal_type)]
