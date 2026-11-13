from datetime import date

from sqlalchemy import select

from app.domain.diet import DietRules, allowed, recipe_violations
from app.domain.planner import meal_targets
from app.models import Ingredient, Recipe


def _r(db, name):
    return db.scalar(select(Recipe).where(Recipe.name == name))


def _i(db, name):
    return db.scalar(select(Ingredient).where(Ingredient.name == name))


def test_diet_rules(db):
    recipes = list(db.scalars(select(Recipe)))
    veg = {r.name for r in allowed(recipes, DietRules(diet="vegetarian"))}
    assert "Menemen" in veg and "Tavuk Sote" not in veg and "Fırında Somon ve Brokoli" not in veg
    pesc = {r.name for r in allowed(recipes, DietRules(diet="pescatarian"))}
    assert "Fırında Somon ve Brokoli" in pesc and "Kıymalı Makarna" not in pesc
    vegan = {r.name for r in allowed(recipes, DietRules(diet="vegan"))}
    assert "Menemen" not in vegan and "Çoban Salata" in vegan
    no_dairy = {r.name for r in allowed(recipes, DietRules(exclusions={"dairy"}))}
    assert "Menemen" not in no_dairy and "Çoban Salata" in no_dairy  # tereyağı zorunlu malzeme
    # isteğe bağlı malzeme engel sayılmaz: Çoban Salata'daki maydanoz sevilmese de tarif kalır
    assert recipe_violations(_r(db, "Çoban Salata"), DietRules(disliked={_i(db, "Maydanoz").id})) == []
    assert "Menemen" not in {r.name for r in allowed(recipes, DietRules(exclusions={"egg"}))}


def test_dislikes_equipment_lowcarb(db):
    karniyarik = _r(db, "Karnıyarık")
    assert recipe_violations(karniyarik, DietRules(disliked={_i(db, "Patlıcan").id}))
    assert any("alet" in v for v in recipe_violations(_r(db, "Fırında Somon ve Brokoli"), DietRules(equipment={"stovetop"})))
    pilav = _r(db, "Bulgur Pilavı")
    assert recipe_violations(pilav, DietRules(low_carb=True), "lunch")
    assert not recipe_violations(pilav, DietRules(low_carb=True), "breakfast")


def test_meal_targets_reserve_own_meals():
    t = meal_targets(2000, {"breakfast": {"mode": "skip"}, "lunch": {"mode": "own", "kcal": 800},
                            "dinner": {"mode": "plan"}, "snack": {"mode": "skip"}})
    assert t == {"dinner": 1200}
    t = meal_targets(2000, {"breakfast": {"mode": "plan"}, "lunch": {"mode": "plan"}, "dinner": {"mode": "plan"},
                            "snack": {"mode": "skip"}})
    assert sum(t.values()) == 2000 and t["dinner"] > t["lunch"] > t["breakfast"]


PREFS = {
    "goals": ["decide_less"], "diet": "none", "low_carb": False, "exclusions": [], "disliked_ingredient_ids": [],
    "equipment": ["stovetop", "oven"],
    "meals": {"breakfast": {"mode": "skip"}, "lunch": {"mode": "own", "kcal": 800, "protein": 60},
              "dinner": {"mode": "plan"}, "snack": {"mode": "skip"}},
    "plan_days": [0, 1, 2, 3, 4, 5, 6], "weekly_budget": 1800, "repeat_policy": "variety", "onboarding_done": True,
}
MONDAY = "2026-11-16"


def test_preferences_roundtrip_and_validation(client):
    assert client.get("/api/preferences").json()["onboarding_done"] is False
    r = client.put("/api/preferences", json=PREFS)
    assert r.status_code == 200 and r.json()["meals"]["lunch"]["kcal"] == 800
    bad = {**PREFS, "meals": {k: {"mode": "skip"} for k in ("breakfast", "lunch", "dinner", "snack")}}
    assert client.put("/api/preferences", json=bad).status_code == 400


def test_generate_week_respects_meals_days_and_variety(client):
    client.put("/api/preferences", json={**PREFS, "plan_days": [0, 2, 4]})  # Pzt, Çar, Cum
    out = client.post("/api/plan/generate", json={"start": MONDAY, "days": 7, "seed": 1}).json()
    assert [m["meal_type"] for m in out["meals"]] == ["dinner"] * 3
    assert [m["day"] for m in out["meals"]] == ["2026-11-16", "2026-11-18", "2026-11-20"]
    ids = [m["recipe_id"] for m in out["meals"]]
    assert len(set(ids)) == 3
    # aynı tohum = aynı plan; yeniden oluşturma eski otomatik kayıtların yerine geçer
    again = client.post("/api/plan/generate", json={"start": MONDAY, "days": 7, "seed": 1}).json()
    assert [m["recipe_id"] for m in again["meals"]] == ids
    plan = client.get("/api/plan", params={"start": MONDAY, "days": 7}).json()
    assert len(plan) == 3 and all(e["auto_generated"] for e in plan)


def test_vegetarian_plan_has_no_meat(client):
    client.put("/api/preferences", json={**PREFS, "diet": "vegetarian"})
    out = client.post("/api/plan/generate", json={"start": MONDAY, "days": 7, "seed": 3}).json()
    recipes = {r["id"]: r for r in client.get("/api/recipes").json()}
    meat = {"Et & Balık"}
    for m in out["meals"]:
        cats = {line["ingredient"]["category"] for line in recipes[m["recipe_id"]]["ingredients"] if not line["optional"]}
        assert not (cats & meat), m["recipe_name"]


def test_batch_lunch_and_shopping_counts_once(client):
    prefs = {**PREFS, "meals": {"breakfast": {"mode": "skip"}, "lunch": {"mode": "plan"},
                                "dinner": {"mode": "skip"}, "snack": {"mode": "skip"}},
             "plan_days": [0, 1, 2], "repeat_policy": "batch"}
    client.put("/api/preferences", json=prefs)
    out = client.post("/api/plan/generate", json={"start": MONDAY, "days": 7, "seed": 5}).json()
    meals = out["meals"]
    assert len({m["recipe_id"] for m in meals}) == 1
    assert [m["is_leftover"] for m in meals] == [False, True, True]
    members = len(client.get("/api/household/targets").json()["members"])
    # ilk kayıt üç günün porsiyonunu taşır (porsiyon çarpanı 1-2 arası); kalanlar günlük pay
    assert meals[0]["servings"] % 3 == 0 and members * 3 <= meals[0]["servings"] <= members * 6
    assert all(m["servings"] == meals[0]["servings"] // 3 for m in meals[1:])


def test_balanced_cooks_once_eats_twice(client):
    prefs = {**PREFS, "meals": {"breakfast": {"mode": "skip"}, "lunch": {"mode": "plan"},
                                "dinner": {"mode": "skip"}, "snack": {"mode": "skip"}},
             "plan_days": [0, 1, 2, 3], "repeat_policy": "balanced"}
    client.put("/api/preferences", json=prefs)
    meals = client.post("/api/plan/generate", json={"start": MONDAY, "days": 7, "seed": 2}).json()["meals"]
    assert [m["is_leftover"] for m in meals] == [False, True, False, True]
    assert meals[0]["recipe_id"] == meals[1]["recipe_id"] != meals[2]["recipe_id"]


def test_meal_status_skip_and_ate_out(client):
    recipes = {r["name"]: r["id"] for r in client.get("/api/recipes").json()}
    entry = client.post("/api/plan", json={"day": MONDAY, "recipe_id": recipes["Karnıyarık"], "servings": 2}).json()
    rng = {"plan_from": MONDAY, "plan_to": MONDAY}
    assert client.post("/api/recipes/missing", json=rng).json()["lines"]
    r = client.post(f"/api/plan/{entry['id']}/status", json={"status": "skipped"})
    assert r.status_code == 200 and r.json()["status"] == "skipped"
    # atlanan öğün alışveriş ihtiyacı doğurmaz
    assert client.post("/api/recipes/missing", json=rng).status_code == 400
    assert client.post(f"/api/plan/{entry['id']}/status", json={"status": "eaten"}).status_code == 422
    client.post(f"/api/plan/{entry['id']}/status", json={"status": "planned"})
    cook = client.post(f"/api/plan/{entry['id']}/cook").json()
    assert cook["consumed"]
    assert client.post(f"/api/plan/{entry['id']}/status", json={"status": "skipped"}).status_code == 400


def test_portion_factor_and_calorie_fit(client):
    from app.domain.planner import portion_factor

    assert portion_factor(200, 1200) == 2.0 and portion_factor(1500, 600) == 1.0 and portion_factor(500, 760) == 1.5
    client.put("/api/preferences", json=PREFS)  # akşam hedefi ~ (günlük - 800) kcal
    out = client.post("/api/plan/generate", json={"start": MONDAY, "days": 7, "seed": 4}).json()
    kcal = [m["kcal_per_serving"] for m in out["meals"]]
    assert sum(kcal) / len(kcal) > 600  # hafif çorbalar tek başına akşam yemeği olarak seçilmez
