from app.models.enums import BaseUnit, Category
from app.schemas.common import ORMModel


class IngredientOut(ORMModel):
    id: int
    name: str
    category: Category
    base_unit: BaseUnit
    emoji: str
    is_staple: bool
    grams_per_piece: float | None
    shelf_life_fridge_days: int | None
    shelf_life_freezer_days: int | None
    shelf_life_opened_days: int | None
