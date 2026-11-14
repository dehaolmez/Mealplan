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


def test_sqlite_table_rebuild_keeps_child_rows(tmp_path):
    """Tarif tablosu yeniden kurulurken (05b09fa15cd3) tarif malzemeleri silinmemeli."""
    from alembic import command

    from app.core.database import make_engine
    from app.core.migrations import alembic_config

    path = tmp_path / "eski.db"
    engine = make_engine(f"sqlite:///{path}")  # yabancı anahtarlar açık (uygulamadaki gibi)
    cfg = alembic_config(f"sqlite:///{path}")
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "d15b5bcc7100")
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO ingredients (id, name, category, base_unit, kcal_per_100g, protein_per_100g, "
                          "carbs_per_100g, fat_per_100g, is_staple, emoji) VALUES (1, 'Domates', 'Manav', 'g', 18, 1, 4, 0, 0, 'x')"))
        conn.execute(text("INSERT INTO recipes (id, name, description, instructions, servings, prep_minutes, meal_type, tags) "
                          "VALUES (1, 'Çoban Salata', '', '', 2, 10, 'lunch', '')"))
        conn.execute(text("INSERT INTO recipe_ingredients (recipe_id, ingredient_id, quantity, optional) VALUES (1, 1, 300, 0)"))
    upgrade_database(engine)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM recipe_ingredients")).scalar() == 1
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1  # sonra yeniden açık
