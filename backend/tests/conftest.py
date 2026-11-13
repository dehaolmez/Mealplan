from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.database import Base, get_db
from app.main import create_app
from app.seed.loader import seed
from app.services import clock

TODAY = date(2026, 11, 13)


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr(clock, "today", lambda: TODAY)
    return TODAY


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    engine.dispose()


@pytest.fixture
def db(session_factory):
    with session_factory() as session:
        seed(session, with_demo=False)
        yield session


@pytest.fixture
def client(session_factory, monkeypatch):
    monkeypatch.setenv("MEALBIRD_SEED_ON_STARTUP", "false")
    from app.core.config import get_settings

    get_settings.cache_clear()
    with session_factory() as s:
        seed(s, with_demo=True)

    application = create_app()

    def _get_db():
        with session_factory() as s:
            yield s

    application.dependency_overrides[get_db] = _get_db
    with TestClient(application) as c:
        yield c
    get_settings.cache_clear()
