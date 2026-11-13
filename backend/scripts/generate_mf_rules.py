"""Genişletilmiş katalog için Market Fiyatı eşleştirme kurallarını gerçek veriden çıkarır
→ app/seed/marketfiyati_rules_extra.json

Her malzeme adıyla (pilot bölge şubelerinde) arama yapılır; başlığında malzeme adı geçen ürünlerin en sık
görülen ana kategorisi kurala yazılır. Eşleşme bulunamayan malzemeler için kural yazılmaz (o malzemenin canlı
fiyatı olmaz, diğer kaynaklar kullanılır). Saniyede en fazla bir istek atılır.
"""

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.domain.chain_matcher import normalize  # noqa: E402
from app.seed.marketfiyati_rules import RULES  # noqa: E402
from app.services import marketfiyati  # noqa: E402

SEED = Path(__file__).resolve().parents[1] / "app" / "seed"
OUT = SEED / "marketfiyati_rules_extra.json"
DEFAULT_EXCLUDE = ["suyu", "aromali", "cips", "sos", "tursu", "kremali", "bebek", "mama", "sampuan", "sabun", "deterjan"]


def main() -> None:
    s = get_settings()
    extra = json.loads((SEED / "catalog_extra.json").read_text(encoding="utf-8"))
    rules = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    depots = [d["id"] for d in marketfiyati._post("/api/v2/nearest", {
        "latitude": round(s.pilot_lat, 2), "longitude": round(s.pilot_lon, 2), "distance": 3})]
    for item in extra:
        name = item["name"]
        if item["is_staple"] or name in RULES or name in rules:
            continue
        q = name.lower()
        data = marketfiyati._post("/api/v2/search", {"keywords": q, "depots": depots, "pages": 0, "size": 60,
                                                     "latitude": round(s.pilot_lat, 2), "longitude": round(s.pilot_lon, 2),
                                                     "distance": 3})
        key = f" {normalize(name)}"
        own_excl = [x for x in DEFAULT_EXCLUDE if x not in normalize(name)]
        hits = [p for p in data.get("content", []) if key in f" {normalize(p.get('title', ''))} "
                and not any(x in normalize(p.get("title", "")) for x in own_excl)]
        cats = Counter(p.get("main_category") for p in hits)
        if not cats:
            print(f"  eşleşme yok: {name}", file=sys.stderr)
            rules[name] = None
        else:
            top, n = cats.most_common(1)[0]
            chosen = [c for c, k in cats.most_common(3) if k >= max(2, n * 0.4)] or [top]
            rules[name] = {"q": q, "cats": chosen, "any": [name], "exclude": own_excl}
            print(f"{name:24} {len(hits):3} → {chosen}", file=sys.stderr)
        OUT.write_text(json.dumps(rules, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
