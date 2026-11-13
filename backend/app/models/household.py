from datetime import date

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import ActivityLevel, Goal, Sex


class Household(Base):
    __tablename__ = "households"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    preferred_store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id", ondelete="SET NULL"))
    # Virgülle ayrılmış market id'leri (MVP için yeterli; ileride ilişki tablosuna taşınabilir)
    selected_store_ids: Mapped[str] = mapped_column(String(200), default="")

    members: Mapped[list["Member"]] = relationship(back_populates="household", cascade="all, delete-orphan")


class Member(Base):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    birth_date: Mapped[date]
    sex: Mapped[Sex] = mapped_column(Enum(Sex, native_enum=False))
    height_cm: Mapped[float]
    weight_kg: Mapped[float]
    activity_level: Mapped[ActivityLevel] = mapped_column(Enum(ActivityLevel, native_enum=False))
    goal: Mapped[Goal] = mapped_column(Enum(Goal, native_enum=False), default=Goal.maintain)

    household: Mapped[Household] = relationship(back_populates="members")
