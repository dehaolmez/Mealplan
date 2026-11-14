from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import BaseUnit, Category


class Ingredient(Base):
    """Malzeme kataloğu: birim, reyon, besin değeri ve ortalama raf ömrü kuralları."""

    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    category: Mapped[Category] = mapped_column(Enum(Category, native_enum=False))
    base_unit: Mapped[BaseUnit] = mapped_column(Enum(BaseUnit, native_enum=False))
    # "adet" ile ölçülen ürünlerin gram karşılığı (besin hesabı ve g<->adet dönüşümü için)
    grams_per_piece: Mapped[float | None]
    # ml ile ölçülen ürünlerin yoğunluğu (g/ml); boşsa 1 kabul edilir
    density_g_per_ml: Mapped[float | None]

    # 100 g başına besin değerleri
    kcal_per_100g: Mapped[float] = mapped_column(default=0)
    protein_per_100g: Mapped[float] = mapped_column(default=0)
    carbs_per_100g: Mapped[float] = mapped_column(default=0)
    fat_per_100g: Mapped[float] = mapped_column(default=0)

    # Ortalama raf ömrü kuralları (gün). SKT etiketi olmayan ürünler için tahmin kaynağı.
    shelf_life_fridge_days: Mapped[int | None]
    shelf_life_freezer_days: Mapped[int | None]
    shelf_life_opened_days: Mapped[int | None]

    # Tuz, karabiber, su gibi "her evde var" kabul edilen temel ürünler eksik listesine girmez
    is_staple: Mapped[bool] = mapped_column(default=False)
    # Diyet/alerjen etiketleri (virgüllü): red_meat, poultry, fish, shellfish, pork, dairy, egg, gluten, nuts,
    # peanut, sesame, soy, honey, carb. Vejetaryen/vegan/pesketaryen uygunluğu bunlardan türetilir.
    diet_tags: Mapped[str] = mapped_column(String(120), default="")
    emoji: Mapped[str] = mapped_column(String(8), default="🛒")
