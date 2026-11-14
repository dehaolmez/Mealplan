import pytest

from app.core import security
from tests.conftest import REGISTER


def _reg(c, **over):
    return c.post("/api/auth/register", json={**REGISTER, **over})


def test_password_hash_roundtrip():
    h = security.hash_password("parola-123", n=2**12)
    assert h.startswith("scrypt$") and security.verify_password("parola-123", h)
    assert not security.verify_password("yanlis", h) and not security.verify_password("x", None)


def test_protected_endpoints_require_login(anon_client):
    assert anon_client.get("/api/inventory").status_code == 401
    assert anon_client.get("/api/auth/me").status_code == 401
    # herkese açık olanlar
    assert anon_client.get("/api/recipes").status_code == 200
    assert anon_client.get("/api/legal/aydinlatma").status_code == 200
    assert anon_client.get("/api/auth/config").json()["google_client_id"] is None


def test_register_requires_legal_acknowledgement(anon_client):
    r = _reg(anon_client, accept_terms=False)
    assert r.status_code == 400
    assert _reg(anon_client, password="kisa").status_code == 422


def test_register_login_logout_flow(anon_client):
    r = _reg(anon_client)
    assert r.status_code == 201
    me = r.json()
    assert me["email"] == "ayse@example.com" and me["role"] == "owner" and me["invite_code"]
    consents = {c["kind"]: c["granted"] for c in me["consents"]}
    assert consents["health_data"] and consents["location"] and not consents["ai_transfer"]
    assert len(anon_client.get("/api/inventory").json()) > 0  # örnek veri

    assert _reg(anon_client).status_code == 400  # aynı e-posta
    anon_client.post("/api/auth/logout")
    assert anon_client.get("/api/auth/me").status_code == 401
    assert anon_client.post("/api/auth/login", json={"email": "AYSE@example.com", "password": "yanlis-sifre"}).status_code == 401
    assert anon_client.post("/api/auth/login", json={"email": "AYSE@example.com", "password": REGISTER["password"]}).status_code == 200
    assert anon_client.get("/api/auth/me").status_code == 200


def test_bearer_token_also_works(anon_client):
    _reg(anon_client)
    token = anon_client.cookies.get("mb_session")
    anon_client.cookies.clear()
    assert anon_client.get("/api/auth/me").status_code == 401
    assert anon_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_login_rate_limited(anon_client):
    _reg(anon_client)
    codes = [anon_client.post("/api/auth/login", json={"email": "ayse@example.com", "password": "yanlis-123"}).status_code
             for _ in range(10)]
    assert codes[-1] == 400 and 401 in codes


def test_households_are_isolated(anon_client):
    _reg(anon_client)
    mine = {i["id"] for i in anon_client.get("/api/inventory").json()}
    anon_client.post("/api/auth/logout")
    _reg(anon_client, email="mehmet@example.com", with_sample_data=False)
    assert anon_client.get("/api/inventory").json() == []
    some_id = next(iter(mine))
    assert anon_client.delete(f"/api/inventory/{some_id}").status_code == 404


def test_invite_code_joins_household(anon_client):
    code = _reg(anon_client).json()["invite_code"]
    anon_client.post("/api/auth/logout")
    me = _reg(anon_client, email="es@example.com", invite_code=code, with_sample_data=False).json()
    assert me["role"] == "member" and me["invite_code"] is None
    assert len(anon_client.get("/api/inventory").json()) > 0  # ortak envanter görünür


def test_health_consent_gates_member_data(anon_client):
    _reg(anon_client, health_data_consent=False)
    member = {"name": "Can", "birth_date": "2000-01-01", "sex": "male", "height_cm": 175, "weight_kg": 70}
    assert anon_client.get("/api/household/targets").json()["members"] == []  # rıza yok → örnek birey eklenmedi
    assert anon_client.post("/api/household/members", json=member).status_code == 400

    anon_client.post("/api/auth/me/consents", json={"kind": "health_data", "granted": True})
    assert anon_client.post("/api/household/members", json=member).status_code == 201
    # rıza geri çekilince sağlık verisi silinir
    me = anon_client.post("/api/auth/me/consents", json={"kind": "health_data", "granted": False}).json()
    assert not {c["kind"]: c["granted"] for c in me["consents"]}["health_data"]
    assert anon_client.get("/api/household/targets").json()["members"] == []


def test_location_consent_gates_home_location(anon_client):
    _reg(anon_client, location_consent=False)
    assert anon_client.patch("/api/household", json={"home_lat": 39.95, "home_lon": 32.66}).status_code == 400
    anon_client.post("/api/auth/me/consents", json={"kind": "location", "granted": True})
    assert anon_client.patch("/api/household", json={"home_lat": 39.95, "home_lon": 32.66}).status_code == 200
    anon_client.post("/api/auth/me/consents", json={"kind": "location", "granted": False})
    assert anon_client.get("/api/household").json()["home_lat"] is None
    # aydınlatma/koşul onayı geri çekilemez
    assert anon_client.post("/api/auth/me/consents", json={"kind": "terms", "granted": False}).status_code == 400


def test_password_reset_flow(anon_client, monkeypatch):
    sent = []
    from app.services import mailer

    monkeypatch.setattr(mailer, "send", lambda to, subj, body: sent.append(body))
    _reg(anon_client)
    sent.clear()
    anon_client.post("/api/auth/logout")
    assert anon_client.post("/api/auth/forgot", json={"email": "yok@example.com"}).status_code == 204
    assert sent == []  # hesap yokken e-posta yok (ama yanıt aynı)
    anon_client.post("/api/auth/forgot", json={"email": "ayse@example.com"})
    token = sent[0].split("#reset=")[1].split()[0]
    assert anon_client.post("/api/auth/reset", json={"token": token, "new_password": "yeni-sifre-456"}).status_code == 200
    # bağlantı tek kullanımlık (token_version arttı)
    assert anon_client.post("/api/auth/reset", json={"token": token, "new_password": "baska-sifre-789"}).status_code == 400
    assert anon_client.post("/api/auth/login", json={"email": "ayse@example.com", "password": "yeni-sifre-456"}).status_code == 200


def test_password_change_invalidates_other_sessions(anon_client):
    _reg(anon_client)
    old = anon_client.cookies.get("mb_session")
    r = anon_client.post("/api/auth/me/password", json={"current_password": REGISTER["password"], "new_password": "yepyeni-sifre-1"})
    assert r.status_code == 204
    assert anon_client.get("/api/auth/me", headers={"Authorization": f"Bearer {old}"}).status_code == 401
    assert anon_client.get("/api/auth/me").status_code == 200  # yeni çerez


def test_export_and_delete_account(anon_client, session_factory):
    _reg(anon_client)
    data = anon_client.get("/api/auth/me/export").json()
    assert data["account"]["email"] == "ayse@example.com" and data["inventory"] and data["consents"]
    assert anon_client.delete("/api/auth/me").status_code == 204
    assert anon_client.get("/api/auth/me").status_code == 401
    from sqlalchemy import func, select

    from app.models import ConsentRecord, Household, InventoryItem, User

    with session_factory() as s:
        assert s.scalar(select(func.count(User.id))) == 0
        assert s.scalar(select(func.count(Household.id))) == 0
        assert s.scalar(select(func.count(InventoryItem.id))) == 0
        # rıza kayıtları anonimleştirilerek saklanır
        records = list(s.scalars(select(ConsentRecord)))
        assert records and all(r.user_id is None and len(r.subject_hash) == 64 for r in records)


def test_google_login_creates_and_links(anon_client, monkeypatch):
    claims = {"sub": "g-123", "email": "ayse@example.com", "email_verified": True, "given_name": "Ayşe",
              "iss": "accounts.google.com"}
    monkeypatch.setattr(security, "verify_google_id_token", lambda t: claims)
    # ilk girişte yasal onay yoksa hesap açılmaz
    assert anon_client.post("/api/auth/google", json={"credential": "x"}).status_code == 400
    me = anon_client.post("/api/auth/google", json={"credential": "x", "accept_terms": True,
                                                    "acknowledge_privacy_notice": True}).json()
    assert me["google_linked"] and me["email_verified"] and not me["has_password"]
    anon_client.post("/api/auth/logout")
    # ikinci girişte onay tekrar istenmez
    assert anon_client.post("/api/auth/google", json={"credential": "x"}).status_code == 200


def test_google_rejects_bad_token(anon_client, monkeypatch):
    def bad(_):
        raise ValueError("imza geçersiz")

    monkeypatch.setattr(security, "verify_google_id_token", bad)
    assert anon_client.post("/api/auth/google", json={"credential": "x", "accept_terms": True,
                                                      "acknowledge_privacy_notice": True}).status_code == 401


@pytest.mark.parametrize("slug", ["aydinlatma", "acik-riza", "kullanim-kosullari", "cerez"])
def test_legal_documents_exist(anon_client, slug):
    r = anon_client.get(f"/api/legal/{slug}")
    assert r.status_code == 200 and len(r.text) > 500
