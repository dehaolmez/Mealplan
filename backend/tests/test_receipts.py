from app.services import gemini, receipts


MODEL_OUTPUT = {
    "store_name": "BİM BİRLEŞİK MAĞAZALAR A.Ş.",
    "date": "2026-11-13",
    "lines": [
        {"raw_text": "DOMATES KG 1,245 X 69,00", "catalog_name": "Domates", "quantity": 1.245, "unit": "kg", "line_total": 85.91},
        {"raw_text": "BILI BILI YUMURTA 30LU", "catalog_name": "Yumurta", "quantity": 30, "unit": "adet", "line_total": 149.0},
        {"raw_text": "DONDURULMUS BEZELYE", "catalog_name": "Dondurulmuş bezelye", "quantity": 450, "unit": "g", "line_total": 49.5},
        {"raw_text": "PECETE", "catalog_name": "Uydurma Ürün", "quantity": 1, "unit": "adet", "line_total": 24.9},
        {"raw_text": "YUMURTA (hatalı birim)", "catalog_name": "Yumurta", "quantity": 1, "unit": "l", "line_total": None},
    ],
}


def test_build_draft_maps_catalog_chain_and_units(db):
    draft = receipts.build_draft(db, MODEL_OUTPUT)
    assert draft["chain"]["name"] == "BİM" and draft["date"] == "2026-11-13"
    lines = {l["raw_text"]: l for l in draft["lines"]}
    assert lines["DOMATES KG 1,245 X 69,00"]["quantity"] == 1245 and lines["DOMATES KG 1,245 X 69,00"]["selected"]
    assert lines["BILI BILI YUMURTA 30LU"]["quantity"] == 30
    assert lines["DONDURULMUS BEZELYE"]["location"] == "freezer"
    assert lines["PECETE"]["ingredient_id"] is None and not lines["PECETE"]["selected"]  # katalog dışı ad kabul edilmez
    assert not lines["YUMURTA (hatalı birim)"]["selected"]  # çevrilemeyen birim


def _enable_gemini(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("MEALBIRD_GEMINI_API_KEY", "test-key")
    get_settings.cache_clear()


def test_scan_requires_ai_consent_then_confirms_into_inventory(client, monkeypatch):
    _enable_gemini(monkeypatch)
    monkeypatch.setattr(gemini, "generate_json", lambda *a, **k: MODEL_OUTPUT)
    body = {"image_base64": "aGVsbG8=", "mime_type": "image/jpeg"}
    r = client.post("/api/receipts/scan", json=body)
    assert r.status_code == 400 and "izn" in r.json()["detail"]

    client.post("/api/auth/me/consents", json={"kind": "ai_transfer", "granted": True})
    draft = client.post("/api/receipts/scan", json=body).json()
    chosen = [l for l in draft["lines"] if l["selected"]]
    before = len(client.get("/api/inventory").json())
    out = client.post("/api/receipts/confirm", json={"date": draft["date"], "lines": [
        {"ingredient_id": l["ingredient_id"], "quantity": l["quantity"], "unit": l["unit"], "location": l["location"]}
        for l in chosen]}).json()
    assert out["added"] == 3
    assert len(client.get("/api/inventory").json()) == before + 3


def test_scan_rejects_bad_input(client, monkeypatch):
    _enable_gemini(monkeypatch)
    client.post("/api/auth/me/consents", json={"kind": "ai_transfer", "granted": True})
    assert client.post("/api/receipts/scan", json={"image_base64": "!!!", "mime_type": "image/jpeg"}).status_code == 400
    assert client.post("/api/receipts/scan", json={"image_base64": "aGVsbG8=", "mime_type": "application/pdf"}).status_code == 400


def test_gemini_falls_back_between_models(monkeypatch):
    import httpx

    from app.core.config import get_settings

    _enable_gemini(monkeypatch)
    seen = []

    def fake_post(url, json, headers, timeout):
        seen.append(json["model"])
        req = httpx.Request("POST", url)
        if len(seen) == 1:
            return httpx.Response(503, request=req, json=[{"error": {"code": 503}}])
        assert headers["Authorization"] == "Bearer test-key"
        return httpx.Response(200, request=req, json={"choices": [{"finish_reason": "stop", "message": {"content": '{"ok": true}'}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    assert gemini.generate_json("s", "u", {"type": "object"}) == {"ok": True}
    assert seen == get_settings().gemini_models[:2]
