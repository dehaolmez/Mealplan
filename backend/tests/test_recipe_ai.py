from app.services import gemini
from tests.conftest import REGISTER

GOOD = {"recipes": [{
    "name": "Ispanaklı Peynirli Omlet", "description": "Bozulmadan önce ıspanağı değerlendiren pratik omlet.",
    "meal_type": "breakfast", "servings": 2, "prep_minutes": 15, "equipment": ["stovetop"], "tags": ["vejetaryen", "pratik"],
    "ingredients": [
        {"ingredient": "Yumurta", "quantity": 4, "unit": "adet", "optional": False},
        {"ingredient": "Ispanak", "quantity": 200, "unit": "g", "optional": False},
        {"ingredient": "Beyaz peynir", "quantity": 60, "unit": "g", "optional": False},
        {"ingredient": "Sarımsak", "quantity": 1, "unit": "adet", "optional": True},
        {"ingredient": "Tuz", "quantity": 2, "unit": "g", "optional": False},
    ],
    "steps": ["Ispanağı doğrayın.", "Tavada söndürün.", "Yumurtaları çırpıp ekleyin.", "Peyniri serpip pişirin."],
}]}


def _enable(monkeypatch, client, output):
    from app.core.config import get_settings

    monkeypatch.setenv("MEALBIRD_GEMINI_API_KEY", "test-key")
    get_settings.cache_clear()
    monkeypatch.setattr(gemini, "generate_json", lambda *a, **k: output)
    client.post("/api/auth/me/consents", json={"kind": "ai_transfer", "granted": True})


def test_generate_recipe_saved_privately(client, monkeypatch):
    _enable(monkeypatch, client, GOOD)
    r = client.post("/api/recipes/generate", json={"meal_type": "breakfast", "wish": "ıspanak bitsin"})
    assert r.status_code == 201, r.text
    recipe = r.json()
    assert recipe["own"] and recipe["source"] == "gemini" and recipe["per_serving"]["kcal"] > 100
    garlic = next(i for i in recipe["ingredients"] if i["ingredient"]["name"] == "Sarımsak")
    assert garlic["quantity"] == 5 and garlic["optional"]  # 1 diş = 5 g
    assert any(x["id"] == recipe["id"] for x in client.get("/api/recipes").json())

    # başka hane göremez, plana ekleyemez
    client.post("/api/auth/logout")
    client.post("/api/auth/register", json={**REGISTER, "email": "baska@example.com"})
    assert all(x["id"] != recipe["id"] for x in client.get("/api/recipes").json())
    assert client.get(f"/api/recipes/{recipe['id']}").status_code == 404
    assert client.post("/api/plan", json={"day": "2026-11-16", "recipe_id": recipe["id"]}).status_code == 404
    client.post("/api/auth/logout")
    assert all(x["id"] != recipe["id"] for x in client.get("/api/recipes").json())  # anonim de göremez


def test_generated_recipe_must_follow_diet(client, monkeypatch):
    _enable(monkeypatch, client, GOOD)
    prefs = client.get("/api/preferences").json()
    client.put("/api/preferences", json={**prefs, "diet": "vegan"})
    r = client.post("/api/recipes/generate", json={"meal_type": "breakfast"})
    assert r.status_code == 400 and "kurala aykırı" in r.json()["detail"]


def test_generate_requires_consent(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("MEALBIRD_GEMINI_API_KEY", "test-key")
    get_settings.cache_clear()
    r = client.post("/api/recipes/generate", json={})
    assert r.status_code == 400 and "izn" in r.json()["detail"]
