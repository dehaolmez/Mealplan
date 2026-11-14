import datetime as dt

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import DB, CurrentHousehold, CurrentUser
from app.core.config import get_settings
from app.models.enums import ConsentKind, StorageLocation
from app.services import auth_service, rate_limit, receipts
from app.services.errors import BadRequest

router = APIRouter(prefix="/receipts", tags=["Fiş okuma (yapay zekâ)"])


class ScanIn(BaseModel):
    image_base64: str = Field(max_length=9_000_000)
    mime_type: str = "image/jpeg"


class ConfirmLine(BaseModel):
    ingredient_id: int
    quantity: float = Field(gt=0)
    unit: str | None = None
    location: StorageLocation = StorageLocation.fridge
    expiry_date: dt.date | None = None


class ConfirmIn(BaseModel):
    date: dt.date | None = None
    lines: list[ConfirmLine] = Field(min_length=1, max_length=80)


@router.post("/scan")
def scan(data: ScanIn, db: DB, user: CurrentUser):
    """Fiş fotoğrafını okuyup envanter taslağı döner. Fotoğraf saklanmaz; yalnız Gemini'ye iletilir."""
    s = get_settings()
    if not s.ai_available or s.ai_provider != "gemini":
        raise BadRequest("Fiş okuma için Gemini yapılandırılmamış")
    if not auth_service.has_consent(db, user, ConsentKind.ai_transfer):
        raise BadRequest("Fiş okuma için Profil › Gizlilik bölümünden yapay zekâ iznini açmalısınız")
    if not rate_limit.allow(f"receipt:{user.id}", 20, 3600):
        raise BadRequest("Saatte en fazla 20 fiş okunabilir")
    return receipts.scan(db, data.image_base64, data.mime_type)


@router.post("/confirm")
def confirm(data: ConfirmIn, db: DB, household: CurrentHousehold):
    added = receipts.confirm(db, household, [line.model_dump() for line in data.lines], data.date)
    return {"added": added}
