"""Envanter anlık görüntüsü: malzeme bazında, SKT'ye göre sıralı (FEFO) stok partileri."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from app.domain.shelf_life import days_left
from app.models.inventory import InventoryItem


@dataclass
class StockLot:
    item_id: int
    ingredient_id: int
    quantity: float
    days_left: int


Stock = dict[int, list[StockLot]]


def build_stock(items: Iterable[InventoryItem], today: date) -> Stock:
    """SKT'si geçmiş ürünleri dışarıda bırakır; partileri ilk bozulacak olan önde olacak şekilde sıralar."""
    stock: Stock = defaultdict(list)
    for item in items:
        left = days_left(item.expiry_date, today)
        if left < 0 or item.quantity <= 0:
            continue
        stock[item.ingredient_id].append(StockLot(item.id, item.ingredient_id, item.quantity, left))
    for lots in stock.values():
        lots.sort(key=lambda lot: lot.days_left)
    return dict(stock)


def available(stock: Stock, ingredient_id: int) -> float:
    return sum(lot.quantity for lot in stock.get(ingredient_id, []))


def allocate_fefo(lots: list[StockLot], needed: float) -> list[tuple[StockLot, float]]:
    """İhtiyacı ilk bozulacak partiden başlayarak karşılar. (parti, kullanılan miktar) listesi döner."""
    taken: list[tuple[StockLot, float]] = []
    remaining = needed
    for lot in lots:
        if remaining <= 1e-9:
            break
        use = min(lot.quantity, remaining)
        if use > 0:
            taken.append((lot, use))
            remaining -= use
    return taken
