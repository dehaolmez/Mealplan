import httpx
import pytest

from app.domain.chain_matcher import build_patterns, match_chain, normalize
from app.domain.geo import cache_key, haversine_m, in_turkey
from app.domain.osm import build_query, parse_elements
from app.services import overpass_client

# Kadıköy civarı (kamuya açık bir nokta)
LAT, LON = 40.9903, 29.0290

OVERPASS_PAYLOAD = {
    "elements": [
        {"type": "node", "id": 1, "lat": 40.9910, "lon": 29.0295, "tags": {"shop": "supermarket", "name": "BİM", "brand": "BİM"}},
        {"type": "node", "id": 2, "lat": 40.9920, "lon": 29.0300, "tags": {"shop": "supermarket", "name": "A-101 Moda"}},
        {"type": "way", "id": 3, "center": {"lat": 40.9890, "lon": 29.0270},
         "tags": {"shop": "supermarket", "name": "Migros Jet", "addr:street": "Bahariye Cd.", "addr:housenumber": "5",
                  "addr:city": "İstanbul", "opening_hours": "09:00-22:00"}},
        {"type": "node", "id": 4, "lat": 40.9905, "lon": 29.0285, "tags": {"shop": "convenience", "name": "Yıldız Bakkal"}},
        {"type": "node", "id": 5, "lat": 40.9930, "lon": 29.0310, "tags": {"shop": "supermarket", "name": "Şok Market"}},
        {"type": "node", "id": 6, "lat": 41.2000, "lon": 29.0310, "tags": {"shop": "supermarket", "name": "BIM"}},  # uzak
        {"type": "relation", "id": 7, "tags": {"shop": "supermarket"}},  # koordinatsız: atlanmalı
    ]
}


def test_haversine_and_bbox():
    # Kadıköy - Taksim yaklaşık 5 km
    assert 4_000 < haversine_m(40.9903, 29.0290, 41.0369, 28.9850) < 7_000
    assert in_turkey(39.93, 32.85) and not in_turkey(48.85, 2.35)
    assert cache_key(40.99031, 29.02904, 1200) == "40.9903:29.029:1500"
    assert cache_key(40.99031, 29.02904, 1200, decimals=3) == "40.99:29.029:1500"


def test_normalize_turkish():
    assert normalize("BİM") == normalize("Bim") == normalize("BIM") == "bim"
    assert normalize("ŞOK Market!") == "sok market"
    assert normalize("A-101") == "a 101"


def test_chain_matching_prefers_brand_and_longer_aliases():
    patterns = build_patterns([(1, "BİM", "bim"), (2, "Migros", "migros,migros jet"), (3, "File", "file")])
    assert match_chain(patterns, None, "Bim Birleşik Mağazalar") == 1
    assert match_chain(patterns, "Migros", "Bir şey") == 2
    assert match_chain(patterns, None, "Profile Kırtasiye") is None  # 'file' tam kelime değil
    assert match_chain(patterns, None, "Mahalle Bakkalı") is None


def test_query_and_parsing():
    assert "around:1500,40.99,29.03" in build_query(40.99, 29.03, 1500)
    shops = parse_elements(OVERPASS_PAYLOAD)
    assert len(shops) == 6
    way = next(s for s in shops if s.osm_type == "way")
    assert way.lat == 40.9890 and way.address == "Bahariye Cd. 5, İstanbul" and way.opening_hours


@pytest.fixture
def fake_overpass(monkeypatch):
    calls = []

    def fake_fetch(lat, lon, radius):
        calls.append((lat, lon, radius))
        return parse_elements(OVERPASS_PAYLOAD)

    monkeypatch.setattr(overpass_client, "fetch_shops", fake_fetch)
    return calls


def test_nearby_endpoint_matches_chains_sorts_and_caches(client, fake_overpass):
    r = client.get("/api/places/nearby", params={"lat": LAT, "lon": LON, "radius_m": 1000})
    assert r.status_code == 200, r.text
    data = r.json()
    names = [p["chain"]["slug"] for p in data["places"]]
    assert set(names) == {"bim", "a101", "migros", "sok"}  # bakkal (zincir değil) ve uzak şube elendi
    dists = [p["distance_m"] for p in data["places"]]
    assert dists == sorted(dists)
    assert data["chains"][0]["nearest_m"] == dists[0]
    assert data["from_cache"] is False
    # gönderilen konum ~11 m'ye (4 ondalık) yuvarlanmış olmalı
    assert fake_overpass[0][:2] == (40.9903, 29.029)

    again = client.get("/api/places/nearby", params={"lat": LAT, "lon": LON, "radius_m": 1000}).json()
    assert again["from_cache"] is True and len(fake_overpass) == 1

    all_shops = client.get("/api/places/nearby", params={"lat": LAT, "lon": LON, "radius_m": 1000, "only_chains": False}).json()
    assert any(p["chain"] is None for p in all_shops["places"])


def test_nearby_requires_location_and_turkey(client, fake_overpass):
    assert client.get("/api/places/nearby").status_code == 400  # demo hanede ev konumu yok
    assert client.get("/api/places/nearby", params={"lat": 48.85, "lon": 2.35}).status_code == 400
    client.patch("/api/household", json={"home_lat": 40.990345, "home_lon": 29.029012})
    hh = client.get("/api/household").json()
    assert (hh["home_lat"], hh["home_lon"]) == (40.9903, 29.029)
    assert client.get("/api/places/nearby").status_code == 200


def test_overpass_failure_is_reported(client, monkeypatch):
    def boom(*_):
        raise overpass_client.MapDataUnavailable("Harita verisine ulaşılamadı")

    monkeypatch.setattr(overpass_client, "fetch_shops", boom)
    r = client.get("/api/places/nearby", params={"lat": LAT, "lon": LON})
    assert r.status_code == 400 and "Harita" in r.json()["detail"]


def test_overpass_client_falls_back_to_next_endpoint(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    seen = []

    def fake_post(url, **kwargs):
        seen.append(url)
        if len(seen) == 1:
            raise httpx.ConnectError("reset")
        return httpx.Response(200, json=OVERPASS_PAYLOAD, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    shops = overpass_client.fetch_shops(LAT, LON, 1000)
    assert len(shops) == 6 and len(seen) == 2
    assert "Meall" in get_settings().http_user_agent


def test_chains_listed(client):
    chains = client.get("/api/chains").json()
    slugs = {c["slug"] for c in chains}
    assert {"bim", "a101", "sok", "migros", "carrefoursa", "hakmar", "tarim-kredi"} <= slugs
    assert all(not c["has_prices"] for c in chains)  # yalnız demo fiyat var
