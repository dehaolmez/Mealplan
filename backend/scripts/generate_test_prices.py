"""Pilot bölge (Ankara/Etimesgut) için TEST fiyat CSV'si üretir.

⚠️ Bu fiyatlar GERÇEK DEĞİLDİR. Demo fiyatların zincir türüne göre ölçeklenmesi ve küçük, tekrarlanabilir
(sabit tohumlu) sapmalarla üretilir. Amaç: gerçek veri gelene kadar konum filtresi ve optimizasyonun uçtan uca
denenmesi. Uygulamada "test" etiketiyle gösterilir.

Kullanım:  python scripts/generate_test_prices.py > app/seed/test_prices_etimesgut.csv
"""

import csv
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.seed.data import INGREDIENTS, PRICES  # noqa: E402

# Etimesgut'ta şubesi bulunan, Market Fiyatı platformundaki zincirler ve kabaca fiyat seviyeleri
CHAIN_LEVEL = {"bim": 0.95, "a101": 0.96, "sok": 0.98, "tarim-kredi": 0.97, "carrefoursa": 1.05, "migros": 1.08}
# İndirim marketlerinde genelde bulunmayan ürünler
NOT_IN_DISCOUNT = {"Somon", "Kuşbaşı et", "Brokoli", "Mantar", "Krema"}
UNIT = {row[0]: row[2].value for row in INGREDIENTS}


def main() -> None:
    rng = random.Random(20261113)
    w = csv.writer(sys.stdout)
    w.writerow(["chain", "ingredient", "package_size", "unit", "price", "brand", "date"])
    for name, (pack, *prices) in PRICES.items():
        base = min(p for p in prices if p is not None)
        for chain, level in CHAIN_LEVEL.items():
            if chain in {"bim", "a101", "sok"} and name in NOT_IN_DISCOUNT:
                continue
            price = round(base * level * rng.uniform(0.96, 1.04), 2)
            unit = {"adet": "adet"}.get(UNIT[name], UNIT[name])
            w.writerow([chain, name, pack, unit, f"{price:.2f}", "TEST", ""])


if __name__ == "__main__":
    main()
