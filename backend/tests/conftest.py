from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.database import Base, get_db
from app.main import create_app
from app.seed.loader import seed
from app.services import clock

TODAY = date(2026, 11, 13)


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch):
    """Testler gerçek veritabanına/anahtar dosyasına asla dokunmaz."""
    from app.core import security
    from app.core.config import get_settings

    monkeypatch.setenv("MEALBIRD_AUTO_MIGRATE", "false")
    monkeypatch.setenv("MEALBIRD_SEED_ON_STARTUP", "false")
    monkeypatch.setenv("MEALBIRD_SECRET_KEY", "test-secret-key-0123456789-abcdefghijklmnop")
    get_settings.cache_clear()
    security.secret_key.cache_clear()
    yield
    get_settings.cache_clear()
    security.secret_key.cache_clear()


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr(clock, "today", lambda: TODAY)
    return TODAY


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    engine.dispose()


@pytest.fixture
def db(session_factory):
    with session_factory() as session:
        seed(session)
        yield session


REGISTER = {
    "email": "ayse@example.com",
    "password": "cok-gizli-sifre-1",
    "display_name": "Ayşe",
    "accept_terms": True,
    "acknowledge_privacy_notice": True,
    "health_data_consent": True,
    "location_consent": True,
    "with_sample_data": True,
}


@pytest.fixture
def anon_client(session_factory, monkeypatch):
    """Oturum açmamış istemci (kayıt/giriş testleri için)."""
    monkeypatch.setenv("MEALBIRD_SEED_ON_STARTUP", "false")
    from app.core import security
    from app.core.config import get_settings
    from app.services import rate_limit

    get_settings.cache_clear()
    rate_limit.reset()
    monkeypatch.setattr(security, "_N", 2**12)
    original = security.hash_password
    monkeypatch.setattr(security, "hash_password", lambda p, n=2**12: original(p, n=n))
    with session_factory() as s:
        seed(s)
    application = create_app()

    def _get_db():
        with session_factory() as s:
            yield s

    application.dependency_overrides[get_db] = _get_db
    with TestClient(application) as c:
        yield c
    get_settings.cache_clear()


@pytest.fixture
def client(session_factory, monkeypatch):
    monkeypatch.setenv("MEALBIRD_SEED_ON_STARTUP", "false")
    from app.core.config import get_settings

    get_settings.cache_clear()
    with session_factory() as s:
        seed(s)
    from app.core import security
    from app.services import rate_limit

    rate_limit.reset()
    # testlerde scrypt'i hızlandır (üretim parametreleri security.py'de)
    monkeypatch.setattr(security, "_N", 2**12)
    original = security.hash_password
    monkeypatch.setattr(security, "hash_password", lambda p, n=2**12: original(p, n=n))

    application = create_app()

    def _get_db():
        with session_factory() as s:
            yield s

    application.dependency_overrides[get_db] = _get_db
    with TestClient(application) as c:
        r = c.post("/api/auth/register", json=REGISTER)
        assert r.status_code == 201, r.text
        yield c
    get_settings.cache_clear()
