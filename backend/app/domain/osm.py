"""Overpass API sorgu üretimi ve yanıt ayrıştırma (ağdan bağımsız, test edilebilir)."""

from dataclasses import dataclass

# Gıda alışverişi yapılabilecek OSM dükkân türleri
SHOP_TYPES = ("supermarket", "convenience", "wholesale", "greengrocer", "department_store")


@dataclass(frozen=True)
class OsmShop:
    osm_type: str
    osm_id: int
    lat: float
    lon: float
    name: str
    brand: str
    shop: str
    address: str
    opening_hours: str


def build_query(lat: float, lon: float, radius_m: int, timeout_s: int = 25) -> str:
    shops = "|".join(SHOP_TYPES)
    return (
        f"[out:json][timeout:{timeout_s}];"
        f'nwr["shop"~"^({shops})$"](around:{int(radius_m)},{lat},{lon});'
        "out center tags;"
    )


def _address(tags: dict[str, str]) -> str:
    street = " ".join(x for x in (tags.get("addr:street"), tags.get("addr:housenumber")) if x)
    parts = [street, tags.get("addr:neighbourhood") or tags.get("addr:suburb"), tags.get("addr:district"), tags.get("addr:city")]
    return ", ".join(p for p in parts if p)


def parse_elements(payload: dict) -> list[OsmShop]:
    shops: list[OsmShop] = []
    for el in payload.get("elements", []):
        tags = el.get("tags") or {}
        if el.get("type") == "node":
            lat, lon = el.get("lat"), el.get("lon")
        else:  # way / relation: "out center" ile merkez noktası gelir
            center = el.get("center") or {}
            lat, lon = center.get("lat"), center.get("lon")
        if lat is None or lon is None:
            continue
        shops.append(
            OsmShop(
                osm_type=el.get("type", "node"),
                osm_id=int(el["id"]),
                lat=float(lat),
                lon=float(lon),
                name=tags.get("name") or tags.get("brand") or "",
                brand=tags.get("brand") or "",
                shop=tags.get("shop", ""),
                address=_address(tags),
                opening_hours=tags.get("opening_hours", ""),
            )
        )
    return shops
