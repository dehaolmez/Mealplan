"""Fiş fotoğrafından envantere ekleme (Gemini görsel okuma).

Akış: fotoğraf → Gemini satırları ve her satır için katalogdaki en uygun malzemeyi döndürür → kullanıcı
taslağı kontrol eder/düzeltir → onaylanan satırlar envantere eklenir. Fotoğraf sunucuda saklanmaz.
"""

import base64
import binascii
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.chain_matcher import build_patterns, match_chain, normalize
from app.domain.units import UnitConversionError, humanize, to_base_quantity
from app.models import Chain, Household, Ingredient
from app.models.enums import Category, StorageLocation
from app.schemas.inventory import InventoryItemIn
from app.services import gemini, inventory_service
from app.services.errors import BadRequest

MAX_IMAGE_BYTES = 6 * 1024 * 1024
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}

SYSTEM = """Sen bir Türk market fişi okuyucususun. Fotoğraftaki fişten satın alınan GIDA ürünlerini çıkar.
- Poşet, indirim, KDV, toplam, ödeme satırlarını ve gıda dışı ürünleri (deterjan, kozmetik vb.) atla.
- quantity: tartılı ürünlerde kg/gr miktarı, diğerlerinde adet/paket sayısı. Paket üzerinde gramaj/hacim yazıyorsa
  (ör. "SÜT 1L", "MAKARNA 500G") quantity ve unit paketin toplam içeriği olsun (ör. 2 adet 1L süt → 2, "l").
- unit: kg, g, l, ml veya adet.
- line_total: satırın TL toplamı (yoksa null).
- catalog_name: verilen katalog listesinden bu ürüne en uygun ad; uygun yoksa null. Yalnız listedeki adları kullan.
- store_name: fişin başındaki market adı; date: fiş tarihi YYYY-AA-GG (okunamıyorsa null)."""

SCHEMA = {
    "type": "object",
    "properties": {
        "store_name": {"type": ["string", "null"]},
        "date": {"type": ["string", "null"]},
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "raw_text": {"type": "string"},
                    "catalog_name": {"type": ["string", "null"]},
                    "quantity": {"type": "number"},
                    "unit": {"type": "string", "enum": ["kg", "g", "l", "ml", "adet"]},
                    "line_total": {"type": ["number", "null"]},
                },
                "required": ["raw_text", "catalog_name", "quantity", "unit", "line_total"],
            },
        },
    },
    "required": ["store_name", "date", "lines"],
}


_DIM = {"kg": "mass", "g": "mass", "l": "volume", "ml": "volume", "adet": "piece"}
_BASE_DIM = {"g": "mass", "ml": "volume", "adet": "piece"}


def _convertible(ing: Ingredient, unit: str | None) -> bool:
    """Anlamsız boyut dönüşümlerini engeller (ör. "1 l yumurta")."""
    src, dst = _DIM.get((unit or "").lower()), _BASE_DIM[ing.base_unit.value]
    if src is None or src == dst:
        return src is not None
    if {src, dst} == {"mass", "piece"}:
        return bool(ing.grams_per_piece)
    if {src, dst} == {"mass", "volume"}:
        return bool(ing.density_g_per_ml)
    return False


def scan(db: Session, image_base64: str, mime_type: str) -> dict:
    if mime_type not in ALLOWED_MIME:
        raise BadRequest("Desteklenmeyen görsel türü (JPEG, PNG, WEBP veya HEIC)")
    try:
        raw = base64.b64decode(image_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise BadRequest("Görsel çözümlenemedi") from exc
    if len(raw) > MAX_IMAGE_BYTES:
        raise BadRequest("Görsel çok büyük (en fazla 6 MB)")

    ingredients = {i.name: i for i in db.scalars(select(Ingredient).where(Ingredient.is_staple.is_(False)))}
    content = [
        {"type": "text", "text": "Katalog: " + ", ".join(sorted(ingredients))},
        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_base64}"}},
    ]
    try:
        data = gemini.generate_json(SYSTEM, content, SCHEMA, name="receipt", timeout=120)
    except gemini.GeminiError as exc:
        raise BadRequest(str(exc)) from exc
    return build_draft(db, data, ingredients)


def build_draft(db: Session, data: dict, ingredients: dict[str, Ingredient] | None = None) -> dict:
    """Model çıktısını doğrulanmış, katalogla eşlenmiş taslağa çevirir (saf mantık; test edilebilir)."""
    if ingredients is None:
        ingredients = {i.name: i for i in db.scalars(select(Ingredient).where(Ingredient.is_staple.is_(False)))}
    by_norm = {normalize(n): i for n, i in ingredients.items()}
    patterns = build_patterns((c.id, c.name, c.aliases) for c in db.scalars(select(Chain)))
    chain_id = match_chain(patterns, data.get("store_name"))
    chain = db.get(Chain, chain_id) if chain_id else None

    receipt_date = None
    try:
        receipt_date = date.fromisoformat(data["date"]) if data.get("date") else None
    except ValueError:
        pass

    lines = []
    for raw in data.get("lines", [])[:80]:
        ing = by_norm.get(normalize(raw.get("catalog_name") or ""))
        qty, unit = raw.get("quantity"), raw.get("unit")
        base_qty = None
        if ing and isinstance(qty, (int, float)) and qty > 0 and _convertible(ing, unit):
            try:
                base_qty = round(to_base_quantity(ing, float(qty), unit), 2)
            except UnitConversionError:
                base_qty = None
        lines.append({
            "raw_text": str(raw.get("raw_text", ""))[:120],
            "ingredient_id": ing.id if ing else None,
            "ingredient_name": ing.name if ing else None,
            "emoji": ing.emoji if ing else "🛒",
            "quantity": base_qty,
            "unit": ing.base_unit.value if ing else unit,
            "quantity_label": humanize(base_qty, ing.base_unit) if ing and base_qty else None,
            "line_total": raw.get("line_total"),
            "location": (StorageLocation.freezer if ing and ing.category == Category.frozen else StorageLocation.fridge).value,
            "selected": bool(ing and base_qty),
        })
    return {
        "store_name": data.get("store_name"),
        "chain": {"id": chain.id, "name": chain.name} if chain else None,
        "date": receipt_date.isoformat() if receipt_date else None,
        "lines": lines,
    }


def confirm(db: Session, household: Household, lines: list[dict], purchase_date: date | None) -> int:
    added = 0
    for line in lines:
        inventory_service.add_item(db, household, InventoryItemIn(
            ingredient_id=line["ingredient_id"], quantity=line["quantity"], unit=line.get("unit"),
            location=StorageLocation(line.get("location", "fridge")), expiry_date=line.get("expiry_date"),
            added_on=purchase_date,
        ))
        added += 1
    return added
