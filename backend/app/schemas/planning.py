from datetime import date, datetime

from typing import Literal

from pydantic import BaseModel, Field

from app.domain.price_optimizer import Strategy
from app.models.enums import Category, MealType
from app.schemas.recipe import RecipeSelection


class MealPlanIn(BaseModel):
    day: date
    meal_type: MealType = MealType.dinner
    recipe_id: int
    servings: int = Field(default=2, ge=1, le=50)


class MealPlanOut(BaseModel):
    id: int
    day: date
    meal_type: MealType
    recipe_id: int
    recipe_name: str
    servings: int
    cooked: bool
    status: str = "planned"
    is_leftover: bool = False
    auto_generated: bool = False
    kcal_per_serving: float


class StatusIn(BaseModel):
    status: Literal["planned", "skipped", "ate_out"]


class CookOut(BaseModel):
    entry_id: int
    consumed: list[str]
    shortages: list[str]


class StoreOut(BaseModel):
    id: int
    name: str
    color: str
    chain_id: int | None = None
    is_demo: bool = False


class OptimizeRequest(BaseModel):
    selections: list[RecipeSelection] = []
    plan_from: date | None = None
    plan_to: date | None = None
    strategy: Strategy = Strategy.cheapest
    store_ids: list[int] | None = Field(default=None, description="Boşsa hanenin seçili marketleri")
    add_to_list: bool = False
    nearby_only: bool = Field(
        default=False,
        description="Yalnız ev konumuna (veya lat/lon'a) yakın şubesi olan zincirlerin fiyatlarını kullan",
    )
    lat: float | None = None
    lon: float | None = None
    radius_m: int | None = Field(default=None, ge=200, le=10_000)
    live_prices: bool = Field(default=True, description="Konum için Market Fiyatı'ndan canlı fiyat çek")


class PurchaseOut(BaseModel):
    ingredient_id: int
    name: str
    emoji: str
    category: Category
    missing_label: str
    store_id: int | None
    store_name: str | None
    brand: str | None
    package_label: str | None
    packages: int
    cost: float


class StoreTotalOut(BaseModel):
    store_id: int
    store_name: str
    total: float
    available_items: int
    missing_items: list[str]


class OptimizeOut(BaseModel):
    strategy: Strategy
    chosen_store_id: int | None
    total: float
    unavailable: list[str]
    purchases: list[PurchaseOut]
    store_totals: list[StoreTotalOut]
    savings_vs_worst_single_store: float | None
    added_to_list: int
    # "live": Market Fiyatı canlı verisi · "real": içe aktarılmış gerçek fiyat · "demo": örnek fiyat
    price_mode: str = "demo"
    price_note: str | None = None


class ShoppingItemIn(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    ingredient_id: int | None = None
    quantity: float | None = Field(default=None, gt=0)
    unit: str | None = None
    note: str = ""


class ShoppingItemUpdate(BaseModel):
    quantity: float | None = Field(default=None, gt=0)
    unit: str | None = None
    note: str | None = None
    checked: bool | None = None
    store_id: int | None = None


class ShoppingItemOut(BaseModel):
    id: int
    ingredient_id: int | None
    name: str
    emoji: str
    category: Category
    quantity: float | None
    unit: str | None
    note: str
    checked: bool
    checked_at: datetime | None
    store_id: int | None
    store_name: str | None
    estimated_price: float | None
    source: str


class ShoppingCategoryOut(BaseModel):
    category: Category
    items: list[ShoppingItemOut]


class ShoppingListOut(BaseModel):
    open_count: int
    estimated_total: float
    categories: list[ShoppingCategoryOut]
    recently_bought: list[ShoppingItemOut]


class CheckoutOut(BaseModel):
    moved_to_inventory: int
    cleared: int
