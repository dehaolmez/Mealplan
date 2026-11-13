"""Raf ömrü tahmini ve SKT durum sınıflandırması."""

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from app.models.catalog import Ingredient
from app.models.enums import StorageLocation

# Katalogda kural yoksa kullanılan muhafazakâr varsayılanlar (gün)
DEFAULT_FRIDGE_DAYS = 5
DEFAULT_FREEZER_DAYS = 90
DEFAULT_OPENED_DAYS = 3


class ExpiryStatus(StrEnum):
    expired = "expired"    # SKT geçti
    critical = "critical"  # bugün / yarın
    warning = "warning"    # birkaç gün içinde
    ok = "ok"


@dataclass(frozen=True)
class ExpiryEstimate:
    expiry_date: date
    estimated: bool


def shelf_life_days(ingredient: Ingredient, location: StorageLocation, opened: bool) -> int:
    if location == StorageLocation.freezer:
        return ingredient.shelf_life_freezer_days or DEFAULT_FREEZER_DAYS
    days = ingredient.shelf_life_fridge_days or DEFAULT_FRIDGE_DAYS
    if opened:
        days = min(days, ingredient.shelf_life_opened_days or DEFAULT_OPENED_DAYS)
    return days


def resolve_expiry(
    ingredient: Ingredient,
    location: StorageLocation,
    added_on: date,
    label_expiry: date | None,
    opened: bool,
) -> ExpiryEstimate:
    """Etiket SKT'si varsa onu kullanır; açılmış ürünlerde açık raf ömrü daha kısaysa onu seçer.

    Etiket yoksa (taze sebze/meyve, açık gıda) katalogdaki raf ömrü kuralından tahmin eder.
    """
    rule_expiry = added_on + timedelta(days=shelf_life_days(ingredient, location, opened))
    if label_expiry is None:
        return ExpiryEstimate(rule_expiry, estimated=True)
    if opened and location == StorageLocation.fridge and rule_expiry < label_expiry:
        return ExpiryEstimate(rule_expiry, estimated=True)
    return ExpiryEstimate(label_expiry, estimated=False)


def days_left(expiry: date, today: date) -> int:
    return (expiry - today).days


def classify(expiry: date, today: date, critical_days: int = 1, warning_days: int = 3) -> ExpiryStatus:
    left = days_left(expiry, today)
    if left < 0:
        return ExpiryStatus.expired
    if left <= critical_days:
        return ExpiryStatus.critical
    if left <= warning_days:
        return ExpiryStatus.warning
    return ExpiryStatus.ok
