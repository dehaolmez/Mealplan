from datetime import date

from pydantic import BaseModel, Field

from app.models.enums import ActivityLevel, Goal, Sex
from app.schemas.common import ORMModel


class MemberIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    birth_date: date
    sex: Sex
    height_cm: float = Field(gt=50, lt=260)
    weight_kg: float = Field(gt=10, lt=400)
    activity_level: ActivityLevel = ActivityLevel.light
    goal: Goal = Goal.maintain


class TargetsOut(BaseModel):
    bmr: float
    tdee: float
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    warnings: list[str] = []


class MemberOut(ORMModel):
    id: int
    name: str
    birth_date: date
    age: int
    sex: Sex
    height_cm: float
    weight_kg: float
    activity_level: ActivityLevel
    goal: Goal
    targets: TargetsOut


class HouseholdTargetsOut(BaseModel):
    members: list[MemberOut]
    total: TargetsOut | None
    meal_kcal_target: float | None = Field(
        description="Kişi başı ortalama öğün kalorisi (günlük ortalama / 3); tarif puanlamasında kullanılır"
    )


class HouseholdSettingsIn(BaseModel):
    name: str | None = None
    preferred_store_id: int | None = None
    selected_store_ids: list[int] | None = None


class HouseholdOut(BaseModel):
    id: int
    name: str
    preferred_store_id: int | None
    selected_store_ids: list[int]
