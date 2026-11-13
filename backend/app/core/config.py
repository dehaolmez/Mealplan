"""Uygulama ayarları. Tüm değerler ortam değişkenleri (MEALBIRD_ önekli) veya .env ile ezilebilir."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MEALBIRD_", env_file=".env", extra="ignore")

    app_name: str = "Mealbird API"
    database_url: str = "sqlite:///./mealbird.db"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    # Derlenmiş arayüz (frontend/dist) bu klasördeyse API ile aynı adresten sunulur (tek servisli dağıtım)
    static_dir: str = ""

    # Açılışta veritabanını otomatik migrasyonla güncelle (testlerde kapalı)
    auto_migrate: bool = True
    # Uygulama ilk açıldığında örnek katalog/tarif/fiyat verisini yükle
    seed_on_startup: bool = True
    # Pilot bölge (Etimesgut) için "test" etiketli fiyatları yükle. Canlı fiyat kaynağı çalıştığı için varsayılan kapalı.
    load_test_prices: bool = False

    # Canlı fiyat: TÜBİTAK "Market Fiyatı" (marketfiyati.org.tr) kamuya açık verisi
    live_prices_enabled: bool = True
    marketfiyati_url: str = "https://api.marketfiyati.org.tr"
    live_prices_ttl_hours: int = 12
    live_prices_min_interval_s: float = 1.0  # kaynağı yormamak için istekler arası en az süre
    live_prices_radius_km: int = 3
    # Açılışta pilot bölgenin tüm katalog fiyatlarını arka planda tazele
    live_prices_prefetch_pilot: bool = True

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
    # Dış servise gönderilen / saklanan konumun ondalık hassasiyeti (4 ≈ 11 m)
    location_precision: int = 4
    # Adres arama (OSM Nominatim, ücretsiz; saniyede en fazla 1 istek kuralına uyulur)
    nominatim_url: str = "https://nominatim.openstreetmap.org/search"
    # Pilot bölge: Ankara / Etimesgut (harita varsayılan merkezi)
    pilot_name: str = "Ankara, Etimesgut"
    pilot_lat: float = 39.9496
    pilot_lon: float = 32.6618
    places_max_radius_m: int = 10_000

    # Kimlik doğrulama
    # Boşsa geliştirme için backend/.secret_key dosyasında rastgele bir anahtar üretilip saklanır.
    secret_key: str = ""
    session_days: int = 30
    cookie_secure: bool = False  # üretimde (HTTPS) True
    google_client_id: str = ""   # Google ile giriş için (Google Cloud Console > OAuth istemci kimliği)
    public_base_url: str = "http://localhost:5173"
    # E-posta (şifre sıfırlama/doğrulama). Boşsa bağlantılar sunucu günlüğüne yazılır (geliştirme).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "Mealbird <no-reply@localhost>"

    # Yapay zekâ. Sağlayıcının anahtarı yoksa kural tabanlı motor çalışır.
    ai_enabled: bool = True
    ai_provider: str = "gemini"  # "gemini" | "claude"
    # Gemini (Google AI Studio anahtarı). OpenAI uyumlu uç nokta: anahtar Authorization: Bearer ile gider.
    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    # Sırayla denenir (yoğunluk/erişim hatasında bir sonrakine geçilir)
    gemini_models: list[str] = ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.1-flash-lite"]
    # Claude (ANTHROPIC_API_KEY ortam değişkeni)
    ai_model: str = "claude-opus-5-5"
    ai_effort: str = "medium"

    @property
    def ai_available(self) -> bool:
        if not self.ai_enabled:
            return False
        return bool(self.gemini_api_key) if self.ai_provider == "gemini" else True


@lru_cache
def get_settings() -> Settings:
    return Settings()
