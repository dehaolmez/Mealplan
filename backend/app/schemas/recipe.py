from datetime import date

from pydantic import BaseModel, Field

from app.models.enums import MealType
from app.schemas.common import MacrosOut
from app.schemas.catalog import IngredientOut


class RecipeIngredientOut(BaseModel):
    ingredient: IngredientOut
    quantity: float
    quantity_label: str
    optional: bool


class RecipeOut(BaseModel):
    id: int
    name: str
    description: str
    instructions: str
    servings: int
    prep_minutes: int
    meal_type: MealType
    tags: list[str]
    equipment: list[str] = []
    source: str = "seed"
    own: bool = False  # hanenin kendi ürettiği tarif
    per_serving: MacrosOut
    ingredients: list[RecipeIngredientOut]


class MissingLineOut(BaseModel):
    ingredient: IngredientOut
    required: float
    available: float
    missing: float
    missing_label: str
    recipes: list[str]


class ExpiringUseOut(BaseModel):
    ingredient_name: str
    days_left: int


class RecommendationOut(BaseModel):
    recipe: RecipeOut
    servings: int
    score: float
    coverage: float
    urgency: float
    nutrition_fit: float
    uses_expiring: list[ExpiringUseOut]
    missing: list[MissingLineOut]
    ai_reason: str | None = None


class RecommendationsOut(BaseModel):
    ai_requested: bool
    ai_used: bool
    ai_error: str | None = None
    meal_kcal_target: float | None
    results: list[RecommendationOut]


class RecipeSelection(BaseModel):
    recipe_id: int
    servings: int | None = Field(default=None, ge=1, le=50)


class MissingRequest(BaseModel):
    selections: list[RecipeSelection] = []
    plan_from: date | None = None
    plan_to: date | None = None


class MissingOut(BaseModel):
    lines: list[MissingLineOut]
