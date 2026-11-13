"""TÜBİTAK "Market Fiyatı" (marketfiyati.org.tr) kamuya açık fiyat verisinden canlı fiyat çekme.

Akış: konum → yakın şubeler (/api/v2/nearest) → her malzeme için şubelere göre arama (/api/v2/search) →
kurallarla eşleşen ürünler → zincir bazında en düşük şube fiyatı → `market_products`.

Kaynağa saygı: istemci kendini tanıtır, istekler arasında en az `live_prices_min_interval_s` beklenir,
sonuçlar bölge+malzeme bazında `live_prices_ttl_hours` boyunca önbelleklenir ve yalnız gerekli malzemeler sorgulanır.
"""

import json
import logging
import math
import threading
import time
from datetime import datetime, timedelta

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.chain_matcher import normalize
from app.domain.packages import package_base_quantity
from app.models import Chain, Ingredient, LiveArea, LivePriceFetch, MarketProduct, Store
from app.seed.marketfiyati_rules import MARKET_TO_CHAIN, RULES

log = logging.getLogger(__name__)
_lock = threading.Lock()
_last_call = 0.0


class LivePricesUnavailable(Exception):
    pass


def area_key(lat: float, lon: float, radius_km: int) -> str:
    # ~1 km'lik ızgara: komşu hanelerin aynı önbelleği paylaşması için
    return f"{round(lat, 2)}:{round(lon, 2)}:{radius_km}"


def _post(path: str, body: dict) -> dict | list:
    global _last_call
    s = get_settings()
    with _lock:  # tüm süreçte istekleri sıraya koy
        wait = s.live_prices_min_interval_s - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        try:
            resp = httpx.post(
                f"{s.marketfiyati_url}{path}",
                json=body,
                headers={"User-Agent": s.http_user_agent, "Accept": "application/json"},
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LivePricesUnavailable(f"Market Fiyatı'na ulaşılamadı: {exc}") from exc
        finally:
            _last_call = time.monotonic()


# ---- saf yardımcılar (test edilebilir) ---------------------------------------------

def matches_rule(product: dict, rule: dict) -> bool:
    """Kategori uymalı; `any` ifadelerinden biri bir kelimenin başında geçmeli; `exclude` hiçbir yerde geçmemeli."""
    if product.get("main_category") not in rule["cats"]:
        return False
    title = f" {normalize(product.get('title', ''))} "
    if not any(f" {normalize(x)}" in title for x in rule["any"]):
        return False
    return not any(normalize(x) in title for x in rule.get("exclude", []))


def extract_offers(products: list[dict], ingredient: Ingredient, rule: dict) -> list[dict]:
    """Eşleşen her ürün için zincir başına en ucuz şube fiyatını döner."""
    offers = []
    for p in products:
        if not matches_rule(p, rule):
            continue
        size = package_base_quantity(ingredient, p.get("title", ""), p.get("refinedVolumeOrWeight"),
                                     p.get("refinedQuantityUnit"))
        if not size or size <= 0:
            continue
        best: dict[str, dict] = {}
        for d in p.get("productDepotInfoList", []):
            chain = MARKET_TO_CHAIN.get(d.get("marketAdi", ""))
            price = d.get("price")
            if chain is None or not price or price <= 0:
                continue
            if chain not in best or price < best[chain]["price"]:
                best[chain] = d
        for chain, d in best.items():
            offers.append({
                "chain": chain, "external_id": str(p.get("id", "")), "title": p.get("title", ""),
                "brand": p.get("brand") or "", "package_size": size, "price": float(d["price"]),
                "depot_name": d.get("depotName", ""), "source_time": d.get("indexTime", ""),
            })
    return offers


# ---- veritabanı akışı ----------------------------------------------------------

def _depots(db: Session, key: str, lat: float, lon: float, radius_km: int) -> list[str]:
    s = get_settings()
    area = db.get(LiveArea, key)
    if area and datetime.now() - area.fetched_at < timedelta(hours=s.live_prices_ttl_hours):
        return json.loads(area.depots_json)
    rows = _post("/api/v2/nearest", {"latitude": lat, "longitude": lon, "distance": radius_km})
    depots = [r["id"] for r in rows if isinstance(r, dict) and r.get("id")]
    area = area or LiveArea(area_key=key)
    area.depots_json, area.fetched_at = json.dumps(depots), datetime.now()
    db.merge(area)
    db.commit()
    return depots


def _store_for(db: Session, chain_slug: str, cache: dict[str, Store]) -> Store | None:
    if chain_slug in cache:
        return cache[chain_slug]
    chain = db.scalar(select(Chain).where(Chain.slug == chain_slug))
    if chain is None:
        return None
    store = db.scalar(select(Store).where(Store.chain_id == chain.id, Store.is_demo.is_(False)))
    if store is None:
        store = Store(name=chain.name, color=chain.color, chain_id=chain.id, is_demo=False)
        db.add(store)
        db.flush()
    cache[chain_slug] = store
    return store


def refresh(db: Session, ingredient_ids: list[int], lat: float, lon: float, radius_km: int | None = None,
            force: bool = False) -> dict:
    """Verilen malzemeler için (önbellek süresi dolmuşsa) canlı fiyatları çeker. Özet döner."""
    s = get_settings()
    radius_km = max(1, int(radius_km or s.live_prices_radius_km))
    key = area_key(lat, lon, radius_km)
    ttl = timedelta(hours=s.live_prices_ttl_hours)
    now = datetime.now()

    todo: list[Ingredient] = []
    for ing in db.scalars(select(Ingredient).where(Ingredient.id.in_(ingredient_ids))):
        if ing.name not in RULES:
            continue
        last = db.get(LivePriceFetch, (key, ing.id))
        if force or last is None or now - last.fetched_at > ttl:
            todo.append(ing)
    if not todo:
        return {"area_key": key, "queried": 0, "matched": 0}

    # Gizlilik: kaynağa yalnız ~1 km'lik ızgara merkezi gönderilir (önbellek anahtarıyla aynı hassasiyet)
    lat, lon = round(lat, 2), round(lon, 2)
    depots = _depots(db, key, lat, lon, radius_km)
    if not depots:
        raise LivePricesUnavailable("Bu konumun yakınında Market Fiyatı'nda kayıtlı şube bulunamadı")

    stores: dict[str, Store] = {}
    matched_total = 0
    for ing in todo:
        rule = RULES[ing.name]
        data = _post("/api/v2/search", {
            "keywords": rule["q"], "depots": depots, "pages": 0, "size": rule.get("size", 60),
            "latitude": lat, "longitude": lon, "distance": radius_km,
        })
        offers = extract_offers(data.get("content", []) if isinstance(data, dict) else [], ing, rule)
        db.execute(delete(MarketProduct).where(MarketProduct.area_key == key, MarketProduct.ingredient_id == ing.id))
        for o in offers:
            store = _store_for(db, o.pop("chain"), stores)
            if store is not None:
                db.add(MarketProduct(area_key=key, store_id=store.id, ingredient_id=ing.id, fetched_at=now, **o))
        db.merge(LivePriceFetch(area_key=key, ingredient_id=ing.id, fetched_at=now, matched=len(offers)))
        db.commit()
        matched_total += len(offers)
    return {"area_key": key, "queried": len(todo), "matched": matched_total}


def offers(db: Session, key: str, ingredient_ids: list[int]) -> list[MarketProduct]:
    if not ingredient_ids:
        return []
    return list(db.scalars(select(MarketProduct).where(
        MarketProduct.area_key == key, MarketProduct.ingredient_id.in_(ingredient_ids))))


def estimated_seconds(n: int) -> int:
    return math.ceil(n * max(get_settings().live_prices_min_interval_s, 0.5)) + 2
