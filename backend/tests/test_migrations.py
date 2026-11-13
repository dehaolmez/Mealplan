from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

import app.models  # noqa: F401
from app.core.database import Base
from app.core.migrations import upgrade_database


def test_migrations_match_models(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'm.db'}")
    upgrade_database(engine)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn, opts={"render_as_batch": True}), Base.metadata)
    assert diff == [], f"Modeller ile migrasyonlar farklı; 'alembic revision --autogenerate' çalıştırın: {diff}"


def test_legacy_sqlite_is_backed_up_and_recreated(tmp_path):
    path = tmp_path / "eski.db"
    legacy = create_engine(f"sqlite:///{path}")
    with legacy.begin() as conn:
        conn.execute(text("CREATE TABLE ingredients (id INTEGER PRIMARY KEY, name TEXT)"))
    legacy.dispose()

    engine = create_engine(f"sqlite:///{path}")
    upgrade_database(engine)
    backups = list(tmp_path.glob("eski.db.bak-*"))
    assert len(backups) == 1
    assert "alembic_version" in inspect(create_engine(f"sqlite:///{path}")).get_table_names()
    # ikinci çalıştırma idempotent
    upgrade_database(create_engine(f"sqlite:///{path}"))
    assert len(list(tmp_path.glob("eski.db.bak-*"))) == 1
