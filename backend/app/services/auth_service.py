"""Hesap, oturum, hane üyeliği ve KVKK rıza kayıtları."""

import logging
import secrets
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import get_settings
from app.legal import LEGAL_VERSION
from app.models import ConsentRecord, Household, HouseholdMembership, Member, User
from app.models.enums import ConsentKind, HouseholdRole
from app.schemas.auth import ConsentState, MeOut
from app.services import mailer
from app.services.errors import BadRequest, NotFound

log = logging.getLogger(__name__)

SESSION_PURPOSE = "session"
RESET_PURPOSE = "pwreset"
VERIFY_PURPOSE = "verify"


class Unauthorized(Exception):
    pass


# ---- oturum -----------------------------------------------------------------

def issue_session(user: User) -> str:
    return security.create_token(
        user.id, SESSION_PURPOSE, timedelta(days=get_settings().session_days), version=user.token_version
    )


def user_from_token(db: Session, token: str | None) -> User:
    if not token:
        raise Unauthorized("Oturum açılmamış")
    payload = security.decode_token(token, SESSION_PURPOSE)
    if payload is None:
        raise Unauthorized("Oturum süresi dolmuş veya geçersiz")
    user = db.get(User, int(payload["sub"]))
    if user is None or user.token_version != payload.get("ver"):
        raise Unauthorized("Oturum geçersiz")
    return user


def membership(user: User) -> HouseholdMembership:
    if not user.memberships:
        raise Unauthorized("Hesaba bağlı hane yok")
    return sorted(user.memberships, key=lambda m: m.joined_at)[0]


# ---- rıza -------------------------------------------------------------------

def record_consent(db: Session, user: User, kind: ConsentKind, granted: bool) -> None:
    db.add(ConsentRecord(user_id=user.id, kind=kind, granted=granted, text_version=LEGAL_VERSION,
                         subject_hash=security.email_fingerprint(user.email)))


def consent_states(db: Session, user: User) -> dict[ConsentKind, ConsentState]:
    rows = db.scalars(
        select(ConsentRecord).where(ConsentRecord.user_id == user.id).order_by(ConsentRecord.id)
    )
    latest: dict[ConsentKind, ConsentRecord] = {}
    for r in rows:
        latest[r.kind] = r
    return {
        k: ConsentState(kind=k, granted=bool(latest[k].granted) if k in latest else False,
                        text_version=latest[k].text_version if k in latest else None,
                        updated_at=latest[k].created_at if k in latest else None)
        for k in ConsentKind
    }


def has_consent(db: Session, user: User | None, kind: ConsentKind) -> bool:
    if user is None:
        return False
    return consent_states(db, user)[kind].granted


def set_consent(db: Session, user: User, kind: ConsentKind, granted: bool) -> None:
    if kind in (ConsentKind.privacy_notice, ConsentKind.terms) and not granted:
        raise BadRequest("Aydınlatma/kullanım koşulu onayı geri alınamaz; hesabı silebilirsiniz")
    record_consent(db, user, kind, granted)
    if not granted:
        _on_withdraw(db, user, kind)
    db.commit()


def _on_withdraw(db: Session, user: User, kind: ConsentKind) -> None:
    """Rıza geri çekilince ilgili veri işlenmez ve silinir (KVKK m.7 / m.11)."""
    hh_id = membership(user).household_id
    if kind == ConsentKind.health_data:
        for m in db.scalars(select(Member).where(Member.household_id == hh_id)):
            db.delete(m)
    elif kind == ConsentKind.location:
        hh = db.get(Household, hh_id)
        hh.home_lat = hh.home_lon = None


def _initial_consents(db: Session, user: User, data) -> None:
    record_consent(db, user, ConsentKind.terms, True)
    record_consent(db, user, ConsentKind.privacy_notice, True)
    for kind, flag in (
        (ConsentKind.health_data, data.health_data_consent),
        (ConsentKind.location, data.location_consent),
        (ConsentKind.ai_transfer, data.ai_transfer_consent),
        (ConsentKind.marketing, getattr(data, "marketing_consent", False)),
    ):
        record_consent(db, user, kind, bool(flag))


# ---- kayıt / giriş -----------------------------------------------------------

def _new_invite_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # karışan harfler (0/O, 1/I) yok
    return "".join(secrets.choice(alphabet) for _ in range(8))


def _attach_household(db: Session, user: User, invite_code: str | None, with_sample: bool, health_ok: bool) -> None:
    if invite_code:
        hh = db.scalar(select(Household).where(Household.invite_code == invite_code.strip().upper()))
        if hh is None:
            raise BadRequest("Davet kodu bulunamadı")
        db.add(HouseholdMembership(user=user, household_id=hh.id, role=HouseholdRole.member))
        return
    hh = Household(name=f"{user.display_name or 'Benim'} evim", invite_code=_new_invite_code())
    db.add(hh)
    db.flush()
    db.add(HouseholdMembership(user=user, household_id=hh.id, role=HouseholdRole.owner))
    if with_sample:
        from app.seed.loader import seed_sample_household

        seed_sample_household(db, hh, with_members=health_ok)


def _require_legal(data) -> None:
    if not data.accept_terms or not data.acknowledge_privacy_notice:
        raise BadRequest("Devam etmek için kullanım koşullarını kabul edip aydınlatma metnini okuduğunuzu onaylayın")


def register(db: Session, data) -> User:
    _require_legal(data)
    email = data.email.strip().lower()
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise BadRequest("Bu e-posta ile zaten bir hesap var")
    user = User(email=email, display_name=data.display_name.strip(), password_hash=security.hash_password(data.password))
    db.add(user)
    db.flush()
    _attach_household(db, user, data.invite_code, data.with_sample_data, data.health_data_consent)
    _initial_consents(db, user, data)
    db.commit()
    send_verification(user)
    return user


def login(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))
    if user is None or not security.verify_password(password, user.password_hash):
        raise Unauthorized("E-posta veya şifre hatalı")
    return user


def login_google(db: Session, data) -> tuple[User, bool]:
    try:
        claims = security.verify_google_id_token(data.credential)
    except Exception as exc:  # imza, süre, audience hataları
        raise Unauthorized(f"Google doğrulaması başarısız: {exc}") from exc
    sub, email = claims["sub"], claims["email"].lower()
    user = db.scalar(select(User).where(User.google_sub == sub))
    if user is None:
        user = db.scalar(select(User).where(func.lower(User.email) == email))
        if user is not None:  # aynı e-postalı mevcut hesaba Google'ı bağla (Google e-postayı doğruladı)
            user.google_sub = sub
            user.email_verified = True
    created = False
    if user is None:
        _require_legal(data)
        user = User(email=email, display_name=claims.get("given_name") or claims.get("name") or "",
                    google_sub=sub, email_verified=True)
        db.add(user)
        db.flush()
        _attach_household(db, user, None, data.with_sample_data, data.health_data_consent)
        _initial_consents(db, user, data)
        created = True
    db.commit()
    return user, created


# ---- şifre & e-posta doğrulama ---------------------------------------------------

def change_password(db: Session, user: User, current: str | None, new: str) -> None:
    if user.password_hash and not security.verify_password(current or "", user.password_hash):
        raise BadRequest("Mevcut şifre hatalı")
    user.password_hash = security.hash_password(new)
    user.token_version += 1  # diğer cihazlardaki oturumları kapat
    db.commit()


def forgot_password(db: Session, email: str) -> None:
    user = db.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))
    if user is None:
        return  # hesap var/yok bilgisini sızdırma
    token = security.create_token(user.id, RESET_PURPOSE, timedelta(hours=1), version=user.token_version)
    link = f"{get_settings().public_base_url}/#reset={token}"
    mailer.send(user.email, "Meall şifre sıfırlama",
                f"Şifrenizi sıfırlamak için bağlantı (1 saat geçerli):\n{link}\n\nBu isteği siz yapmadıysanız yok sayın.")


def reset_password(db: Session, token: str, new: str) -> User:
    payload = security.decode_token(token, RESET_PURPOSE)
    user = db.get(User, int(payload["sub"])) if payload else None
    if user is None or payload.get("ver") != user.token_version:
        raise BadRequest("Bağlantı geçersiz veya süresi dolmuş")
    user.password_hash = security.hash_password(new)
    user.token_version += 1
    db.commit()
    return user


def send_verification(user: User) -> None:
    if user.email_verified:
        return
    token = security.create_token(user.id, VERIFY_PURPOSE, timedelta(days=3))
    link = f"{get_settings().public_base_url}/#verify={token}"
    mailer.send(user.email, "Meall e-posta doğrulama", f"E-posta adresinizi doğrulamak için:\n{link}")


def verify_email(db: Session, token: str) -> None:
    payload = security.decode_token(token, VERIFY_PURPOSE)
    user = db.get(User, int(payload["sub"])) if payload else None
    if user is None:
        raise BadRequest("Bağlantı geçersiz veya süresi dolmuş")
    user.email_verified = True
    db.commit()


# ---- profil, hane, haklar ------------------------------------------------------

def me(db: Session, user: User) -> MeOut:
    m = membership(user)
    hh = db.get(Household, m.household_id)
    states = consent_states(db, user)
    needs = any(states[k].text_version != LEGAL_VERSION for k in (ConsentKind.terms, ConsentKind.privacy_notice))
    return MeOut(
        id=user.id, email=user.email, display_name=user.display_name, email_verified=user.email_verified,
        is_admin=user.is_admin,
        has_password=bool(user.password_hash), google_linked=bool(user.google_sub),
        household_id=hh.id, household_name=hh.name, role=m.role,
        invite_code=hh.invite_code if m.role == HouseholdRole.owner else None,
        consents=list(states.values()), legal_version=LEGAL_VERSION, needs_reconsent=needs,
    )


def accept_current_terms(db: Session, user: User) -> None:
    record_consent(db, user, ConsentKind.terms, True)
    record_consent(db, user, ConsentKind.privacy_notice, True)
    db.commit()


def join_household(db: Session, user: User, code: str) -> None:
    hh = db.scalar(select(Household).where(Household.invite_code == code.strip().upper()))
    if hh is None:
        raise NotFound("Davet kodu", code)
    old = membership(user)
    if old.household_id == hh.id:
        return
    old_hh_id = old.household_id
    db.delete(old)
    db.flush()
    db.add(HouseholdMembership(user_id=user.id, household_id=hh.id, role=HouseholdRole.member))
    _delete_household_if_empty(db, old_hh_id)
    db.commit()


def rotate_invite(db: Session, user: User) -> str:
    m = membership(user)
    if m.role != HouseholdRole.owner:
        raise BadRequest("Yalnız hane sahibi davet kodunu yenileyebilir")
    hh = db.get(Household, m.household_id)
    hh.invite_code = _new_invite_code()
    db.commit()
    return hh.invite_code


def _delete_household_if_empty(db: Session, household_id: int) -> None:
    remaining = db.scalar(select(func.count()).select_from(HouseholdMembership)
                          .where(HouseholdMembership.household_id == household_id))
    if remaining == 0:
        from app.models import InventoryItem, MealPlanEntry, ShoppingItem

        # Veritabanı CASCADE'ine güvenmeden hanenin tüm verisini açıkça sil
        for model in (InventoryItem, MealPlanEntry, ShoppingItem, Member):
            for row in db.scalars(select(model).where(model.household_id == household_id)):
                db.delete(row)
        hh = db.get(Household, household_id)
        if hh is not None:
            db.delete(hh)


def delete_account(db: Session, user: User) -> None:
    """KVKK m.7/m.11: hesap ve (başka üyesi yoksa) hanenin tüm verisi silinir.
    Rıza kayıtları ispat yükümlülüğü için kullanıcıdan koparılarak (anonim özetle) saklanır."""
    hh_ids = [m.household_id for m in user.memberships]
    for r in db.scalars(select(ConsentRecord).where(ConsentRecord.user_id == user.id)):
        r.user_id = None
    db.delete(user)
    db.flush()
    for hh_id in hh_ids:
        # Sahip ayrılıyorsa ve başka üye varsa sahipliği en eski üyeye devret
        members = list(db.scalars(select(HouseholdMembership).where(HouseholdMembership.household_id == hh_id)
                                  .order_by(HouseholdMembership.joined_at)))
        if members and not any(m.role == HouseholdRole.owner for m in members):
            members[0].role = HouseholdRole.owner
        _delete_household_if_empty(db, hh_id)
    db.commit()


def export_data(db: Session, user: User) -> dict:
    """KVKK m.11 kapsamında kullanıcının verilerinin makinece okunur dökümü."""
    from app.models import InventoryItem, MealPlanEntry, ShoppingItem

    hh_id = membership(user).household_id
    hh = db.get(Household, hh_id)

    def rows(model):
        out = []
        for obj in db.scalars(select(model).where(model.household_id == hh_id)):
            out.append({c.name: _jsonable(getattr(obj, c.name)) for c in model.__table__.columns})
        return out

    consents = [
        {"kind": r.kind.value, "granted": r.granted, "text_version": r.text_version, "at": r.created_at.isoformat()}
        for r in db.scalars(select(ConsentRecord).where(ConsentRecord.user_id == user.id).order_by(ConsentRecord.id))
    ]
    return {
        "generated_at": datetime.now().isoformat(),
        "account": {"email": user.email, "display_name": user.display_name, "created_at": user.created_at.isoformat(),
                    "google_linked": bool(user.google_sub)},
        "household": {"name": hh.name, "home_lat": hh.home_lat, "home_lon": hh.home_lon},
        "members": rows(Member),
        "inventory": rows(InventoryItem),
        "meal_plan": rows(MealPlanEntry),
        "shopping_list": rows(ShoppingItem),
        "consents": consents,
    }


def _jsonable(v):
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if hasattr(v, "value"):
        return v.value
    return v


# ---- yönetici -------------------------------------------------------------------

def ensure_admin(db: Session, email: str, password: str) -> tuple[User, bool]:
    """Yönetici hesabını yoksa oluşturur (tüm isteğe bağlı izinler açık, örnek verili hane); varsa yalnız
    yönetici yetkisini verir — mevcut şifreyi değiştirmez."""
    from app.schemas.auth import RegisterIn

    email = email.strip().lower()
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user is not None:
        if not user.is_admin:
            user.is_admin = True
            db.commit()
        return user, False
    data = RegisterIn(
        email=email, password=password, display_name="Yönetici", accept_terms=True, acknowledge_privacy_notice=True,
        health_data_consent=True, location_consent=True, ai_transfer_consent=True, marketing_consent=False,
        with_sample_data=True,
    )
    _require_legal(data)
    user = User(email=email, display_name=data.display_name, password_hash=security.hash_password(password),
                email_verified=True, is_admin=True)
    db.add(user)
    db.flush()
    _attach_household(db, user, None, True, True)
    _initial_consents(db, user, data)
    db.commit()
    return user, True
