from typing import Literal

from pydantic import BaseModel, Field

MealMode = Literal["plan", "skip", "own"]


class MealSetting(BaseModel):
    mode: MealMode = "plan"
    kcal: int = Field(default=0, ge=0, le=3000)     # "own": kendi hallettiği öğün için ayrılan kalori
    protein: int = Field(default=0, ge=0, le=300)


def default_meals() -> dict[str, MealSetting]:
    return {
        "breakfast": MealSetting(mode="plan"),
        "lunch": MealSetting(mode="plan"),
        "dinner": MealSetting(mode="plan"),
        "snack": MealSetting(mode="skip"),
    }


class PreferencesIn(BaseModel):
    preferred_chains: list[str] = []
    goals: list[Literal["lose", "muscle", "decide_less", "save_money", "family", "healthy"]] = []
    diet: Literal["none", "vegetarian", "vegan", "pescatarian"] = "none"
    low_carb: bool = False
    exclusions: list[Literal["pork", "red_meat", "gluten", "dairy", "egg", "nuts", "peanut", "fish", "shellfish",
                             "sesame", "soy"]] = []
    disliked_ingredient_ids: list[int] = []
    equipment: list[Literal["stovetop", "oven", "microwave", "airfryer", "blender", "grill", "pressure_cooker"]] = [
        "stovetop", "oven"]
    meals: dict[Literal["breakfast", "lunch", "dinner", "snack"], MealSetting] = Field(default_factory=default_meals)
    plan_days: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])
    weekly_budget: float | None = Field(default=None, ge=0, le=100_000)
    repeat_policy: Literal["variety", "balanced", "batch"] = "variety"
    meal_structure: Literal["main", "main_side", "full"] = "main_side"
    max_prep_minutes: int | None = Field(default=None, ge=5, le=480)
    onboarding_done: bool = True


class PreferencesOut(PreferencesIn):
    pass


class GenerateIn(BaseModel):
    start: str | None = Field(default=None, description="YYYY-AA-GG; boşsa bugün")
    days: int = Field(default=7, ge=1, le=14)
    replace: bool = True
    seed: int | None = None


class GeneratedMealOut(BaseModel):
    entry_id: int
    day: str
    meal_type: str
    recipe_id: int
    recipe_name: str
    servings: int
    is_leftover: bool
    est_cost: float
    kcal_per_serving: float
    course: str = "main"


class GenerateOut(BaseModel):
    meals: list[GeneratedMealOut]
    est_cost: float
    weekly_budget: float | None
    warnings: list[str]
    candidate_counts: dict[str, int]
    seed: int
