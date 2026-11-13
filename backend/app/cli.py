"""Komut satırı araçları.

    python -m app.cli create-admin ornek@eposta.com            # şifre sorulur
    python -m app.cli create-admin ornek@eposta.com --generate # güçlü şifre üretip bir kez yazdırır
"""

import argparse
import getpass
import secrets
import sys

import app.models  # noqa: F401
from app.core.database import SessionLocal, engine
from app.core.migrations import upgrade_database
from app.seed.loader import seed
from app.services import auth_service


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    ca = sub.add_parser("create-admin", help="Yönetici hesabı oluştur / yetki ver")
    ca.add_argument("email")
    ca.add_argument("--generate", action="store_true", help="Rastgele şifre üret")
    args = parser.parse_args(argv)

    if args.cmd == "create-admin":
        password = secrets.token_urlsafe(12) if args.generate else getpass.getpass("Şifre (en az 8 karakter): ")
        if len(password) < 8:
            print("Şifre en az 8 karakter olmalı", file=sys.stderr)
            return 1
        upgrade_database(engine)
        with SessionLocal() as db:
            seed(db)
            user, created = auth_service.ensure_admin(db, args.email, password)
        if created:
            print(f"Yönetici oluşturuldu: {user.email}" + (f"\nŞifre: {password}" if args.generate else ""))
        else:
            print(f"Mevcut hesaba yönetici yetkisi verildi: {user.email} (şifre değişmedi)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
