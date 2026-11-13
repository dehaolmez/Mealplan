from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.price_optimizer import Need, Offer, OptimizationResult, Strategy, optimize
from app.domain.requirements import MissingLine
from app.domain.units import humanize
from app.models import Household, Store, StorePrice
from app.schemas.planning import OptimizeOut, PurchaseOut, StoreTotalOut
from app.services import household_service, shopping_service
from app.services.errors import BadRequest


def list_stores(db: Session) -> list[Store]:
    return list(db.scalars(select(Store).order_by(Store.name)))


def offers_for(db: Session, ingredient_ids: list[int]) -> dict[int, list[Offer]]:
    offers: dict[int, list[Offer]] = defaultdict(list)
    if not ingredient_ids:
        return offers
    rows = db.scalars(select(StorePrice).where(StorePrice.ingredient_id.in_(ingredient_ids)))
    for row in rows:
        offers[row.ingredient_id].append(Offer(row.store_id, row.store.name, row.package_size, row.price, row.brand))
    return offers


def optimize_missing(
    db: Session,
    household: Household,
    missing: list[MissingLine],
    strategy: Strategy,
    store_ids: list[int] | None,
    add_to_list: bool,
    nearby_chains: set[int] | None = None,
) -> OptimizeOut:
    store_rows = list_stores(db)
    all_stores = {s.id: s.name for s in store_rows}
    chosen_ids = store_ids or household_service.store_ids(household) or list(all_stores)
    unknown = set(chosen_ids) - set(all_stores)
    if unknown:
        raise BadRequest(f"Bilinmeyen market: {sorted(unknown)}")
    if nearby_chains is not None:
        chain_of = {s.id: s.chain_id for s in store_rows}
        chosen_ids = [sid for sid in chosen_ids if chain_of[sid] in nearby_chains]
        if not chosen_ids:
            raise BadRequest(
                "Yakınındaki zincirler için fiyat verisi yok. Gerçek fiyatları /api/prices/import ile yükleyin "
                "veya 'yalnız yakındakiler' seçeneğini kapatın."
            )
    stores = {sid: all_stores[sid] for sid in chosen_ids}

    by_id = {m.ingredient.id: m for m in missing}
    needs = [Need(m.ingredient.id, m.ingredient.name, m.missing) for m in missing]
    result = optimize(
        needs,
        offers_for(db, list(by_id)),
        stores,
        strategy=strategy,
        preferred_store_id=household.preferred_store_id,
    )

    added = shopping_service.add_purchases(db, household, result, by_id) if add_to_list else 0
    return _to_out(result, by_id, added)


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
