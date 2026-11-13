"""Overpass API istemcisi. Birden çok uç nokta sırayla denenir; ağ hataları tek bir istisnaya indirgenir."""

import logging

import httpx

from app.core.config import get_settings
from app.domain.osm import OsmShop, build_query, parse_elements

log = logging.getLogger(__name__)


class MapDataUnavailable(Exception):
    pass


def fetch_shops(lat: float, lon: float, radius_m: int) -> list[OsmShop]:
    s = get_settings()
    query = build_query(lat, lon, radius_m, s.overpass_timeout_s)
    last_error: Exception | None = None
    for endpoint in s.overpass_endpoints:
        try:
            resp = httpx.post(
                endpoint,
                data={"data": query},
                headers={"User-Agent": s.http_user_agent},
                timeout=s.overpass_timeout_s + 10,
            )
            if resp.status_code == 429:
                last_error = MapDataUnavailable("Harita servisi yoğun (429)")
                continue
            resp.raise_for_status()
            return parse_elements(resp.json())
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("Overpass %s başarısız: %s", endpoint, exc)
            last_error = exc
    raise MapDataUnavailable(f"Harita verisine ulaşılamadı: {last_error}")
