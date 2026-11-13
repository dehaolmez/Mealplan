"""Eksik malzemelerin market fiyatlarıyla eşleştirilip alışveriş maliyetinin optimize edilmesi.

Stratejiler:
  * cheapest   – her ürünü, seçili marketler arasında en ucuza veren marketten al (çok duraklı)
  * single     – toplam tutarı en düşük olan TEK markette tamamla (bulunmayanlar ayrıca işaretlenir)
  * preferred  – tercih edilen markette al; orada olmayanları en ucuz alternatiften tamamla
"""

import math
from dataclasses import dataclass, field
from enum import StrEnum


class Strategy(StrEnum):
    cheapest = "cheapest"
    single = "single"
    preferred = "preferred"


@dataclass(frozen=True)
class Offer:
    store_id: int
    store_name: str
    package_size: float
    price: float
    brand: str = ""


@dataclass(frozen=True)
class Need:
    ingredient_id: int
    name: str
    quantity: float  # temel birimde eksik miktar


@dataclass
class Purchase:
    need: Need
    offer: Offer | None
    packages: int
    cost: float


@dataclass
class StoreTotal:
    store_id: int
    store_name: str
    total: float
    available_items: int
    missing_items: list[str]


@dataclass
class OptimizationResult:
    strategy: Strategy
    purchases: list[Purchase]
    total: float
    unavailable: list[str]
    store_totals: list[StoreTotal] = field(default_factory=list)
    chosen_store_id: int | None = None


def packages_needed(quantity: float, package_size: float) -> int:
    return max(1, math.ceil(quantity / package_size - 1e-9))


def offer_cost(need: Need, offer: Offer) -> tuple[int, float]:
    n = packages_needed(need.quantity, offer.package_size)
    return n, round(n * offer.price, 2)


def _best_offer(need: Need, offers: list[Offer]) -> Purchase:
    best: Purchase | None = None
    for offer in offers:
        n, cost = offer_cost(need, offer)
        if best is None or cost < best.cost:
            best = Purchase(need, offer, n, cost)
    return best or Purchase(need, None, 0, 0.0)


def store_totals(needs: list[Need], offers: dict[int, list[Offer]], stores: dict[int, str]) -> list[StoreTotal]:
    totals: list[StoreTotal] = []
    for store_id, store_name in stores.items():
        total = 0.0
        found = 0
        missing: list[str] = []
        for need in needs:
            store_offers = [o for o in offers.get(need.ingredient_id, []) if o.store_id == store_id]
            if not store_offers:
                missing.append(need.name)
                continue
            total += _best_offer(need, store_offers).cost
            found += 1
        totals.append(StoreTotal(store_id, store_name, round(total, 2), found, missing))
    # Önce en çok ürünü bulunduran, sonra en ucuz market
    totals.sort(key=lambda t: (-t.available_items, t.total))
    return totals


def optimize(
    needs: list[Need],
    offers: dict[int, list[Offer]],
    stores: dict[int, str],
    strategy: Strategy = Strategy.cheapest,
    preferred_store_id: int | None = None,
) -> OptimizationResult:
    """`offers`: ingredient_id -> tüm marketlerdeki teklifler. `stores`: dikkate alınacak marketler."""
    scoped = {iid: [o for o in lst if o.store_id in stores] for iid, lst in offers.items()}
    totals = store_totals(needs, scoped, stores)

    chosen: int | None = None
    if strategy == Strategy.single and totals:
        chosen = totals[0].store_id
    elif strategy == Strategy.preferred and preferred_store_id in stores:
        chosen = preferred_store_id

    purchases: list[Purchase] = []
    for need in needs:
        candidates = scoped.get(need.ingredient_id, [])
        if chosen is not None:
            at_chosen = [o for o in candidates if o.store_id == chosen]
            if at_chosen:
                purchases.append(_best_offer(need, at_chosen))
                continue
            if strategy == Strategy.single:
                purchases.append(Purchase(need, None, 0, 0.0))
                continue
        purchases.append(_best_offer(need, candidates))

    unavailable = [p.need.name for p in purchases if p.offer is None]
    total = round(sum(p.cost for p in purchases), 2)
    return OptimizationResult(strategy, purchases, total, unavailable, totals, chosen)
