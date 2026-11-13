"""Şifre özetleme (scrypt, standart kütüphane), oturum/amaçlı token'lar (JWT HS256) ve Google kimlik doğrulama."""

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import jwt

from app.core.config import get_settings

# scrypt parametreleri: OWASP önerisi (N=2^17, r=8, p=1) ≈ 128 MB bellek
_N, _R, _P, _DKLEN = 2**17, 8, 1, 32
_MAXMEM = 256 * 1024 * 1024
SECRET_FILE = Path(__file__).resolve().parents[2] / ".secret_key"


@lru_cache
def secret_key() -> str:
    configured = get_settings().secret_key
    if configured:
        return configured
    # Geliştirme kolaylığı: anahtar yoksa bir kere üret ve dosyada sakla (git'e girmez)
    if SECRET_FILE.exists():
        return SECRET_FILE.read_text().strip()
    key = secrets.token_urlsafe(48)
    SECRET_FILE.write_text(key)
    SECRET_FILE.chmod(0o600)
    return key


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def hash_password(password: str, *, n: int = _N) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=n, r=_R, p=_P, dklen=_DKLEN, maxmem=_MAXMEM)
    return f"scrypt${n}${_R}${_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        algo, n, r, p, salt, digest = stored.split("$")
        if algo != "scrypt":
            return False
        calc = hashlib.scrypt(password.encode(), salt=_unb64(salt), n=int(n), r=int(r), p=int(p),
                              dklen=len(_unb64(digest)), maxmem=_MAXMEM)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(calc, _unb64(digest))


def create_token(user_id: int, purpose: str, ttl: timedelta, version: int = 0, extra: dict | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "pur": purpose, "ver": version, "iat": now, "exp": now + ttl, **(extra or {})}
    return jwt.encode(payload, secret_key(), algorithm="HS256")


def decode_token(token: str, purpose: str) -> dict | None:
    try:
        payload = jwt.decode(token, secret_key(), algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    if payload.get("pur") != purpose:
        return None
    return payload


def email_fingerprint(email: str) -> str:
    """Rıza kayıtlarında e-postanın kendisi yerine anahtarlı özeti tutulur."""
    return hmac.new(secret_key().encode(), email.strip().lower().encode(), hashlib.sha256).hexdigest()


GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")
_google_jwks = jwt.PyJWKClient("https://www.googleapis.com/oauth2/v3/certs", cache_keys=True)


def verify_google_id_token(token: str) -> dict:
    """Google Identity Services'ten gelen ID token'ı Google'ın açık anahtarlarıyla doğrular."""
    client_id = get_settings().google_client_id
    if not client_id:
        raise ValueError("Google ile giriş yapılandırılmamış")
    key = _google_jwks.get_signing_key_from_jwt(token)
    claims = jwt.decode(token, key.key, algorithms=["RS256"], audience=client_id)
    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise ValueError("Geçersiz token yayıncısı")
    if not claims.get("email") or not claims.get("email_verified"):
        raise ValueError("Google hesabında doğrulanmış e-posta yok")
    return claims
