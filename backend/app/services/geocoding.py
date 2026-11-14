"""Adres → koordinat (OSM Nominatim). Ücretsiz; kullanım kuralı: saniyede ≤1 istek, kimlik bildiren User-Agent,
sonuçların önbelleklenmesi. Bu yüzden istekleri sıraya koyup sonuçları bellekte tutuyoruz."""

import threading
import time
from functools import lru_cache

import httpx

from app.core.config import get_settings
from app.services.errors import BadRequest

_lock = threading.Lock()
_last_call = 0.0


@lru_cache(maxsize=512)
def _search_cached(query: str) -> tuple[tuple[str, float, float], ...]:
    global _last_call
    s = get_settings()
    with _lock:
        wait = 1.0 - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()
        try:
            resp = httpx.get(
                s.nominatim_url,
                params={"q": query, "format": "jsonv2", "limit": 5, "countrycodes": "tr", "accept-language": "tr"},
                headers={"User-Agent": s.http_user_agent},
                timeout=15,
            )
            resp.raise_for_status()
            rows = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise BadRequest(f"Adres araması şu an yapılamıyor: {exc}") from exc
    return tuple((r.get("display_name", ""), float(r["lat"]), float(r["lon"])) for r in rows)


def search(query: str) -> list[dict]:
    q = " ".join(query.split())
    if len(q) < 3:
        raise BadRequest("En az 3 karakter girin")
    return [{"label": label, "lat": lat, "lon": lon} for label, lat, lon in _search_cached(q.lower())]
