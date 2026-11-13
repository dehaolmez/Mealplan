"""Yakındaki marketler: OSM şubelerini çeker, zincirle eşleştirir, önbelleğe alır ve mesafeye göre sıralar."""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.chain_matcher import build_patterns, match_chain
from app.domain.geo import cache_key, haversine_m, in_turkey, round_coord
from app.models import Chain, Place, PlaceQuery, Store
from app.schemas.places import ChainOut, ChainSummaryOut, NearbyOut, PlaceOut
from app.services import overpass_client
from app.services.errors import BadRequest


def list_chains(db: Session) -> list[Chain]:
    return list(db.scalars(select(Chain).order_by(Chain.name)))


def chains_with_prices(db: Session) -> dict[int, str]:
    """Fiyat listesi bulunan zincirler → "real" (gerçek veri) veya "test" (yalnız test verisi)."""
    out: dict[int, str] = {}
    for chain_id, is_test in db.execute(select(Store.chain_id, Store.is_demo).where(Store.chain_id.is_not(None))):
        if not is_test or chain_id not in out:
            out[chain_id] = "test" if is_test else "real"
    return out


def chain_out(chain: Chain, priced: dict[int, str]) -> ChainOut:
    return ChainOut(
        id=chain.id, slug=chain.slug, name=chain.name, kind=chain.kind, parent=chain.parent, website=chain.website,
        color=chain.color, in_market_fiyati=chain.in_market_fiyati, has_prices=chain.id in priced,
        price_source=priced.get(chain.id),
    )


def _refresh_area(db: Session, key: str, lat: float, lon: float, radius_m: int) -> list[Place]:
    shops = overpass_client.fetch_shops(lat, lon, radius_m)
    patterns = build_patterns((c.id, c.name, c.aliases) for c in list_chains(db))
    now = datetime.now()
    places: list[Place] = []
    for shop in shops:
        place = db.scalar(select(Place).where(Place.osm_type == shop.osm_type, Place.osm_id == shop.osm_id))
        if place is None:
            place = Place(osm_type=shop.osm_type, osm_id=shop.osm_id)
            db.add(place)
        place.name, place.brand, place.shop = shop.name, shop.brand, shop.shop
        place.lat, place.lon = shop.lat, shop.lon
        place.address, place.opening_hours = shop.address, shop.opening_hours
        place.chain_id = match_chain(patterns, shop.brand, shop.name)
        place.fetched_at = now
        places.append(place)
    db.flush()
    cached = db.get(PlaceQuery, key) or PlaceQuery(key=key)
    cached.fetched_at = now
    cached.place_ids = ",".join(str(p.id) for p in places)
    db.merge(cached)
    db.commit()
    return places


def _cached_area(db: Session, key: str) -> list[Place] | None:
    cached = db.get(PlaceQuery, key)
    ttl = timedelta(hours=get_settings().places_cache_hours)
    if cached is None or datetime.now() - cached.fetched_at > ttl:
        return None
    ids = [int(x) for x in cached.place_ids.split(",") if x]
    if not ids:
        return []
    return list(db.scalars(select(Place).where(Place.id.in_(ids))))


def nearby(
    db: Session,
    lat: float,
    lon: float,
    radius_m: int,
    *,
    only_chains: bool = True,
    chain_ids: list[int] | None = None,
    refresh: bool = False,
    limit: int = 100,
) -> NearbyOut:
    s = get_settings()
    if not in_turkey(lat, lon):
        raise BadRequest("Konum Türkiye sınırları dışında görünüyor")
    radius_m = max(200, min(radius_m, s.places_max_radius_m))
    # Konumu ayarlı hassasiyete (varsayılan ~11 m) yuvarla: dış servise tam konum gönderilmez
    qlat, qlon = round_coord(lat, s.location_precision), round_coord(lon, s.location_precision)
    key = cache_key(qlat, qlon, radius_m, s.location_precision)

    places = None if refresh else _cached_area(db, key)
    from_cache = places is not None
    if places is None:
        try:
            places = _refresh_area(db, key, qlat, qlon, radius_m)
        except overpass_client.MapDataUnavailable as exc:
            raise BadRequest(str(exc)) from exc

    priced = chains_with_prices(db)
    results: list[PlaceOut] = []
    for p in places:
        if only_chains and p.chain_id is None:
            continue
        if chain_ids and p.chain_id not in chain_ids:
            continue
        distance = haversine_m(lat, lon, p.lat, p.lon)
        if distance > radius_m:
            continue
        results.append(
            PlaceOut(
                id=p.id, name=p.name or (p.chain.name if p.chain else "Market"), brand=p.brand, shop=p.shop,
                lat=p.lat, lon=p.lon, address=p.address, opening_hours=p.opening_hours,
                distance_m=round(distance), chain=chain_out(p.chain, priced) if p.chain else None,
                osm_url=f"https://www.openstreetmap.org/{p.osm_type}/{p.osm_id}",
            )
        )
    results.sort(key=lambda r: r.distance_m)

    summary: dict[int, ChainSummaryOut] = {}
    for r in results:
        if r.chain is None:
            continue
        item = summary.get(r.chain.id)
        if item is None:
            summary[r.chain.id] = ChainSummaryOut(chain=r.chain, count=1, nearest_m=r.distance_m, nearest_place_id=r.id)
        else:
            item.count += 1
    return NearbyOut(
        lat=lat, lon=lon, radius_m=radius_m, from_cache=from_cache,
        chains=sorted(summary.values(), key=lambda c: c.nearest_m),
        places=results[:limit],
    )


def nearby_chain_ids(db: Session, lat: float, lon: float, radius_m: int) -> set[int]:
    out = nearby(db, lat, lon, radius_m, only_chains=True, limit=10_000)
    return {c.chain.id for c in out.chains}
