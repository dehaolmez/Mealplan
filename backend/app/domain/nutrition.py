"""Enerji ve makro besin ihtiyacı hesabı (Mifflin-St Jeor).

Saf fonksiyonlar: veritabanından bağımsızdır, birim testleri kolaydır.
"""

import math
from dataclasses import dataclass, field
from datetime import date

from app.models.enums import ActivityLevel, Goal, Sex

ACTIVITY_FACTORS: dict[ActivityLevel, float] = {
    ActivityLevel.sedentary: 1.2,
    ActivityLevel.light: 1.375,
    ActivityLevel.moderate: 1.55,
    ActivityLevel.active: 1.725,
    ActivityLevel.very_active: 1.9,
}

# Hedefe göre günlük kalori ayarı (kcal) ve kg başına protein (g)
GOAL_KCAL_DELTA: dict[Goal, int] = {Goal.lose: -500, Goal.maintain: 0, Goal.gain: 300}
PROTEIN_G_PER_KG: dict[Goal, float] = {Goal.lose: 1.8, Goal.maintain: 1.4, Goal.gain: 1.8}
FAT_ENERGY_SHARE = 0.30  # günlük enerjinin %30'u yağdan

KCAL_PER_G_PROTEIN = 4
KCAL_PER_G_CARB = 4
KCAL_PER_G_FAT = 9


@dataclass(frozen=True)
class NutritionTargets:
    bmr: float
    tdee: float
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    warnings: list[str] = field(default_factory=list)


def age_on(birth_date: date, today: date) -> int:
    years = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years


def mifflin_st_jeor_bmr(sex: Sex, weight_kg: float, height_cm: float, age: int) -> float:
    """Bazal metabolizma hızı (kcal/gün). Erkek: +5, kadın: -161."""
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + (5 if sex == Sex.male else -161)


def daily_targets(
    *,
    sex: Sex,
    weight_kg: float,
    height_cm: float,
    age: int,
    activity: ActivityLevel,
    goal: Goal,
) -> NutritionTargets:
    warnings: list[str] = []
    if age < 18:
        warnings.append("Mifflin-St Jeor yetişkinler için geçerlidir; 18 yaş altı için sonuçlar yaklaşıktır.")

    bmr = mifflin_st_jeor_bmr(sex, weight_kg, height_cm, age)
    tdee = bmr * ACTIVITY_FACTORS[activity]
    calories = tdee + GOAL_KCAL_DELTA[goal]
    if calories < bmr:
        # Güvenlik sınırı: kilo verirken bile BMR altına inme
        calories = math.ceil(bmr)  # yukarı yuvarla: hedef BMR'nin altına düşmesin
        warnings.append("Kalori açığı BMR ile sınırlandı.")

    protein_g = PROTEIN_G_PER_KG[goal] * weight_kg
    fat_g = calories * FAT_ENERGY_SHARE / KCAL_PER_G_FAT
    carb_kcal = calories - protein_g * KCAL_PER_G_PROTEIN - fat_g * KCAL_PER_G_FAT
    carbs_g = max(0.0, carb_kcal / KCAL_PER_G_CARB)

    return NutritionTargets(
        bmr=round(bmr, 1),
        tdee=round(tdee, 1),
        calories=round(calories),
        protein_g=round(protein_g),
        carbs_g=round(carbs_g),
        fat_g=round(fat_g),
        warnings=warnings,
    )


@dataclass(frozen=True)
class Macros:
    kcal: float = 0
    protein_g: float = 0
    carbs_g: float = 0
    fat_g: float = 0

    def __add__(self, other: "Macros") -> "Macros":
        return Macros(
            self.kcal + other.kcal,
            self.protein_g + other.protein_g,
            self.carbs_g + other.carbs_g,
            self.fat_g + other.fat_g,
        )

    def scaled(self, factor: float) -> "Macros":
        return Macros(self.kcal * factor, self.protein_g * factor, self.carbs_g * factor, self.fat_g * factor)

    def rounded(self) -> "Macros":
        return Macros(round(self.kcal), round(self.protein_g, 1), round(self.carbs_g, 1), round(self.fat_g, 1))
