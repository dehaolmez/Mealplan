from app.services import auth_service


def test_admin_bootstrap_and_endpoints(anon_client, session_factory):
    with session_factory() as s:
        user, created = auth_service.ensure_admin(s, "Admin@Example.com", "yonetici-sifre-1")
        assert created and user.is_admin and user.email == "admin@example.com"
        _, again = auth_service.ensure_admin(s, "admin@example.com", "baska-sifre-999")
        assert not again  # var olan hesabın şifresi değişmez

    me = anon_client.post("/api/auth/login", json={"email": "admin@example.com", "password": "yonetici-sifre-1"}).json()
    assert me["is_admin"] and me["email_verified"]
    consents = {c["kind"]: c["granted"] for c in me["consents"]}
    assert consents["health_data"] and consents["ai_transfer"] and not consents["marketing"]
    assert len(anon_client.get("/api/inventory").json()) > 0  # örnek veriyle gelir

    stats = anon_client.get("/api/admin/stats").json()
    assert stats["users"] == 1 and "live_products" in stats


def test_admin_endpoints_forbidden_for_normal_users(client):
    assert client.get("/api/auth/me").json()["is_admin"] is False
    assert client.get("/api/admin/stats").status_code == 401
    assert client.post("/api/admin/live-prices/refresh").status_code == 401


def test_cli_create_admin_generates_password(monkeypatch, tmp_path, capsys):
    from sqlalchemy.orm import sessionmaker

    from app import cli
    from app.core.database import make_engine

    eng = make_engine(f"sqlite:///{tmp_path / 'cli.db'}")
    monkeypatch.setattr(cli, "engine", eng)
    monkeypatch.setattr(cli, "SessionLocal", sessionmaker(bind=eng, expire_on_commit=False))
    assert cli.main(["create-admin", "yeni@example.com", "--generate"]) == 0
    out = capsys.readouterr().out
    assert "Yönetici oluşturuldu" in out and "Şifre:" in out
