from datetime import date

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.catalog import Ingredient
from app.models.chain import Chain


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    color: Mapped[str] = mapped_column(String(9), default="#64748b")
    # Fiyat listesi gerçek bir zincire aitse bağlanır (konum filtresi bunu kullanır)
    chain_id: Mapped[int | None] = mapped_column(ForeignKey("chains.id", ondelete="SET NULL"), index=True)
    # Demo (hayali) market mi? Gerçek fiyat verisi gelince False olan kayıtlar oluşur.
    is_demo: Mapped[bool] = mapped_column(default=False)

    chain: Mapped[Chain | None] = relationship(lazy="joined")


class StorePrice(Base):
    """Bir marketin bir malzeme için sattığı paket ve fiyatı.

    Fiyat kaynağı (seed, CSV içe aktarma, ileride market API'leri) `source` alanında tutulur.
    """

    __tablename__ = "store_prices"
    __table_args__ = (UniqueConstraint("store_id", "ingredient_id", name="uq_store_ingredient"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id", ondelete="CASCADE"), index=True)
    package_size: Mapped[float]  # malzemenin temel biriminde (ör. 1000 g)
    price: Mapped[float]  # paket fiyatı, TL
    brand: Mapped[str] = mapped_column(String(80), default="")
    source: Mapped[str] = mapped_column(String(40), default="seed")
    updated_on: Mapped[date]

    store: Mapped[Store] = relationship(lazy="joined")
    ingredient: Mapped[Ingredient] = relationship(lazy="joined")
