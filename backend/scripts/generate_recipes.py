"""Tarif kütüphanesini Gemini ile üretir → app/seed/recipes_generated.json

* Tarifler ÖZGÜN yazılır (başka sitelerden metin kopyalanmaz); yalnız klasik yemek adları ortaktır.
* Malzemeler JSON şemasıyla katalog adlarına kısıtlanır: eksik tespiti, kalori ve fiyat hesabı her tarifte çalışır.
* Çıktı doğrulanır: birim dönüşümü, porsiyon başı kalori aralığı, tekrar eden ad.
* Kaldığı yerden devam eder (mevcut JSON'daki tarifler yeniden üretilmez).

Kullanım:  MEALBIRD_GEMINI_API_KEY=... python scripts/generate_recipes.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.seed.data import INGREDIENTS, RECIPES  # noqa: E402
from app.services import gemini  # noqa: E402
from app.services.recipe_ai import SYSTEM_RECIPE, recipe_schema, validate  # noqa: E402

SEED = Path(__file__).resolve().parents[1] / "app" / "seed"
OUT_DIR = SEED / "recipes"
GROUPS = [
    # (dosya, kategori, varsayılan öğün, adet)
    ("Kahvaltılık (yumurtalı, hamur işi, kahvaltı tabakları, kahvaltılık sıcaklar)", "breakfast", 24),
    ("Çorbalar", "lunch", 18),
    ("Kırmızı etli ana yemekler (kıyma, kuşbaşı, köfte, güveç)", "dinner", 18),
    ("Tavuk yemekleri", "dinner", 16),
    ("Balık ve deniz ürünleri yemekleri", "dinner", 8),
    ("Sebze yemekleri ve zeytinyağlılar", "dinner", 22),
    ("Bakliyat yemekleri (kuru fasulye, nohut, mercimek...)", "lunch", 12),
    ("Pilavlar, makarnalar ve hamur işi ana yemekler", "lunch", 16),
    ("Salatalar, mezeler ve ara öğün atıştırmalıkları", "snack", 16),
]

SYSTEM_LIST = """Türk ev mutfağından, evde kolayca yapılabilen, yaygın bilinen yemek adları öner. Uluslararası ama
Türkiye'de sık yapılan ev yemekleri de olabilir. Domuz ürünü içeren yemek önerme. Ana malzemesi verilen katalogda
olmayan yemekleri (ör. kalamar, midye, işkembe, asma yaprağı, enginar) önerme. Yalnız ad listesi döndür."""

def load_catalog() -> list[dict]:
    rows = [{"name": r[0], "base_unit": r[2].value, "grams_per_piece": r[3], "density_g_per_ml": r[4],
             "kcal": r[5], "is_staple": r[12]} for r in INGREDIENTS]
    extra = SEED / "catalog_extra.json"
    if extra.exists():
        rows += [{"name": i["name"], "base_unit": i["base_unit"], "grams_per_piece": i["grams_per_piece"],
                  "density_g_per_ml": i["density_g_per_ml"], "kcal": i["kcal"], "is_staple": i["is_staple"]}
                 for i in json.loads(extra.read_text(encoding="utf-8"))]
    return rows


def main() -> None:
    import argparse

    from app.services.recipe_ai import piece_weights_note

    ap = argparse.ArgumentParser()
    ap.add_argument("--group", type=int, required=True, help="GROUPS içindeki sıra (0'dan)")
    args = ap.parse_args()
    label, default_meal, quota = GROUPS[args.group]
    out = OUT_DIR / f"{args.group + 1:02d}-{SLUGS[args.group]}.json"

    catalog_rows = load_catalog()
    catalog = {c["name"]: c for c in catalog_rows}
    names = sorted(catalog)
    existing = json.loads(out.read_text(encoding="utf-8")) if out.exists() else []
    taken = {r["name"].lower() for r in existing} | {r[0].lower() for r in RECIPES} | BLOCKLIST
    for f in OUT_DIR.glob("*.json"):  # diğer gruplarla çakışmasın
        taken |= {r["name"].lower() for r in json.loads(f.read_text(encoding="utf-8"))}
    schema = recipe_schema(names)
    note = piece_weights_note(catalog)

    attempts = 0
    while len(existing) < quota and attempts < 6:
        attempts += 1
        lst = gemini.generate_json(
            SYSTEM_LIST,
            f"Kategori: {label}. {quota - len(existing) + 4} farklı yemek adı öner. Şunları önerme: {', '.join(sorted(taken))}",
            {"type": "object", "properties": {"names": {"type": "array", "items": {"type": "string"}}},
             "required": ["names"]}, name="dish_list", timeout=120, rounds=4)
        todo = [n.strip() for n in lst["names"] if n.strip().lower() not in taken][: quota - len(existing)]
        for i in range(0, len(todo), 3):
            batch = todo[i:i + 3]
            try:
                data = gemini.generate_json(
                    SYSTEM_RECIPE,
                    f"{note}\nKategori: {label} (varsayılan öğün: {default_meal}). Şu yemeklerin tariflerini yaz: {', '.join(batch)}",
                    schema, name="recipes", timeout=240, rounds=4)
            except gemini.GeminiError as exc:
                print(f"  hata ({batch}): {exc}", file=sys.stderr)
                continue
            for r in data["recipes"]:
                if r["name"].lower() in taken:
                    continue
                err = validate(r, catalog)
                if err:
                    print(f"  atlandı: {r['name']} — {err}", file=sys.stderr)
                    continue
                r["group"] = label
                existing.append(r)
                taken.add(r["name"].lower())
            out.write_text(json.dumps(existing, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"{label[:30]}… {len(existing)}/{quota}", file=sys.stderr)
    print(f"Bitti: {len(existing)} tarif → {out}", file=sys.stderr)


# Katalogda ana malzemesi olmadığı için (model başka malzemeyle "uydurduğu") elle çıkarılanlar; yeniden üretilmez
BLOCKLIST = {"tarhana çorbası", "kelle paça çorbası", "yalancı işkembe çorbası", "gözleme çorbası", "ali nazik çorbası",
             "kalamar tava", "midye dolma", "zeytinyağlı enginar", "zeytinyağlı ispanaklı semizotu",
             "yoğurtlu semizotu salatası", "zeytinyağlı pirinçli sarma", "tas kebabı", "besleyici mercimek köftesi",
             "semizotu salatası", "fırında levrek (alabalık yerine)", "ezo gelin çorbası"}

SLUGS = ["kahvalti", "corba", "kirmizi-et", "tavuk", "balik", "sebze-zeytinyagli", "bakliyat", "pilav-makarna", "salata-meze"]


if __name__ == "__main__":
    main()
