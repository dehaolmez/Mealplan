"""Veritabanını otomatik olarak güncel şemaya getirir.

* Yeni veritabanı → tüm migrasyonlar uygulanır.
* Alembic öncesi (v0.1/v0.2) oluşturulmuş eski SQLite dosyası → yedeklenir (mealbird.db.bak-ZAMAN) ve
  sıfırdan oluşturulur. Eski sürümlerde yalnız demo veri bulunduğundan veri kaybı yoktur.
* SQLite dışı (PostgreSQL) eski şema → güvenlik için otomatik silinmez, hata verilir.
"""

import logging
import shutil
from datetime import datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.engine import Engine, make_url

log = logging.getLogger(__name__)
BACKEND_DIR = Path(__file__).resolve().parents[2]


def alembic_config(url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


def _is_legacy(engine: Engine) -> bool:
    tables = set(inspect(engine).get_table_names())
    return bool(tables) and "alembic_version" not in tables


def upgrade_database(engine: Engine) -> None:
    url = engine.url
    if _is_legacy(engine):
        if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
            raise RuntimeError(
                "Veritabanında migrasyon kaydı olmayan eski bir şema var. Yedekleyip boş bir veritabanı verin "
                "veya 'alembic stamp' ile işaretleyin."
            )
        engine.dispose()
        db_path = Path(url.database)
        backup = db_path.with_name(f"{db_path.name}.bak-{datetime.now():%Y%m%d-%H%M%S}")
        shutil.move(db_path, backup)
        log.warning("Eski şemalı veritabanı yedeklendi: %s — yeni veritabanı oluşturuluyor", backup)

    cfg = alembic_config(make_url(str(url)).render_as_string(hide_password=False))
    is_sqlite = url.get_backend_name() == "sqlite"
    with engine.connect() as connection:
        if is_sqlite:
            # SQLite'ta tablo yeniden kurulurken (batch) eski tablo DROP edilir; yabancı anahtarlar açıksa
            # ON DELETE CASCADE bağlı satırları (ör. tarif malzemeleri) siler. PRAGMA işlem dışında olmalı.
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.commit()
        try:
            with connection.begin():
                cfg.attributes["connection"] = connection
                command.upgrade(cfg, "head")
        finally:
            if is_sqlite:
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
                connection.commit()
