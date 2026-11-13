"""SQLAlchemy motoru ve oturum yönetimi.

SQLite ile başlıyoruz (sıfır kurulum); DATABASE_URL değiştirilerek PostgreSQL'e geçilebilir.
"""

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def normalize_url(url: str) -> str:
    """Barındırma servislerinin verdiği "postgres://" / "postgresql://" adreslerini psycopg 3 sürücüsüne yönlendirir."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def make_engine(url: str) -> Engine:
    url = normalize_url(url)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    # pool_pre_ping: ücretsiz bulut veritabanları boşta bağlantıları kapatabilir
    engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _enable_fk(dbapi_conn, _):  # pragma: no cover - sürücü kancası
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

    return engine


engine = make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
