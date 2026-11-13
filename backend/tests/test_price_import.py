from app.domain.osm import parse_elements
from app.services import overpass_client
from tests.test_places import LAT, LON, OVERPASS_PAYLOAD

CSV = """chain;ingredient;package_size;unit;price;brand;date
bim;Patlıcan;1;kg;29,90;;2026-11-10
Migros;Patlıcan;1;kg;44,90;;2026-11-10
bim;Kıyma;500;g;279,90;;2026-11-10
bilinmeyen;Patlıcan;1;kg;10;;
bim;Ejder meyvesi;1;kg;10;;
bim;Patlıcan;1;fincan;10;;
"""


def test_csv_import_creates_real_stores_and_reports_errors(client):
    r = client.post("/api/prices/import", content=CSV.encode(), headers={"content-type": "text/csv"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["created"] == 3 and set(out["stores_created"]) == {"BİM", "Migros"}
    assert [e["line"] for e in out["errors"]] == [5, 6, 7]

    # aynı veri tekrar: güncelleme sayılır, yeni kayıt açılmaz; daha eski tarih üzerine yazmaz
    again = client.post("/api/prices/import", content=CSV.encode()).json()
    assert again["created"] == 0 and again["updated"] == 3
    stale = client.post("/api/prices/import", content=b"chain,ingredient,package_size,unit,price,date\nbim,Patl\xc4\xb1can,1,kg,1,2020-01-01\n").json()
    assert stale["updated"] == 0
    chains = {c["slug"]: c for c in client.get("/api/chains").json()}
    assert chains["bim"]["has_prices"] and chains["migros"]["has_prices"]
    stats = {s["store"]: s for s in client.get("/api/prices/stats").json()}
    assert stats["BİM"]["prices"] == 2 and stats["BİM"]["is_demo"] is False


def test_csv_missing_columns(client):
    r = client.post("/api/prices/import", content=b"chain,price\nbim,1\n")
    assert r.status_code == 400 and "ingredient" in r.json()["detail"]


def test_template_downloads(client):
    r = client.get("/api/prices/template.csv")
    assert r.status_code == 200 and r.text.startswith("chain,ingredient")


def test_nearby_only_optimization_uses_nearby_real_prices(client, monkeypatch):
    monkeypatch.setattr(overpass_client, "fetch_shops", lambda *a: parse_elements(OVERPASS_PAYLOAD))
    recipes = {r["name"]: r["id"] for r in client.get("/api/recipes").json()}
    body = {"selections": [{"recipe_id": recipes["Karnıyarık"]}], "nearby_only": True, "lat": LAT, "lon": LON}

    # Gerçek fiyat yokken: anlaşılır hata
    r = client.post("/api/shopping/optimize", json=body)
    assert r.status_code == 400 and "fiyat verisi yok" in r.json()["detail"]

    client.post("/api/prices/import", content=CSV.encode())
    # hanenin seçili market listesini temizle ki tüm marketler (gerçekler dahil) aday olsun
    client.patch("/api/household", json={"selected_store_ids": []})
    out = client.post("/api/shopping/optimize", json=body).json()
    eggplant = next(p for p in out["purchases"] if p["name"] == "Patlıcan")
    assert eggplant["store_name"] == "BİM" and eggplant["cost"] == 29.9
    assert {t["store_name"] for t in out["store_totals"]} == {"BİM", "Migros"}  # demo marketler elendi
