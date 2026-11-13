from fastapi import APIRouter, Query, Request
from fastapi.responses import PlainTextResponse

from app.api.deps import DB, CurrentHousehold
from app.schemas.places import ChainOut, NearbyOut, PriceImportOut
from app.core.config import get_settings
from app.services import geocoding, places_service, price_import
from app.services.errors import BadRequest

router = APIRouter(tags=["Marketler, Harita & Fiyat Verisi"])


@router.get("/chains", response_model=list[ChainOut])
def list_chains(db: DB):
    """Türkiye'deki büyük market zincirleri (indirim, süper/hipermarket, toptan, kooperatif)."""
    priced = places_service.chains_with_prices(db)
    return [places_service.chain_out(c, priced) for c in places_service.list_chains(db)]


@router.get("/places/nearby", response_model=NearbyOut)
def nearby(
    db: DB,
    household: CurrentHousehold,
    lat: float | None = None,
    lon: float | None = None,
    radius_m: int | None = Query(default=None, ge=200, le=10_000),
    only_chains: bool = True,
    chain_ids: list[int] | None = Query(default=None),
    refresh: bool = False,
):
    """Konuma yakın market şubeleri (OpenStreetMap). lat/lon verilmezse kayıtlı ev konumu kullanılır."""
    lat = lat if lat is not None else household.home_lat
    lon = lon if lon is not None else household.home_lon
    if lat is None or lon is None:
        raise BadRequest("Konum gerekli: lat/lon gönderin veya profilde ev konumunu kaydedin")
    return places_service.nearby(
        db, lat, lon, radius_m or household.search_radius_m,
        only_chains=only_chains, chain_ids=chain_ids, refresh=refresh,
    )


@router.post("/prices/import", response_model=PriceImportOut)
async def import_prices(request: Request, db: DB):
    """Gövdede CSV (text/csv) bekler. Şablon için GET /api/prices/template.csv"""
    raw = await request.body()
    if not raw:
        raise BadRequest("CSV gövdesi boş")
    if len(raw) > 5_000_000:
        raise BadRequest("Dosya çok büyük (en fazla 5 MB)")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("cp1254")  # Excel'in Türkçe Windows kodlaması
    return price_import.import_csv(db, text)


@router.get("/prices/template.csv", response_class=PlainTextResponse)
def price_template():
    return PlainTextResponse(price_import.TEMPLATE, media_type="text/csv; charset=utf-8")


@router.get("/prices/stats")
def price_stats(db: DB):
    """Market başına fiyat sayısı ve son güncelleme tarihi (verinin tazeliğini izlemek için)."""
    return price_import.price_stats(db)


@router.get("/geocode")
def geocode(q: str = Query(min_length=3, max_length=200)):
    """Adres/semt arama (OSM Nominatim). Ör. 'Etimesgut Elvankent'"""
    return geocoding.search(q)


@router.get("/places/pilot")
def pilot():
    """Pilot bölge (haritanın varsayılan merkezi)."""
    s = get_settings()
    return {"name": s.pilot_name, "lat": s.pilot_lat, "lon": s.pilot_lon}
