"""Konum yardımcıları: mesafe, gizlilik için yuvarlama, önbellek anahtarı."""

import math

EARTH_RADIUS_M = 6_371_000

# Türkiye'nin kaba sınır kutusu: hatalı/uç koordinatları erken yakalamak için
TR_BBOX = (35.8, 25.6, 42.2, 44.9)  # güney, batı, kuzey, doğu


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


# 4 ondalık ≈ 11 m (enlem) — dış servise giden ve saklanan konum hassasiyeti.
DEFAULT_PRECISION = 4


def round_coord(value: float, decimals: int = DEFAULT_PRECISION) -> float:
    """Konumu kabalaştırır: 3 ondalık ≈ 110 m, 4 ondalık ≈ 11 m, 5 ondalık ≈ 1 m."""
    return round(value, decimals)


def in_turkey(lat: float, lon: float) -> bool:
    s, w, n, e = TR_BBOX
    return s <= lat <= n and w <= lon <= e


def cache_key(lat: float, lon: float, radius_m: int, decimals: int = DEFAULT_PRECISION) -> str:
    # Yarıçapı 500 m'lik basamaklara yuvarla ki benzer aramalar aynı önbelleği kullansın
    bucket = max(500, int(math.ceil(radius_m / 500) * 500))
    return f"{round_coord(lat, decimals)}:{round_coord(lon, decimals)}:{bucket}"
