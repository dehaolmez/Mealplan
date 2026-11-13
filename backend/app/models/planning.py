from datetime import date, datetime

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.catalog import Ingredient
from app.models.enums import Category, MealType
from app.models.pricing import Store
from app.models.recipe import Recipe


class MealPlanEntry(Base):
    __tablename__ = "meal_plan_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(index=True)
    meal_type: Mapped[MealType] = mapped_column(Enum(MealType, native_enum=False))
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"))
    servings: Mapped[int] = mapped_column(default=2)
    cooked: Mapped[bool] = mapped_column(default=False)

    recipe: Mapped[Recipe] = relationship(lazy="joined")


class ShoppingItem(Base):
    """Alışveriş listesi kalemi. Katalogdaki bir malzemeye bağlı olabilir veya serbest metin olabilir."""

    __tablename__ = "shopping_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    ingredient_id: Mapped[int | None] = mapped_column(ForeignKey("ingredients.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[Category] = mapped_column(Enum(Category, native_enum=False), default=Category.other)
    quantity: Mapped[float | None]
    unit: Mapped[str | None] = mapped_column(String(10))
    note: Mapped[str] = mapped_column(String(200), default="")
    checked: Mapped[bool] = mapped_column(default=False)
    checked_at: Mapped[datetime | None]
    # Satın alınıp envantere aktarılan kalemler arşivlenir ("son alınanlar" listesini besler)
    archived: Mapped[bool] = mapped_column(default=False, index=True)
    store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id", ondelete="SET NULL"))
    estimated_price: Mapped[float | None]
    source: Mapped[str] = mapped_column(String(20), default="manual")  # manual | plan | recipe
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    ingredient: Mapped[Ingredient | None] = relationship(lazy="joined")
    store: Mapped[Store | None] = relationship(lazy="joined")
