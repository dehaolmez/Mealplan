from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.pricing import Store


class MarketProduct(Base):
    """Canlı fiyat kaynağından (Market Fiyatı) gelen, bir malzemeyle eşleşen gerçek ürün ve şube fiyatı.

    Aynı zincirde aynı malzeme için birden çok paket (ör. 1 L ve 5 L yağ) tutulur; optimizasyon ihtiyaca göre
    en ucuz toplam tutarı veren paketi seçer.
    """

    __tablename__ = "market_products"

    id: Mapped[int] = mapped_column(primary_key=True)
    area_key: Mapped[str] = mapped_column(String(40), index=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    brand: Mapped[str] = mapped_column(String(80), default="")
    package_size: Mapped[float]  # malzemenin temel biriminde
    price: Mapped[float]
    depot_name: Mapped[str] = mapped_column(String(160), default="")
    source_time: Mapped[str] = mapped_column(String(20), default="")  # kaynağın bildirdiği güncelleme zamanı
    fetched_at: Mapped[datetime]

    store: Mapped[Store] = relationship(lazy="joined")


class LivePriceFetch(Base):
    """Bir bölge + malzeme için son başarılı sorgu zamanı (önbellek ve hız sınırı için)."""

    __tablename__ = "live_price_fetches"

    area_key: Mapped[str] = mapped_column(String(40), primary_key=True)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id", ondelete="CASCADE"), primary_key=True)
    fetched_at: Mapped[datetime]
    matched: Mapped[int] = mapped_column(default=0)


class LiveArea(Base):
    """Bir bölgedeki Market Fiyatı şubeleri (depo kimlikleri) önbelleği."""

    __tablename__ = "live_areas"

    area_key: Mapped[str] = mapped_column(String(40), primary_key=True)
    depots_json: Mapped[str] = mapped_column(Text, default="[]")
    fetched_at: Mapped[datetime]
