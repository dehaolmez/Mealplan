from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.chain import Chain


class Place(Base):
    """OpenStreetMap'ten alınan fiziksel market şubesi."""

    __tablename__ = "places"
    __table_args__ = (UniqueConstraint("osm_type", "osm_id", name="uq_place_osm"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    osm_type: Mapped[str] = mapped_column(String(10))
    osm_id: Mapped[int]
    name: Mapped[str] = mapped_column(String(160), default="")
    brand: Mapped[str] = mapped_column(String(120), default="")
    shop: Mapped[str] = mapped_column(String(40), default="")
    chain_id: Mapped[int | None] = mapped_column(ForeignKey("chains.id", ondelete="SET NULL"), index=True)
    lat: Mapped[float] = mapped_column(index=True)
    lon: Mapped[float] = mapped_column(index=True)
    address: Mapped[str] = mapped_column(String(240), default="")
    opening_hours: Mapped[str] = mapped_column(String(240), default="")
    fetched_at: Mapped[datetime]

    chain: Mapped[Chain | None] = relationship(lazy="joined")


class PlaceQuery(Base):
    """Overpass'a yapılan alan sorgularının önbelleği (aynı bölge için sunucuyu tekrar yormamak adına)."""

    __tablename__ = "place_queries"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    fetched_at: Mapped[datetime]
    place_ids: Mapped[str] = mapped_column(Text, default="")  # virgülle ayrılmış Place.id
