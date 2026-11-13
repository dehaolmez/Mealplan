from datetime import date

from sqlalchemy import Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.catalog import Ingredient
from app.models.enums import StorageLocation


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"), index=True)
    location: Mapped[StorageLocation] = mapped_column(Enum(StorageLocation, native_enum=False))
    # Miktar her zaman malzemenin temel biriminde (g / ml / adet) saklanır
    quantity: Mapped[float]
    added_on: Mapped[date]
    expiry_date: Mapped[date]
    # True: SKT etiketten değil, raf ömrü kurallarından tahmin edildi
    expiry_estimated: Mapped[bool] = mapped_column(default=False)
    opened: Mapped[bool] = mapped_column(default=False)

    ingredient: Mapped[Ingredient] = relationship(lazy="joined")
