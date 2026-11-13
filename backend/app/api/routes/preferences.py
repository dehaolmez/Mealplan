from fastapi import APIRouter

from app.api.deps import DB, CurrentHousehold
from app.schemas.preferences import GenerateIn, GenerateOut, PreferencesIn, PreferencesOut
from app.services import preferences_service as svc

router = APIRouter(tags=["Tercihler & Otomatik Plan"])


@router.get("/preferences", response_model=PreferencesOut)
def get_preferences(db: DB, household: CurrentHousehold):
    return svc.to_schema(svc.get(db, household))


@router.put("/preferences", response_model=PreferencesOut)
def put_preferences(data: PreferencesIn, db: DB, household: CurrentHousehold):
    """Diyet, alerji, sevilmeyenler, mutfak aletleri, öğün ayarları (planla/atla/kendim), günler, bütçe, tekrar."""
    return svc.to_schema(svc.update(db, household, data))


@router.post("/plan/generate", response_model=GenerateOut)
def generate(data: GenerateIn, db: DB, household: CurrentHousehold):
    """Tercihlere göre haftalık planı otomatik oluşturur (pişirilmiş/işaretlenmiş öğünlere dokunmaz)."""
    return svc.generate_week(db, household, data)
