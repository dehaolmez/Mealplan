from datetime import datetime

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import ConsentKind, HouseholdRole


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(80), default="")
    # Yalnız Google ile giriş yapanlarda boş olabilir
    password_hash: Mapped[str | None] = mapped_column(String(300))
    google_sub: Mapped[str | None] = mapped_column(String(64), unique=True)
    email_verified: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    # Şifre değişince eski oturumları geçersiz kılmak için token'a gömülür
    token_version: Mapped[int] = mapped_column(default=0)

    memberships: Mapped[list["HouseholdMembership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )


class HouseholdMembership(Base):
    __tablename__ = "household_memberships"
    __table_args__ = (UniqueConstraint("user_id", "household_id", name="uq_membership"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    role: Mapped[HouseholdRole] = mapped_column(Enum(HouseholdRole, native_enum=False), default=HouseholdRole.member)
    joined_at: Mapped[datetime] = mapped_column(default=datetime.now)

    user: Mapped[User] = relationship(back_populates="memberships")


class ConsentRecord(Base):
    """KVKK ispat yükü için her onay/geri çekme olayı ayrı satır olarak saklanır (silinmez, güncellenmez)."""

    __tablename__ = "consent_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    kind: Mapped[ConsentKind] = mapped_column(Enum(ConsentKind, native_enum=False))
    granted: Mapped[bool]
    text_version: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    # Kullanıcı hesabını silse bile kaydın kime ait olduğunu ispat için e-postanın özeti (düz metin değil)
    subject_hash: Mapped[str] = mapped_column(String(64), default="")
