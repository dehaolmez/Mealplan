"""Market ürünlerinin paket bilgisini ("1.65 KG", "710 GR", "1 LT", "10 Adet") malzemenin temel birimine çevirir."""

import re

from app.domain.units import UnitConversionError, to_base_quantity
from app.models.catalog import Ingredient
from app.models.enums import BaseUnit

_UNIT = {"kg": "kg", "gr": "g", "g": "g", "lt": "l", "l": "l", "ml": "ml", "adet": "adet", "ad": "adet"}
_QTY = re.compile(r"(\d+(?:[.,]\d+)?)\s*(kg|gr|g|lt|l|ml|adet|ad)\b", re.IGNORECASE)


def _parse(text: str | None) -> tuple[float, str] | None:
    if not text:
        return None
    m = _QTY.search(text)
    if not m:
        return None
    return float(m.group(1).replace(",", ".")), _UNIT[m.group(2).lower()]


def package_base_quantity(ingredient: Ingredient, title: str, volume_or_weight: str | None,
                          quantity_unit: str | None) -> float | None:
    """Paket miktarını temel birimde döner; çevrilemiyorsa None."""
    candidates: list[tuple[float, str]] = []
    if ingredient.base_unit == BaseUnit.piece:
        # Adetle tutulan ürünlerde (yumurta) adet bilgisi ağırlıktan önce gelir
        for src in (quantity_unit, title):
            for m in _QTY.finditer(src or ""):
                if _UNIT[m.group(2).lower()] == "adet":
                    candidates.append((float(m.group(1).replace(",", ".")), "adet"))
    for src in (volume_or_weight, quantity_unit, title):
        parsed = _parse(src)
        if parsed:
            candidates.append(parsed)
    for qty, unit in candidates:
        if qty <= 0:
            continue
        try:
            return to_base_quantity(ingredient, qty, unit)
        except UnitConversionError:
            continue
    return None
