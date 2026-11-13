import pytest
from sqlalchemy import select

from app.domain.packages import package_base_quantity
from app.models import Ingredient
from app.seed.marketfiyati_rules import RULES
from app.services import marketfiyati


def _ing(db, name):
    return db.scalar(select(Ingredient).where(Ingredient.name == name))


def product(title, cat, price_by_market, vw=None, qu=None, pid="X1"):
    return {
        "id": pid, "title": title, "brand": "", "main_category": cat, "refinedVolumeOrWeight": vw,
        "refinedQuantityUnit": qu,
        "productDepotInfoList": [
            {"depotId": f"{m}-1", "depotName": f"{m} şube", "price": p, "marketAdi": m, "indexTime": "13.11.2026 07:37"}
            for m, p in price_by_market
        ],
    }


@pytest.mark.parametrize(("title", "vw", "qu", "name", "expected"), [
    ("Domates 1 Kg", "1 KG", None, "Domates", 1000),
    ("Tukaş Domates Salçası 1.65 Kg", "1.65 KG", None, "Domates salçası", 1650),
    ("İçim Süt 1 Lt", "1 LT", None, "Süt", 1000),
    ("Yumurta Gezen 53-62 Gr 10 Adet", "62 GR", None, "Yumurta", 10),  # ağırlık değil adet
    ("Yumurta M Boy 30 Adet", None, "30 Adet", "Yumurta", 30),
    ("Limon 1 Kg", "1 KG", None, "Limon", 10),  # 100 g/adet
    ("Maydanoz 1 Adet", None, "1 Adet", "Maydanoz", 50),
])
def test_package_parsing(db, title, vw, qu, name, expected):
    assert package_base_quantity(_ing(db, name), title, vw, qu) == pytest.approx(expected)


def test_rules_exist_for_all_buyable_ingredients(db):
    missing = [i.name for i in db.scalars(select(Ingredient)) if not i.is_staple and i.name not in RULES]
    assert missing == [], f"Kural eksik: {missing}"


def test_rule_matching_filters_wrong_products(db):
    rule = RULES["Domates"]
    assert marketfiyati.matches_rule(product("Domates 1 Kg", "Sebze", []), rule)
    assert not marketfiyati.matches_rule(product("Tat Domates Salçası 710 Gr", "Salça", []), rule)
    assert not marketfiyati.matches_rule(product("Kokteyl Domates 1 Kg", "Sebze", []), rule)
    assert not marketfiyati.matches_rule(product("Sek Çilekli Süt 180 Ml", "Süt", []), RULES["Süt"])
    assert not marketfiyati.matches_rule(product("Söke Unlu Mamül", "Un ve İrmik", []), RULES["Un"])
    assert marketfiyati.matches_rule(product("Söke Un 5 Kg", "Un ve İrmik", []), RULES["Un"])


def test_extract_offers_takes_cheapest_depot_per_chain(db):
    p = product("Domates 1 Kg", "Sebze", [("bim", 69.0), ("bim", 72.0), ("migros", 64.9), ("bilinmeyen", 1.0)], vw="1 KG")
    offers = marketfiyati.extract_offers([p], _ing(db, "Domates"), RULES["Domates"])
    assert {(o["chain"], o["price"]) for o in offers} == {("bim", 69.0), ("migros", 64.9)}
    assert all(o["package_size"] == 1000 for o in offers)


@pytest.fixture
def fake_api(monkeypatch):
    calls = []

    def fake_post(path, body):
        calls.append((path, body))
        if path.endswith("/nearest"):
            return [{"id": "bim-1"}, {"id": "migros-1"}]
        kw = body["keywords"]
        if kw == "patlıcan":
            return {"content": [
                product("Patlıcan 1 Kg", "Sebze", [("bim", 59.0), ("migros", 139.95)], vw="1 KG", pid="P1"),
                product("Közlenmiş Patlıcan 650 Gr", "Konserve", [("bim", 10.0)], vw="650 GR", pid="P2"),
            ]}
        if kw == "kıyma":
            return {"content": [product("Dana Kıyma 400 Gr", "Kırmızı Et", [("migros", 264.0)], vw="400 GR", pid="K1")]}
        return {"content": []}

    monkeypatch.setattr(marketfiyati, "_post", fake_post)
    return calls


def test_refresh_caches_by_area_and_ingredient(db, fake_api):
    ids = [_ing(db, "Patlıcan").id, _ing(db, "Kıyma").id]
    first = marketfiyati.refresh(db, ids, 39.9496, 32.6618)
    assert first["queried"] == 2 and first["matched"] == 3
    assert [p for p, _ in fake_api].count("/api/v2/nearest") == 1
    search = next(b for p, b in fake_api if p.endswith("/search"))
    assert search["depots"] == ["bim-1", "migros-1"]
    # önbellek: ikinci çağrı istek atmaz
    n = len(fake_api)
    assert marketfiyati.refresh(db, ids, 39.9496, 32.6618)["queried"] == 0 and len(fake_api) == n
    titles = {o.title for o in marketfiyati.offers(db, first["area_key"], ids)}
    assert "Közlenmiş Patlıcan 650 Gr" not in titles  # konserve elendi


def test_optimize_prefers_live_prices_over_demo(client, fake_api, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("MEALBIRD_LIVE_PRICES_ENABLED", "true")
    get_settings.cache_clear()
    recipes = {r["name"]: r["id"] for r in client.get("/api/recipes").json()}
    out = client.post("/api/shopping/optimize", json={"selections": [{"recipe_id": recipes["Karnıyarık"], "servings": 8}]}).json()
    assert out["price_mode"] == "live" and "Etimesgut" in (out["price_note"] or "")
    eggplant = next(p for p in out["purchases"] if p["name"] == "Patlıcan")
    assert eggplant["store_name"] == "BİM" and eggplant["brand"] == "Patlıcan 1 Kg"
    assert all(t["store_name"] in {"BİM", "Migros"} for t in out["store_totals"])  # demo marketler karışmaz

    # canlı kapalıyken demo moduna düşer ve bunu açıkça söyler
    demo = client.post("/api/shopping/optimize", json={"selections": [{"recipe_id": recipes["Karnıyarık"]}], "live_prices": False}).json()
    assert demo["price_mode"] in {"demo", "real"}


def test_live_source_failure_is_reported(client, monkeypatch):
    from app.core.config import get_settings

    def boom(*_):
        raise marketfiyati.LivePricesUnavailable("Market Fiyatı'na ulaşılamadı")

    monkeypatch.setattr(marketfiyati, "_post", boom)
    monkeypatch.setenv("MEALBIRD_LIVE_PRICES_ENABLED", "true")
    get_settings.cache_clear()
    recipes = {r["name"]: r["id"] for r in client.get("/api/recipes").json()}
    out = client.post("/api/shopping/optimize", json={"selections": [{"recipe_id": recipes["Karnıyarık"]}]}).json()
    assert out["price_mode"] == "demo" and "ulaşılamadı" in out["price_note"]
