"""Malzeme kataloğunu Gemini ile genişletir → app/seed/catalog_extra.json

Gemini yalnız taslak üretir; çıktı burada doğrulanır (kalori ↔ makro tutarlılığı, tekrar eden ad, birim/etiket
geçerliliği). Değerler 100 g başına ortalama besin değeridir (TÜRKOMP/USDA mertebesinde).

Kullanım:  MEALBIRD_GEMINI_API_KEY=... python scripts/generate_catalog.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.seed.data import INGREDIENTS  # noqa: E402
from app.services import gemini  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "app" / "seed" / "catalog_extra.json"
CATEGORIES = ["Manav", "Süt Ürünleri", "Et & Balık", "Fırın", "Temel Gıda", "Dondurulmuş", "Baharat & Sos", "İçecek", "Diğer"]
TAGS = ["red_meat", "poultry", "fish", "shellfish", "pork", "dairy", "egg", "gluten", "nuts", "peanut", "sesame", "soy", "honey", "carb"]

SYSTEM = f"""Türk ev mutfağı için bir malzeme kataloğu hazırlıyorsun. Mevcut katalogda OLMAYAN, Türkiye'deki
marketlerde kolayca bulunan ve ev yemeklerinde sık kullanılan malzemeleri ekle (sebze, meyve, otlar, bakliyat,
tahıl, süt ürünleri, et/balık, konserve, sos, baharat, kuruyemiş, hamur işleri). Domuz ürünü ekleme.
Her malzeme için:
- name: Türkçe, kısa, market rafındaki yaygın ad (ör. "Pırasa", "Kuru fasulye", "Tahin").
- category: {CATEGORIES}
- base_unit: g, ml veya adet (meyve/sebzede tek tek sayılanlar adet olabilir; çoğu g).
- grams_per_piece: base_unit adet ise bir adedin ortalama gramı, değilse null.
- density_g_per_ml: base_unit ml ise yoğunluk, değilse null.
- kcal/protein/carbs/fat: 100 g başına ortalama değerler (çiğ/kuru hâl).
- shelf_life_fridge_days / freezer_days / opened_days: buzdolabında, dondurucuda ve açıldıktan sonra ortalama gün;
  oda sıcaklığında saklananlarda (bakliyat vb.) buzdolabı için null.
- is_staple: tuz, karabiber, kuru baharatlar gibi her evde olduğu varsayılanlar true.
- diet_tags: {TAGS} içinden uygun olanlar (carb: pirinç/makarna/ekmek/patates gibi yüksek nişastalılar).
- emoji: tek uygun emoji."""

SCHEMA = {
    "type": "object",
    "properties": {"items": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "name": {"type": "string"}, "category": {"type": "string", "enum": CATEGORIES},
            "base_unit": {"type": "string", "enum": ["g", "ml", "adet"]},
            "grams_per_piece": {"type": ["number", "null"]}, "density_g_per_ml": {"type": ["number", "null"]},
            "kcal": {"type": "number"}, "protein": {"type": "number"}, "carbs": {"type": "number"}, "fat": {"type": "number"},
            "shelf_life_fridge_days": {"type": ["integer", "null"]}, "shelf_life_freezer_days": {"type": ["integer", "null"]},
            "shelf_life_opened_days": {"type": ["integer", "null"]}, "is_staple": {"type": "boolean"},
            "diet_tags": {"type": "array", "items": {"type": "string", "enum": TAGS}}, "emoji": {"type": "string"},
        },
        "required": ["name", "category", "base_unit", "grams_per_piece", "density_g_per_ml", "kcal", "protein", "carbs",
                     "fat", "shelf_life_fridge_days", "shelf_life_freezer_days", "shelf_life_opened_days", "is_staple",
                     "diet_tags", "emoji"],
    }}},
    "required": ["items"],
}

GROUPS = [
    "35 sebze, yeşillik ve meyve (pırasa, ıspanak dışı yeşillikler, kök sebzeler, mevsim meyveleri)",
    "30 bakliyat, tahıl, hamur işi, konserve ve kuru gıda (kuru fasulye, yeşil mercimek, şehriye, yufka, ton balığı...)",
    "25 süt ürünü, et, tavuk, balık ve şarküteri",
    "30 baharat, ot, sos, yağ, kuruyemiş, tatlandırıcı ve diğer (kekik, sumak, tahin, nar ekşisi, ceviz...)",
]


def valid(item: dict) -> str | None:
    p, c, f, k = item["protein"], item["carbs"], item["fat"], item["kcal"]
    if min(p, c, f, k) < 0 or p + c + f > 101:
        return "makrolar geçersiz"
    calc = 4 * p + 4 * c + 9 * f
    if k > 30 and abs(calc - k) / k > 0.25:  # lif/alkol farkları için geniş tolerans
        return f"kalori tutarsız ({k} ≠ ~{calc:.0f})"
    if item["base_unit"] == "adet" and not item["grams_per_piece"]:
        return "adet ama gram karşılığı yok"
    return None


def main() -> None:
    names = {row[0].lower() for row in INGREDIENTS}
    out: list[dict] = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else []
    names |= {i["name"].lower() for i in out}
    done_groups = {i.get("group") for i in out}
    for group in GROUPS:
        if group in done_groups:
            continue
        existing = sorted(names)
        data = gemini.generate_json(SYSTEM, f"Mevcut katalog: {', '.join(existing)}\n\nŞimdi şunları ekle: {group}",
                                    SCHEMA, name="catalog", timeout=180, rounds=4)
        for item in data["items"]:
            key = item["name"].strip().lower()
            if key in names:
                continue
            err = valid(item)
            if err:
                print(f"  atlandı: {item['name']} — {err}", file=sys.stderr)
                continue
            item["name"] = item["name"].strip()
            item["group"] = group
            names.add(key)
            out.append(item)
        OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")  # her gruptan sonra kaydet
        print(f"{group[:40]}… → toplam {len(out)}", file=sys.stderr)
    print(f"{len(out)} malzeme yazıldı: {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
