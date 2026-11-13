from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.nutrition import NutritionTargets, age_on, daily_targets
from app.models import Household, Member, Store
from app.schemas.household import (
    HouseholdOut,
    HouseholdSettingsIn,
    HouseholdTargetsOut,
    MemberIn,
    MemberOut,
    TargetsOut,
)
from app.services import clock
from app.services.errors import BadRequest, NotFound

DEFAULT_HOUSEHOLD_ID = 1


def get_household(db: Session, household_id: int = DEFAULT_HOUSEHOLD_ID) -> Household:
    """MVP tek haneli çalışır. Kimlik doğrulama eklendiğinde hane, kullanıcıdan çözülecek."""
    household = db.get(Household, household_id)
    if household is None:
        household = Household(id=household_id, name="Evim")
        db.add(household)
        db.commit()
    return household


def store_ids(household: Household) -> list[int]:
    return [int(x) for x in household.selected_store_ids.split(",") if x]


def household_out(household: Household) -> HouseholdOut:
    return HouseholdOut(
        id=household.id,
        name=household.name,
        preferred_store_id=household.preferred_store_id,
        selected_store_ids=store_ids(household),
    )


def update_settings(db: Session, household: Household, data: HouseholdSettingsIn) -> Household:
    if data.name is not None:
        household.name = data.name
    known = set(db.scalars(select(Store.id)))
    if data.selected_store_ids is not None:
        unknown = set(data.selected_store_ids) - known
        if unknown:
            raise BadRequest(f"Bilinmeyen market: {sorted(unknown)}")
        household.selected_store_ids = ",".join(str(i) for i in data.selected_store_ids)
    if "preferred_store_id" in data.model_fields_set:
        if data.preferred_store_id is not None and data.preferred_store_id not in known:
            raise BadRequest("Bilinmeyen market")
        household.preferred_store_id = data.preferred_store_id
    db.commit()
    return household


def _targets(member: Member) -> NutritionTargets:
    return daily_targets(
        sex=member.sex,
        weight_kg=member.weight_kg,
        height_cm=member.height_cm,
        age=age_on(member.birth_date, clock.today()),
        activity=member.activity_level,
        goal=member.goal,
    )


def member_out(member: Member) -> MemberOut:
    t = _targets(member)
    return MemberOut(
        id=member.id,
        name=member.name,
        birth_date=member.birth_date,
        age=age_on(member.birth_date, clock.today()),
        sex=member.sex,
        height_cm=member.height_cm,
        weight_kg=member.weight_kg,
        activity_level=member.activity_level,
        goal=member.goal,
        targets=TargetsOut(**t.__dict__),
    )


def add_member(db: Session, household: Household, data: MemberIn) -> Member:
    member = Member(household_id=household.id, **data.model_dump())
    db.add(member)
    db.commit()
    return member


def update_member(db: Session, household: Household, member_id: int, data: MemberIn) -> Member:
    member = _get_member(db, household, member_id)
    for key, value in data.model_dump().items():
        setattr(member, key, value)
    db.commit()
    return member


def delete_member(db: Session, household: Household, member_id: int) -> None:
    db.delete(_get_member(db, household, member_id))
    db.commit()


def _get_member(db: Session, household: Household, member_id: int) -> Member:
    member = db.get(Member, member_id)
    if member is None or member.household_id != household.id:
        raise NotFound("Kişi", member_id)
    return member


def household_targets(db: Session, household: Household) -> HouseholdTargetsOut:
    members = list(db.scalars(select(Member).where(Member.household_id == household.id).order_by(Member.id)))
    outs = [member_out(m) for m in members]
    if not outs:
        return HouseholdTargetsOut(members=[], total=None, meal_kcal_target=None)
    total = TargetsOut(
        bmr=round(sum(m.targets.bmr for m in outs), 1),
        tdee=round(sum(m.targets.tdee for m in outs), 1),
        calories=sum(m.targets.calories for m in outs),
        protein_g=sum(m.targets.protein_g for m in outs),
        carbs_g=sum(m.targets.carbs_g for m in outs),
        fat_g=sum(m.targets.fat_g for m in outs),
    )
    meal_target = round(total.calories / len(outs) / 3)
    return HouseholdTargetsOut(members=outs, total=total, meal_kcal_target=meal_target)
