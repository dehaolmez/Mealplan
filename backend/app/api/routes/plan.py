from datetime import date, timedelta

from fastapi import APIRouter, status

from app.api.deps import DB, CurrentHousehold
from app.schemas.planning import CookOut, MealPlanIn, MealPlanOut
from app.services import clock
from app.services import plan_service as svc

router = APIRouter(prefix="/plan", tags=["Yemek Planı"])


@router.get("", response_model=list[MealPlanOut])
def list_plan(db: DB, household: CurrentHousehold, start: date | None = None, days: int = 7):
    start = start or clock.today()
    end = start + timedelta(days=max(days, 1) - 1)
    return [svc.entry_out(e) for e in svc.list_entries(db, household, start, end)]


@router.post("", response_model=MealPlanOut, status_code=status.HTTP_201_CREATED)
def add_entry(data: MealPlanIn, db: DB, household: CurrentHousehold):
    return svc.entry_out(svc.add_entry(db, household, data))


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(entry_id: int, db: DB, household: CurrentHousehold):
    svc.delete_entry(db, household, entry_id)


@router.post("/{entry_id}/cook", response_model=CookOut)
def cook(entry_id: int, db: DB, household: CurrentHousehold):
    """Öğünü pişirildi işaretler; malzemeleri ilk bozulacak partiden başlayarak envanterden düşer."""
    return svc.cook(db, household, entry_id)
