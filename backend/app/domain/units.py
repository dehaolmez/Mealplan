"""Birim dönüşümleri. Her malzeme tek bir temel birimde (g / ml / adet) tutulur."""

from app.models.catalog import Ingredient
from app.models.enums import BaseUnit

# Kullanıcının girebileceği birim -> (temel birim, çarpan)
_UNIT_ALIASES: dict[str, tuple[BaseUnit, float]] = {
    "g": (BaseUnit.g, 1),
    "gr": (BaseUnit.g, 1),
    "kg": (BaseUnit.g, 1000),
    "ml": (BaseUnit.ml, 1),
    "l": (BaseUnit.ml, 1000),
    "lt": (BaseUnit.ml, 1000),
    "adet": (BaseUnit.piece, 1),
    "piece": (BaseUnit.piece, 1),
}


class UnitConversionError(ValueError):
    pass


def to_base_quantity(ingredient: Ingredient, quantity: float, unit: str | None) -> float:
    """Kullanıcı girdisini malzemenin temel birimine çevirir.

    Boyutlar arası (ör. adet -> g) dönüşüm, katalogdaki `grams_per_piece` / `density_g_per_ml`
    değerleri üzerinden yapılır.
    """
    if unit is None or unit == "":
        return quantity
    key = unit.strip().lower()
    if key not in _UNIT_ALIASES:
        raise UnitConversionError(f"Bilinmeyen birim: {unit}")
    src_unit, factor = _UNIT_ALIASES[key]
    amount = quantity * factor
    target = ingredient.base_unit
    if src_unit == target:
        return amount

    grams = _to_grams(ingredient, amount, src_unit)
    return _from_grams(ingredient, grams, target)


def to_grams(ingredient: Ingredient, base_quantity: float) -> float:
    """Temel birimdeki miktarın gram karşılığı (besin değeri hesabı için)."""
    return _to_grams(ingredient, base_quantity, ingredient.base_unit)


def _to_grams(ingredient: Ingredient, amount: float, unit: BaseUnit) -> float:
    if unit == BaseUnit.g:
        return amount
    if unit == BaseUnit.ml:
        return amount * (ingredient.density_g_per_ml or 1.0)
    if ingredient.grams_per_piece:
        return amount * ingredient.grams_per_piece
    raise UnitConversionError(f"{ingredient.name} için adet->gram dönüşümü tanımlı değil")


def _from_grams(ingredient: Ingredient, grams: float, unit: BaseUnit) -> float:
    if unit == BaseUnit.g:
        return grams
    if unit == BaseUnit.ml:
        return grams / (ingredient.density_g_per_ml or 1.0)
    if ingredient.grams_per_piece:
        return grams / ingredient.grams_per_piece
    raise UnitConversionError(f"{ingredient.name} için gram->adet dönüşümü tanımlı değil")


def humanize(quantity: float, unit: BaseUnit) -> str:
    """1500 g -> '1,5 kg', 3 adet -> '3 adet'."""
    if unit == BaseUnit.g and quantity >= 1000:
        return f"{_fmt(quantity / 1000)} kg"
    if unit == BaseUnit.ml and quantity >= 1000:
        return f"{_fmt(quantity / 1000)} l"
    return f"{_fmt(quantity)} {unit.value}"


def _fmt(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")
