from datetime import date, timedelta

import pytest

from app.domain.shelf_life import ExpiryStatus, classify, resolve_expiry
from app.domain.units import UnitConversionError, humanize, to_base_quantity
from app.models import Ingredient
from app.models.enums import BaseUnit, Category, StorageLocation

D = date(2026, 11, 13)


def ing(**kw):
    defaults = dict(name="X", category=Category.produce, base_unit=BaseUnit.g, grams_per_piece=None,
                    density_g_per_ml=None, shelf_life_fridge_days=7, shelf_life_freezer_days=180,
                    shelf_life_opened_days=2)
    defaults.update(kw)
    return Ingredient(**defaults)


def test_estimates_from_rules_when_no_label():
    e = resolve_expiry(ing(), StorageLocation.fridge, D, None, opened=False)
    assert e.estimated and e.expiry_date == D + timedelta(days=7)
    f = resolve_expiry(ing(), StorageLocation.freezer, D, None, opened=False)
    assert f.expiry_date == D + timedelta(days=180)


def test_label_wins_unless_opened_rule_is_shorter():
    label = D + timedelta(days=20)
    assert resolve_expiry(ing(), StorageLocation.fridge, D, label, opened=False).expiry_date == label
    opened = resolve_expiry(ing(), StorageLocation.fridge, D, label, opened=True)
    assert opened.expiry_date == D + timedelta(days=2) and opened.estimated


def test_falls_back_to_defaults_without_catalog_rule():
    e = resolve_expiry(ing(shelf_life_fridge_days=None), StorageLocation.fridge, D, None, opened=False)
    assert e.expiry_date == D + timedelta(days=5)


@pytest.mark.parametrize(
    ("delta", "status"),
    [(-1, ExpiryStatus.expired), (0, ExpiryStatus.critical), (1, ExpiryStatus.critical),
     (3, ExpiryStatus.warning), (4, ExpiryStatus.ok)],
)
def test_classify(delta, status):
    assert classify(D + timedelta(days=delta), D) == status


def test_unit_conversion():
    assert to_base_quantity(ing(), 1.5, "kg") == 1500
    egg = ing(base_unit=BaseUnit.piece, grams_per_piece=60)
    assert to_base_quantity(egg, 120, "g") == 2
    milk = ing(base_unit=BaseUnit.ml, density_g_per_ml=1.03)
    assert to_base_quantity(milk, 2, "l") == 2000
    with pytest.raises(UnitConversionError):
        to_base_quantity(ing(), 1, "adet")
    with pytest.raises(UnitConversionError):
        to_base_quantity(ing(), 1, "fincan")


def test_humanize():
    assert humanize(1500, BaseUnit.g) == "1,5 kg"
    assert humanize(250, BaseUnit.ml) == "250 ml"
    assert humanize(3, BaseUnit.piece) == "3 adet"
