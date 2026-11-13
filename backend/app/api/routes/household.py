from fastapi import APIRouter, status

from app.api.deps import DB, CurrentHousehold
from app.schemas.household import HouseholdOut, HouseholdSettingsIn, HouseholdTargetsOut, MemberIn, MemberOut
from app.services import household_service as svc

router = APIRouter(prefix="/household", tags=["Hane & Beslenme"])


@router.get("", response_model=HouseholdOut)
def get_household(household: CurrentHousehold):
    return svc.household_out(household)


@router.patch("", response_model=HouseholdOut)
def update_household(data: HouseholdSettingsIn, db: DB, household: CurrentHousehold):
    return svc.household_out(svc.update_settings(db, household, data))


@router.get("/targets", response_model=HouseholdTargetsOut)
def targets(db: DB, household: CurrentHousehold):
    """Her bireyin ve hanenin toplam günlük kalori/makro hedefleri (Mifflin-St Jeor)."""
    return svc.household_targets(db, household)


@router.post("/members", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
def add_member(data: MemberIn, db: DB, household: CurrentHousehold):
    return svc.member_out(svc.add_member(db, household, data))


@router.put("/members/{member_id}", response_model=MemberOut)
def update_member(member_id: int, data: MemberIn, db: DB, household: CurrentHousehold):
    return svc.member_out(svc.update_member(db, household, member_id, data))


@router.delete("/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_member(member_id: int, db: DB, household: CurrentHousehold):
    svc.delete_member(db, household, member_id)
