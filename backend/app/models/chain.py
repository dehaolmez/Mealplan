from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import ChainKind


class Chain(Base):
    """Market zinciri (marka). Haritadaki şubeler ve fiyat listeleri bu kayda bağlanır."""

    __tablename__ = "chains"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    kind: Mapped[ChainKind] = mapped_column(Enum(ChainKind, native_enum=False))
    parent: Mapped[str] = mapped_column(String(120), default="")
    # OpenStreetMap'teki brand/name etiketleriyle eşleştirme için virgülle ayrılmış takma adlar
    aliases: Mapped[str] = mapped_column(String(300), default="")
    website: Mapped[str] = mapped_column(String(120), default="")
    color: Mapped[str] = mapped_column(String(9), default="#64748b")
    # TÜBİTAK "Market Fiyatı" platformunda fiyatları yayımlanan zincirlerden mi?
    in_market_fiyati: Mapped[bool] = mapped_column(default=False)
