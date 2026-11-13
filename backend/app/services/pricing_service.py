from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.price_optimizer import Need, Offer, OptimizationResult, Strategy, optimize
from app.domain.requirements import MissingLine
from app.domain.units import humanize
from app.models import Household, MarketProduct, Store, StorePrice
from app.schemas.planning import OptimizeOut, PurchaseOut, StoreTotalOut
from app.services import household_service, shopping_service
from app.services.errors import BadRequest


def list_stores(db: Session) -> list[Store]:
    return list(db.scalars(select(Store).order_by(Store.name)))


def offers_for(db: Session, ingredient_ids: list[int], live_area: str | None = None) -> dict[int, list[Offer]]:
    """CSV/test/demo fiyatları + (bölge verildiyse) canlı kaynaktan gelen ürünler. Aynı market için birden çok
    paket olabilir; optimizasyon ihtiyaca göre toplamı en düşük olanı seçer."""
    offers: dict[int, list[Offer]] = defaultdict(list)
    if not ingredient_ids:
        return offers
    rows = db.scalars(select(StorePrice).where(StorePrice.ingredient_id.in_(ingredient_ids)))
    for row in rows:
        offers[row.ingredient_id].append(Offer(row.store_id, row.store.name, row.package_size, row.price, row.brand))
    if live_area:
        live = db.scalars(select(MarketProduct).where(
            MarketProduct.area_key == live_area, MarketProduct.ingredient_id.in_(ingredient_ids)))
        for p in live:
            offers[p.ingredient_id].append(Offer(p.store_id, p.store.name, p.package_size, p.price, p.title))
    return offers


def optimize_missing(
    db: Session,
    household: Household,
    missing: list[MissingLine],
    strategy: Strategy,
    store_ids: list[int] | None,
    add_to_list: bool,
    nearby_chains: set[int] | None = None,
    live_area: str | None = None,
    price_note: str | None = None,
) -> OptimizeOut:
    by_id = {m.ingredient.id: m for m in missing}
    all_offers = offers_for(db, list(by_id), live_area)
    store_rows = list_stores(db)
    all_stores = {s.id: s.name for s in store_rows}
    if store_ids:
        unknown = set(store_ids) - set(all_stores)
        if unknown:
            raise BadRequest(f"Bilinmeyen market: {sorted(unknown)}")

    # Gerçek (demo/test olmayan) fiyat varsa yalnız onlar kullanılır; örnek fiyatlar gerçeklerle karışmaz.
    offered = {o.store_id for lst in all_offers.values() for o in lst}
    real_ids = [s.id for s in store_rows if not s.is_demo and s.id in offered]
    price_mode = "real" if real_ids else "demo"
    if real_ids:
        from app.services.preferences_service import preferred_chain_ids

        selection = store_ids or [i for i in household_service.store_ids(household) if i in real_ids]
        chosen_ids = [i for i in (selection or real_ids) if i in real_ids] or real_ids
        favorite = preferred_chain_ids(db, household)
        if favorite and not store_ids:  # yalnız alışveriş yapılan zincirler (en az biri teklif veriyorsa)
            chain_of = {s.id: s.chain_id for s in store_rows}
            chosen_ids = [i for i in chosen_ids if chain_of[i] in favorite] or chosen_ids
    elif nearby_chains is not None and not store_ids:
        # Konum modunda hanenin market seçimi yerine yakındaki tüm zincirler aday olur
        chosen_ids = list(all_stores)
    else:
        chosen_ids = store_ids or household_service.store_ids(household) or list(all_stores)
    if nearby_chains is not None:
        chain_of = {s.id: s.chain_id for s in store_rows}
        chosen_ids = [sid for sid in chosen_ids if chain_of[sid] in nearby_chains]
        if not chosen_ids:
            raise BadRequest(
                "Yakınındaki zincirler için fiyat verisi yok. Gerçek fiyatları /api/prices/import ile yükleyin "
                "veya 'yalnız yakındakiler' seçeneğini kapatın."
            )
    stores = {sid: all_stores[sid] for sid in chosen_ids}

    needs = [Need(m.ingredient.id, m.ingredient.name, m.missing) for m in missing]
    result = optimize(
        needs,
        all_offers,
        stores,
        strategy=strategy,
        preferred_store_id=household.preferred_store_id,
    )

    added = shopping_service.add_purchases(db, household, result, by_id) if add_to_list else 0
    if price_mode == "demo" and not price_note:
        price_note = "Gerçek fiyat verisi bulunamadı; örnek (demo) fiyatlar gösteriliyor."
    out = _to_out(result, by_id, added)
    out.price_mode, out.price_note = ("live" if live_area and real_ids else price_mode), price_note
    return out


def _to_out(result: OptimizationResult, by_id: dict[int, MissingLine], added: int) -> OptimizeOut:
    purchases = []
    for p in result.purchases:
        ing = by_id[p.need.ingredient_id].ingredient
        purchases.append(
            PurchaseOut(
                ingredient_id=ing.id,
                name=ing.name,
                emoji=ing.emoji,
                category=ing.category,
                missing_label=humanize(p.need.quantity, ing.base_unit),
                store_id=p.offer.store_id if p.offer else None,
                store_name=p.offer.store_name if p.offer else None,
                brand=p.offer.brand if p.offer else None,
                package_label=humanize(p.offer.package_size, ing.base_unit) if p.offer else None,
                packages=p.packages,
                cost=p.cost,
            )
        )
    complete = [t for t in result.store_totals if not t.missing_items]
    savings = round(max(t.total for t in complete) - result.total, 2) if complete and not result.unavailable else None
    return OptimizeOut(
        strategy=result.strategy,
        chosen_store_id=result.chosen_store_id,
        total=result.total,
        unavailable=result.unavailable,
        purchases=purchases,
        store_totals=[StoreTotalOut(**t.__dict__) for t in result.store_totals],
        savings_vs_worst_single_store=savings,
        added_to_list=added,
    )
