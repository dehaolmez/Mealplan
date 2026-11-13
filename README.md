# 🍽️ Meall

Ev içi akıllı yemek planlama, envanter (SKT) takibi ve bütçe optimizasyonu.
Mealbird tarzı "buzdolabında ne var?" tarif önerisi + Bring! tarzı hızlı, reyonlara ayrılmış alışveriş listesi.

## Hızlı başlangıç

```bash
# Backend (http://localhost:8000, API dokümanı: /docs)
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload

# Frontend (http://localhost:5173, /api isteklerini backend'e yönlendirir)
cd frontend
npm install && npm run dev

# Testler
cd backend && .venv/bin/pytest
```

İlk açılışta katalog (54 malzeme), 18 tarif, zincirler, demo ve pilot bölge test fiyatları yüklenir. Kayıt olurken
"Örnek envanterle başla" seçilirse hesaba örnek envanter eklenir. Veritabanı açılışta otomatik güncellenir.

## Teknoloji seçimleri

| Katman | Seçim | Neden |
|---|---|---|
| API | **Python 3.13 + FastAPI** | Tip güvenli Pydantic şemaları, otomatik OpenAPI dokümanı, hızlı geliştirme; besin/optimizasyon algoritmaları için Python doğal tercih |
| ORM / DB | **SQLAlchemy 2 + SQLite** | MVP'de sıfır kurulum; `MEALBIRD_DATABASE_URL` ile kod değişmeden PostgreSQL'e geçilir |
| Web | **React 19 + TypeScript + Vite** | Mobil öncelikli SPA; ek UI kütüphanesi yok, sade CSS token'ları (açık/koyu tema) |
| Yapay zekâ | **Claude (Anthropic SDK)**, isteğe bağlı | Kural tabanlı motorun adaylarını yeniden sıralar ve Türkçe gerekçe yazar |

## Mimari

```
backend/app/
  core/       ayarlar (env), veritabanı motoru/oturumu
  models/     SQLAlchemy tabloları
  domain/     SAF iş mantığı (DB'siz, birim testli)
    nutrition.py        Mifflin-St Jeor, TDEE, hedef & makro hesabı
    units.py            g/kg/ml/l/adet dönüşümleri (yoğunluk, adet ağırlığı)
    shelf_life.py       raf ömrü tahmini, SKT durum sınıfları
    stock.py            envanter anlık görüntüsü, FEFO (ilk bozulan ilk çıkar) tahsis
    requirements.py     tarif ihtiyaçlarını toplama, eksik tespiti
    recommender.py      "Buzdolabında ne var?" puanlama motoru
    price_optimizer.py  market fiyat eşleştirme ve 3 strateji
    ai_planner.py       Claude ile yeniden sıralama (isteğe bağlı)
  services/   DB orkestrasyonu (domain + modeller)
  schemas/    API giriş/çıkış şemaları (Pydantic)
  api/routes/ HTTP uç noktaları
  seed/       örnek veri
backend/tests/  101 test (domain, API, plan, diyet, harita/fiyat, canlı fiyat, fiş/tarif üretimi, hesap/KVKK, migrasyon)

frontend/src/
  api/        tipli API istemcisi ve tipler
  features/   Öneriler, Envanter, Plan, Alışveriş, Profil ekranları
  components/ ortak UI parçaları (SKT rozeti, uyarı şeridi, toast…)
```

### Veritabanı şeması

```
households (id, name, preferred_store_id, selected_store_ids)
members (household_id, name, birth_date, sex, height_cm, weight_kg, activity_level, goal)
ingredients (name, category, base_unit, grams_per_piece, density_g_per_ml,
             kcal/protein/carbs/fat per 100g,
             shelf_life_fridge_days, shelf_life_freezer_days, shelf_life_opened_days,
             is_staple, emoji)
inventory_items (household_id, ingredient_id, location[fridge|freezer], quantity, added_on,
                 expiry_date, expiry_estimated, opened)
recipes (name, servings, prep_minutes, meal_type, tags, description, instructions)
recipe_ingredients (recipe_id, ingredient_id, quantity, optional)
stores (name, color)
store_prices (store_id, ingredient_id, package_size, price, brand, source, updated_on)  UNIQUE(store, ingredient)
meal_plan_entries (household_id, day, meal_type, recipe_id, servings, cooked)
shopping_items (household_id, ingredient_id?, name, category, quantity, unit, note, checked,
                checked_at, archived, store_id, estimated_price, source)
```

Tüm miktarlar malzemenin **temel biriminde** (g / ml / adet) tutulur; kullanıcı girdisi (kg, l…) girişte dönüştürülür.
Envanterde her alım ayrı bir **parti** olarak tutulur, böylece aynı üründen farklı SKT'ler doğru izlenir.

## Modüller

**A. Beslenme profili** — Mifflin-St Jeor ile BMR → aktivite katsayısı (1.2–1.9) ile TDEE → hedef ayarı
(kilo verme −500, koruma 0, kazanım +300 kcal; BMR altına inilmez). Protein kg başına (1.4–1.8 g),
yağ enerjinin %30'u, karbonhidrat kalan enerji. Hane toplamı ve kişi başı öğün hedefi tarif puanlamasına girer.

**B. Envanter & SKT** — Buzdolabı/Buzluk. SKT girilmezse katalogdaki raf ömrü kuralıyla tahmin edilir (`~`).
Ürün açıldığında, açık raf ömrü daha kısaysa SKT öne çekilir; buzluğa taşınınca dondurucu kuralıyla yeniden hesaplanır.
Durumlar: geçmiş / kritik (≤1 gün) / yaklaşan (≤3 gün). Uygulama içi şerit + izin verilirse günde bir tarayıcı bildirimi.

**C. Öneri motoru & eksik tespiti** — Her tarif için:
`puan = 0.55·kapsama + 0.30·aciliyet + 0.15·besin uyumu`.
Aciliyet, tarifin FEFO ile tükettiği partilerin kalan gününe göre hesaplanır (7 gün ufuk) → bozulmak üzere olanlar öne çıkar.
SKT'si geçmiş ürünler stok sayılmaz; tuz/su gibi temel ürünler ve opsiyonel malzemeler eksik listesine girmez.
Eksikler hem tek tarif hem de bir plan aralığı (birden çok tarif toplanarak) için hesaplanır.
`?ai=true` ile Claude, aday tarifleri yeniden sıralayıp gerekçe yazar; model yalnızca aday ID'leri döndürebildiğinden
eksik/fiyat hesapları deterministik kalır. Claude erişilemezse kural tabanlı sıralamaya düşülür.

**D. Fiyat & alışveriş listesi** — Eksikler paket boyutuna yuvarlanarak (ör. 400 g eksik → 1 kg paket) market fiyatlarıyla eşleşir:
- `cheapest`: her ürün en ucuz marketten (çok duraklı)
- `single`: en çok ürünü bulunduran, en ucuz tek market
- `preferred`: tercih edilen market, orada olmayanlar en ucuz alternatiften

Bring! tarzı liste: reyon renkli kutucuklar, dokun = alındı, aynı ürün tekrar eklenince miktar birleşir, serbest metin desteği,
"son alınanlar"dan tek dokunuşla ekleme, "Envantere aktar" ile alınanlar SKT tahminiyle envantere girer.
Plandaki öğün "pişirildi" işaretlenince malzemeler envanterden FEFO ile düşülür.

## API özet

| Metod | Yol | Açıklama |
|---|---|---|
| GET/PATCH | `/api/household` | hane ayarları, seçili/tercih edilen marketler |
| GET | `/api/household/targets` | kişi ve hane kalori/makro hedefleri |
| POST/PUT/DELETE | `/api/household/members[/{id}]` | birey yönetimi |
| GET | `/api/ingredients?q=`, `/api/stores` | katalog |
| GET/POST | `/api/inventory` | envanter listesi / ekleme (SKT tahminli) |
| PATCH/DELETE | `/api/inventory/{id}` | miktar, açıldı, taşıma |
| GET | `/api/inventory/alerts` | SKT uyarıları |
| GET | `/api/recipes`, `/api/recipes/{id}` | tarifler (porsiyon başı besin değeriyle) |
| GET | `/api/recipes/recommendations?meal_type=&ai=` | "Buzdolabında ne var?" |
| POST | `/api/recipes/missing` | seçili tarifler / plan aralığı için eksikler |
| GET/POST/DELETE | `/api/plan` | haftalık plan |
| POST | `/api/plan/{id}/cook` | pişirildi → envanterden düş |
| GET | `/api/shopping` | reyonlara göre liste + son alınanlar |
| POST/PATCH/DELETE | `/api/shopping/items[/{id}]` | liste kalemleri |
| POST | `/api/shopping/optimize` | eksik → fiyat optimizasyonu (+ listeye ekle) |
| POST | `/api/shopping/checkout` | alınanları envantere aktar |

## Yapay zekâ (isteğe bağlı)

```bash
export ANTHROPIC_API_KEY=...        # veya `ant auth login`
export MEALBIRD_AI_ENABLED=true
```
Varsayılan model `claude-opus-5-5`, yapılandırılmış çıktı (Pydantic) ile. Güvenlik sınıflandırıcısı bir isteği reddederse
sunucu tarafı yedek model (`fallbacks: "default"`) devreye girer.

## v0.2: Market zincirleri, harita ve gerçek fiyat verisi

- **Zincir kataloğu** (`GET /api/chains`): BİM, A101, ŞOK, Migros, Macrocenter, CarrefourSA, Hakmar Express,
  Tarım Kredi, File, Metro, Bizim Toptan, Onur, Happy Center.
- **Yakındaki marketler** (`GET /api/places/nearby`, arayüzde 📍 Yakında): OpenStreetMap/Overpass verisi, Leaflet harita,
  zincir eşleştirme, mesafe sıralama, yol tarifi bağlantısı, 24 saat önbellek. Konum ~110 m'ye yuvarlanır.
- **Gerçek fiyat içe aktarma** (`POST /api/prices/import`, `GET /api/prices/template.csv`, Profil ekranında dosya yükleme).
- **Yalnız yakındaki marketlerle optimizasyon** (`"nearby_only": true`).

Ayrıntılı yol haritası, dinamik kullanım planı ve ihtiyaç listesi: [docs/ROADMAP.md](docs/ROADMAP.md).

## v0.5: Meall — otomatik haftalık plan, 162 tarif, öğün durumu

- **Yeni ad:** Meall (çalışma adı).
- **Başlangıç akışı (11 adım):** marketler, hedefler, kişiler ve formülle kalori hedefi, öğünler (planla / yemiyorum /
  kendim hallederim + ayrılan kalori), diyet (vejetaryen/vegan/pesketaryen/düşük karbonhidrat), alerji ve dışlamalar,
  sevilmeyen malzemeler, mutfak aletleri, günler, haftalık bütçe, tekrar tercihi. Profil'den tekrar açılabilir.
- **Otomatik haftalık plan:** kurallara uyan tarifler arasından buzdolabındakileri (önce bozulacakları) kullanan,
  kalori hedefine uyan (porsiyon ölçekleme), bütçeyi gözeten, protein çeşitliliği olan plan. "Bir pişir iki gün ye" ve
  "haftalık toplu pişirme" seçenekleri; kalan yemekler alışverişte iki kez sayılmaz.
- **Öğün durumu:** pişirdim / yapmadım / dışarıda yedim; atlanan öğün alışveriş listesinden düşer.
- **Katalog:** 54 → 170 malzeme, diyet/alerjen etiketleri; 18 → **162 tarif** (Gemini ile özgün yazıldı, malzemeler
  katalogla kısıtlı, insan eliyle temizlendi). Uygulama içinden "✨ Buzdolabımdakilerle yeni tarif" (haneye özel).
- **Tüm tarifler** gezgini (arama, öğün filtresi).

## v0.4: Canlı fiyat, fiş okuma, ücretsiz yayın

- **Canlı fiyat:** TÜBİTAK Market Fiyatı verisi; yakın şubelerdeki gerçek ürün ve fiyatlarla optimizasyon.
- **Fiş tara (Gemini):** fiş fotoğrafı → ürünler katalogla eşlenir → kontrol edip envantere ekle.
- **Yapay zekâ önerileri** Gemini ile (Claude seçeneği duruyor).
- **PostgreSQL** desteği; testler SQLite ve PostgreSQL'de koşar.
- **Tek Docker imajı** (API + arayüz), **Render blueprint**, **GitHub Actions CI**.
- Yayına alma rehberi: [docs/DEPLOY.md](docs/DEPLOY.md).

## v0.3: Hesaplar, KVKK, PWA, otomatik veritabanı

- **Giriş:** e-posta + şifre ve Google ile giriş, davet koduyla aynı haneyi paylaşma, şifre sıfırlama, e-posta doğrulama.
- **KVKK:** aydınlatma metni, açık rıza metni (sağlık verisi / konum / yapay zekâ / ticari ileti ayrı ayrı),
  kullanım koşulları, çerez politikası (taslak, `backend/app/legal/`). Rıza kayıtları, verilerimi indir,
  hesabı sil, rıza geri çekilince ilgili verinin silinmesi.
- **PWA:** telefona kurulabilir, çevrimdışı açılır.
- **Pilot bölge Ankara/Etimesgut:** harita merkezi, adres araması, "test" etiketli fiyatlar.
- **Konum hassasiyeti** ~11 m (`MEALBIRD_LOCATION_PRECISION`).
- **Veritabanı otomatik:** Alembic migrasyonları açılışta uygulanır; eski şemalı SQLite dosyası yedeklenip yenilenir.

Ayarların tamamı: `backend/.env.example`. Hukuki metinler hakkında: `docs/legal/README.md`.

## Bilinen sınırlar / sonraki adımlar

- Hazır gelen fiyatlar **demo** veridir ve hayali marketlere aittir. Gerçek zincir fiyatları CSV ile yüklenir;
  otomatik kaynak (ör. TÜBİTAK Market Fiyatı) için izin/erişim gerekir — bkz. docs/ROADMAP.md.
- Uygulama kapalıyken bildirim (Web Push) henüz yok.
- Kiler (oda sıcaklığı) saklama alanı yok — kapsam gereği yalnız buzdolabı/buzluk; kuru gıdalar şimdilik buzdolabı altında.
