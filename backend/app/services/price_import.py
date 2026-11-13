"""Gerçek fiyat verisini CSV ile içe aktarma.

Fiyat kaynağından bağımsız ortak giriş noktası: elle hazırlanmış tablo, bir market API'sinden dönüştürülmüş
dışa aktarım ya da ileride zamanlanmış bir toplayıcı aynı formatı üretebilir.

Sütunlar (başlık satırı zorunlu, ayraç `,` veya `;`):
    chain, ingredient, package_size, unit, price[, brand][, date]
    chain       : zincir slug'ı veya adı (ör. "bim", "Migros")
    ingredient  : katalogdaki malzeme adı (ör. "Domates")
    package_size: paket miktarı (ondalık ayraç . veya ,)
    unit        : g, kg, ml, l, adet
    price       : paket fiyatı (TL)
    date        : YYYY-AA-GG (boşsa bugün)
"""

import csv
import io
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.chain_matcher import normalize
from app.domain.units import UnitConversionError, to_base_quantity
from app.models import Chain, Ingredient, Store, StorePrice
from app.schemas.places import PriceImportError, PriceImportOut
from app.services import clock
from app.services.errors import BadRequest

REQUIRED = ("chain", "ingredient", "package_size", "unit", "price")
TEMPLATE = (
    "chain,ingredient,package_size,unit,price,brand,date\n"
    "bim,Domates,1,kg,34.90,,\n"
    "migros,Süt,1,l,41.50,Örnek Marka,\n"
)
MAX_ROWS = 20_000


def _num(raw: str) -> float:
    return float(raw.strip().replace(" ", "").replace(",", "."))


def _store_for_chain(db: Session, chain: Chain, created: list[str]) -> Store:
    store = db.scalar(select(Store).where(Store.chain_id == chain.id, Store.is_demo.is_(False)))
    if store is None:
        store = Store(name=chain.name, color=chain.color, chain_id=chain.id, is_demo=False)
        db.add(store)
        db.flush()
        created.append(chain.name)
    return store


def import_csv(db: Session, text: str, source: str = "csv") -> PriceImportOut:
    sample = text[:2048]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")), delimiter=delimiter)
    headers = [h.strip().lower() for h in (reader.fieldnames or [])]
    missing = [c for c in REQUIRED if c not in headers]
    if missing:
        raise BadRequest(f"Eksik sütun(lar): {', '.join(missing)}")
    reader.fieldnames = headers

    chains = {}
    for c in db.scalars(select(Chain)):
        chains[normalize(c.slug)] = c
        chains[normalize(c.name)] = c
    ingredients = {normalize(i.name): i for i in db.scalars(select(Ingredient))}

    created = updated = 0
    stores_created: list[str] = []
    errors: list[PriceImportError] = []
    for line_no, row in enumerate(reader, start=2):
        if line_no - 1 > MAX_ROWS:
            errors.append(PriceImportError(line=line_no, error=f"En fazla {MAX_ROWS} satır işlenir"))
            break
        row = {k: (v or "").strip() for k, v in row.items() if k}
        if not any(row.values()):
            continue
        try:
            chain = chains.get(normalize(row["chain"]))
            if chain is None:
                raise ValueError(f"Bilinmeyen zincir: {row['chain']}")
            ing = ingredients.get(normalize(row["ingredient"]))
            if ing is None:
                raise ValueError(f"Katalogda olmayan malzeme: {row['ingredient']}")
            size = to_base_quantity(ing, _num(row["package_size"]), row["unit"])
            price = _num(row["price"])
            if size <= 0 or price <= 0:
                raise ValueError("Paket boyutu ve fiyat pozitif olmalı")
            updated_on = date.fromisoformat(row["date"]) if row.get("date") else clock.today()
        except (ValueError, UnitConversionError) as exc:
            errors.append(PriceImportError(line=line_no, error=str(exc)))
            continue

        store = _store_for_chain(db, chain, stores_created)
        sp = db.scalar(select(StorePrice).where(StorePrice.store_id == store.id, StorePrice.ingredient_id == ing.id))
        if sp is None:
            db.add(StorePrice(store_id=store.id, ingredient_id=ing.id, package_size=size, price=price,
                              brand=row.get("brand", ""), source=source, updated_on=updated_on))
            created += 1
        elif updated_on >= sp.updated_on:  # daha eski bir veri yeni fiyatın üstüne yazılmaz
            sp.package_size, sp.price, sp.brand = size, price, row.get("brand", "")
            sp.source, sp.updated_on = source, updated_on
            updated += 1
        db.flush()
    db.commit()
    return PriceImportOut(created=created, updated=updated, stores_created=stores_created, errors=errors)


def price_stats(db: Session) -> list[dict]:
    rows = db.execute(
        select(Store.id, Store.name, Store.is_demo, Store.chain_id, func.count(StorePrice.id), func.max(StorePrice.updated_on))
        .join(StorePrice, StorePrice.store_id == Store.id, isouter=True)
        .group_by(Store.id)
        .order_by(Store.name)
    )
    return [
        {"store_id": r[0], "store": r[1], "is_demo": r[2], "chain_id": r[3], "prices": r[4],
         "last_update": r[5].isoformat() if r[5] else None}
        for r in rows
    ]
