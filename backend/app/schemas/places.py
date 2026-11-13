from pydantic import BaseModel

from app.models.enums import ChainKind


class ChainOut(BaseModel):
    id: int
    slug: str
    name: str
    kind: ChainKind
    parent: str
    website: str
    color: str
    in_market_fiyati: bool
    has_prices: bool
    price_source: str | None = None  # "real" | "test" | None


class PlaceOut(BaseModel):
    id: int
    name: str
    brand: str
    shop: str
    lat: float
    lon: float
    address: str
    opening_hours: str
    distance_m: int
    chain: ChainOut | None
    osm_url: str


class ChainSummaryOut(BaseModel):
    chain: ChainOut
    count: int
    nearest_m: int
    nearest_place_id: int


class NearbyOut(BaseModel):
    lat: float
    lon: float
    radius_m: int
    from_cache: bool
    chains: list[ChainSummaryOut]
    places: list[PlaceOut]


class PriceImportError(BaseModel):
    line: int
    error: str


class PriceImportOut(BaseModel):
    created: int
    updated: int
    stores_created: list[str]
    errors: list[PriceImportError]
