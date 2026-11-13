from app.domain.price_optimizer import Need, Offer, Strategy, optimize, packages_needed

STORES = {1: "A", 2: "B"}
OFFERS = {
    10: [Offer(1, "A", 1000, 30.0), Offer(2, "B", 1000, 25.0)],  # domates
    20: [Offer(1, "A", 10, 80.0), Offer(2, "B", 10, 90.0)],      # yumurta
    30: [Offer(1, "A", 400, 300.0)],                              # somon: sadece A
}
NEEDS = [Need(10, "Domates", 1500), Need(20, "Yumurta", 6), Need(30, "Somon", 300)]


def test_packages_needed_rounds_up():
    assert packages_needed(1500, 1000) == 2
    assert packages_needed(1000, 1000) == 1
    assert packages_needed(1, 1000) == 1


def test_cheapest_splits_across_stores():
    r = optimize(NEEDS, OFFERS, STORES, Strategy.cheapest)
    stores = {p.need.name: p.offer.store_id for p in r.purchases}
    assert stores == {"Domates": 2, "Yumurta": 1, "Somon": 1}
    assert r.total == 50.0 + 80.0 + 300.0


def test_single_store_prefers_store_with_all_items():
    r = optimize(NEEDS, OFFERS, STORES, Strategy.single)
    assert r.chosen_store_id == 1
    assert {p.offer.store_id for p in r.purchases} == {1}
    assert r.total == 60.0 + 80.0 + 300.0


def test_preferred_falls_back_for_unavailable_items():
    r = optimize(NEEDS, OFFERS, STORES, Strategy.preferred, preferred_store_id=2)
    stores = {p.need.name: p.offer.store_id for p in r.purchases}
    assert stores == {"Domates": 2, "Yumurta": 2, "Somon": 1}


def test_store_filter_marks_unavailable():
    r = optimize(NEEDS, OFFERS, {2: "B"}, Strategy.cheapest)
    assert r.unavailable == ["Somon"]
