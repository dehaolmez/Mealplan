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

    # Yapay zekâ (Claude) ile öneri sıralama/açıklama. Kapalıyken kural tabanlı motor çalışır.
    ai_enabled: bool = False
    ai_model: str = "claude-opus-5-5"
    ai_effort: str = "medium"


@lru_cache
def get_settings() -> Settings:
    return Settings()
