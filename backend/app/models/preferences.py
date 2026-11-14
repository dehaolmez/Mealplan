from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class HouseholdPreferences(Base):
    """Planlama tercihleri (başlangıç akışında sorulur, Profil'den değiştirilebilir)."""

    __tablename__ = "household_preferences"

    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), primary_key=True)
    # Alışveriş yapılan zincirler (slug, virgüllü). Boşsa tüm zincirler karşılaştırılır.
    preferred_chains: Mapped[str] = mapped_column(String(200), default="")
    # Ana hedefler (virgüllü): lose, muscle, decide_less, save_money, family, healthy
    goals: Mapped[str] = mapped_column(String(120), default="")
    diet: Mapped[str] = mapped_column(String(20), default="none")  # none | vegetarian | vegan | pescatarian
    low_carb: Mapped[bool] = mapped_column(default=False)
    # Tamamen dışlananlar (virgüllü etiketler): pork, red_meat, gluten, dairy, egg, nuts, peanut, fish,
    # shellfish, sesame, soy
    exclusions: Mapped[str] = mapped_column(String(200), default="")
    disliked_ingredient_ids: Mapped[str] = mapped_column(Text, default="")
    equipment: Mapped[str] = mapped_column(String(160), default="stovetop,oven")
    # Öğün ayarları (JSON): {"breakfast": {"mode": "plan|skip|own", "kcal": 0, "protein": 0}, ...}
    meals_json: Mapped[str] = mapped_column(Text, default="")
    plan_days: Mapped[str] = mapped_column(String(20), default="0,1,2,3,4,5,6")  # 0 = Pazartesi
    weekly_budget: Mapped[float | None]
    # Öğle/akşam öğününün düzeni: main (yalnız ana yemek) | main_side (ana + yan/salata) | full (çorba + ana + yan + salata)
    meal_structure: Mapped[str] = mapped_column(String(12), default="main_side")
    repeat_policy: Mapped[str] = mapped_column(String(12), default="variety")  # variety | balanced | batch
    max_prep_minutes: Mapped[int | None]
    onboarding_done: Mapped[bool] = mapped_column(default=False)
