from datetime import date

import pytest

from app.domain.nutrition import age_on, daily_targets, mifflin_st_jeor_bmr
from app.models.enums import ActivityLevel, Goal, Sex


def test_mifflin_st_jeor_reference_values():
    # 80 kg, 180 cm, 30 yaş erkek: 10*80 + 6.25*180 - 5*30 + 5 = 1780
    assert mifflin_st_jeor_bmr(Sex.male, 80, 180, 30) == pytest.approx(1780)
    # 60 kg, 165 cm, 25 yaş kadın: 600 + 1031.25 - 125 - 161 = 1345.25
    assert mifflin_st_jeor_bmr(Sex.female, 60, 165, 25) == pytest.approx(1345.25)


def test_targets_apply_activity_goal_and_macros():
    t = daily_targets(sex=Sex.male, weight_kg=80, height_cm=180, age=30, activity=ActivityLevel.moderate, goal=Goal.lose)
    assert t.tdee == pytest.approx(1780 * 1.55, abs=0.1)
    assert t.calories == round(1780 * 1.55 - 500)
    assert t.protein_g == round(1.8 * 80)
    # makrolardan geri hesaplanan enerji hedefle tutarlı olmalı (yuvarlama payı)
    energy = t.protein_g * 4 + t.carbs_g * 4 + t.fat_g * 9
    assert energy == pytest.approx(t.calories, abs=15)


def test_deficit_never_below_bmr():
    t = daily_targets(sex=Sex.female, weight_kg=45, height_cm=150, age=70, activity=ActivityLevel.sedentary, goal=Goal.lose)
    assert t.calories >= t.bmr
    assert t.warnings


def test_age_on_birthday_boundary():
    assert age_on(date(1990, 11, 14), date(2026, 11, 13)) == 35
    assert age_on(date(1990, 11, 13), date(2026, 11, 13)) == 36
