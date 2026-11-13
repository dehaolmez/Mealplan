"""Uygulama ayarları. Tüm değerler ortam değişkenleri (MEALBIRD_ önekli) veya .env ile ezilebilir."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MEALBIRD_", env_file=".env", extra="ignore")

    app_name: str = "Mealbird API"
    database_url: str = "sqlite:///./mealbird.db"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Uygulama ilk açıldığında örnek katalog/tarif/fiyat verisini yükle
    seed_on_startup: bool = True

    # SKT uyarı eşikleri (gün)
    expiry_critical_days: int = 1
    expiry_warning_days: int = 3

    # Harita / yakındaki marketler (OpenStreetMap Overpass API). Sırayla denenir.
    overpass_endpoints: list[str] = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
    ]
    overpass_timeout_s: int = 25
    # Overpass kullanım kuralları uygulamanın kendini tanıtmasını ister
    http_user_agent: str = "Mealbird/0.2 (+https://github.com/dehaolmez/mealplan)"
    places_cache_hours: int = 24
    places_max_radius_m: int = 10_000

    # Yapay zekâ (Claude) ile öneri sıralama/açıklama. Kapalıyken kural tabanlı motor çalışır.
    ai_enabled: bool = False
    ai_model: str = "claude-opus-5-5"
    ai_effort: str = "medium"


@lru_cache
def get_settings() -> Settings:
    return Settings()
