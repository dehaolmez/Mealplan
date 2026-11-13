def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_household_targets(client):
    data = client.get("/api/household/targets").json()
    assert len(data["members"]) == 2
    assert data["total"]["calories"] == sum(m["targets"]["calories"] for m in data["members"])
    assert data["meal_kcal_target"] > 300


def test_member_crud(client):
    r = client.post("/api/household/members", json={
        "name": "Can", "birth_date": "2000-01-01", "sex": "male", "height_cm": 175, "weight_kg": 70,
        "activity_level": "active", "goal": "gain"})
    assert r.status_code == 201
    member = r.json()
    assert member["targets"]["calories"] > member["targets"]["tdee"]
    assert client.delete(f"/api/household/members/{member['id']}").status_code == 204
    assert client.post("/api/household/members", json={"name": "x", "birth_date": "2000-01-01", "sex": "male",
                                                       "height_cm": 5, "weight_kg": 70}).status_code == 422


def _ingredient_id(client, name):
    return next(i["id"] for i in client.get("/api/ingredients", params={"q": name}).json() if i["name"] == name)


def test_inventory_add_estimates_expiry_and_converts_units(client):
    tid = _ingredient_id(client, "Domates")
    r = client.post("/api/inventory", json={"ingredient_id": tid, "quantity": 1.2, "unit": "kg"})
    item = r.json()
    assert r.status_code == 201
    assert item["quantity"] == 1200 and item["expiry_estimated"] is True
    assert item["days_left"] == 7 and item["status"] == "ok"

    moved = client.patch(f"/api/inventory/{item['id']}", json={"location": "freezer"}).json()
    assert moved["location"] == "freezer" and moved["days_left"] == 60

    assert client.post("/api/inventory", json={"ingredient_id": tid, "quantity": 1, "unit": "fincan"}).status_code == 400
    assert client.post("/api/inventory", json={"ingredient_id": 9999, "quantity": 1}).status_code == 404


def test_inventory_zero_quantity_removes_item(client):
    item = client.get("/api/inventory").json()[0]
    assert client.patch(f"/api/inventory/{item['id']}", json={"quantity": 0}).status_code == 204
    assert all(i["id"] != item["id"] for i in client.get("/api/inventory").json())


def test_alerts_list_expiring_items(client):
    data = client.get("/api/inventory/alerts").json()
    assert data["critical"] >= 1
    names = [a["ingredient_name"] for a in data["alerts"]]
    assert "Tavuk göğsü" in names


def test_recommendations_and_ai_fallback(client):
    data = client.get("/api/recipes/recommendations", params={"limit": 5, "ai": True}).json()
    assert data["ai_requested"] and not data["ai_used"] and data["ai_error"]
    assert len(data["results"]) == 5
    scores = [r["score"] for r in data["results"]]
    assert scores == sorted(scores, reverse=True)


def test_plan_missing_optimize_shopping_checkout_flow(client):
    recipes = {r["name"]: r["id"] for r in client.get("/api/recipes").json()}
    entry = client.post("/api/plan", json={"day": "2026-11-14", "recipe_id": recipes["Karnıyarık"], "servings": 4}).json()

    missing = client.post("/api/recipes/missing", json={"plan_from": "2026-11-13", "plan_to": "2026-11-19"}).json()
    names = {m["ingredient"]["name"] for m in missing["lines"]}
    assert "Patlıcan" in names and "Kıyma" not in names  # kıyma buzlukta var

    opt = client.post("/api/shopping/optimize", json={"plan_from": "2026-11-13", "plan_to": "2026-11-19",
                                                      "strategy": "cheapest", "add_to_list": True}).json()
    assert opt["added_to_list"] == len(missing["lines"])
    assert opt["total"] > 0

    lst = client.get("/api/shopping").json()
    item = next(i for c in lst["categories"] for i in c["items"] if i["name"] == "Patlıcan")
    assert item["category"] == "Manav" and item["store_name"]

    client.patch(f"/api/shopping/items/{item['id']}", json={"checked": True})
    out = client.post("/api/shopping/checkout").json()
    assert out["moved_to_inventory"] == 1

    lst = client.get("/api/shopping").json()
    assert any(i["name"] == "Patlıcan" for i in lst["recently_bought"])
    inv = client.get("/api/inventory").json()
    assert any(i["ingredient"]["name"] == "Patlıcan" for i in inv)

    # artık patlıcan evde: eksik listesinden düşmeli
    missing = client.post("/api/recipes/missing", json={"plan_from": "2026-11-13", "plan_to": "2026-11-19"}).json()
    assert "Patlıcan" not in {m["ingredient"]["name"] for m in missing["lines"]}

    # pişir: envanterden FEFO ile düşer
    cook = client.post(f"/api/plan/{entry['id']}/cook").json()
    assert any(c.startswith("Patlıcan") for c in cook["consumed"])
    assert client.post(f"/api/plan/{entry['id']}/cook").status_code == 400


def test_shopping_merges_duplicates_and_free_text(client):
    a = client.post("/api/shopping/items", json={"name": "domates", "quantity": 500, "unit": "g"}).json()
    b = client.post("/api/shopping/items", json={"name": "Domates", "quantity": 1, "unit": "kg"}).json()
    assert a["id"] == b["id"] and b["quantity"] == 1500 and b["category"] == "Manav"
    free = client.post("/api/shopping/items", json={"name": "Peçete"}).json()
    assert free["category"] == "Diğer" and free["ingredient_id"] is None
    assert client.post("/api/shopping/items", json={}).status_code == 400
