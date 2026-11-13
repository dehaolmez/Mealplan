from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.catalog import Ingredient
from app.models.enums import MealType


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    instructions: Mapped[str] = mapped_column(Text, default="")
    servings: Mapped[int] = mapped_column(default=2)
    prep_minutes: Mapped[int] = mapped_column(default=30)
    meal_type: Mapped[MealType] = mapped_column(Enum(MealType, native_enum=False), default=MealType.dinner)
    tags: Mapped[str] = mapped_column(String(200), default="")  # "vejetaryen,pratik"
    # Gereken mutfak aletleri (virgüllü): stovetop, oven, microwave, airfryer, blender, grill, pressure_cooker
    equipment: Mapped[str] = mapped_column(String(120), default="stovetop")
    source: Mapped[str] = mapped_column(String(20), default="seed")  # seed | gemini | user
    # Kullanıcının Gemini ile ürettiği tarifler yalnız kendi hanesine görünür (None = herkese açık katalog)
    household_id: Mapped[int | None] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)

    ingredients: Mapped[list["RecipeIngredient"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan", lazy="selectin"
    )


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), index=True)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"))
    quantity: Mapped[float]  # malzemenin temel biriminde, tarifin `servings` porsiyonu için
    optional: Mapped[bool] = mapped_column(default=False)

    recipe: Mapped[Recipe] = relationship(back_populates="ingredients")
    ingredient: Mapped[Ingredient] = relationship(lazy="joined")
