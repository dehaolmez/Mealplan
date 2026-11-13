# Mealbird — Yol Haritası, Dinamik Kullanım ve İhtiyaç Listesi

Son güncelleme: 13 Kasım 2026

Bu belge üç şeyi anlatır:
1. MVP'den sonraki adımların **sabit kod yerine dinamik veriyle** nasıl çalışacağı,
2. bu adımlar için **senden (proje sahibinden) gerekenler**,
3. Türkiye'deki büyük market zincirleri ve **konum tabanlı yakın market** özelliği.

---

## 1. Şu an çalışanlar (v0.2)

| Özellik | Durum | Nasıl dinamik |
|---|---|---|
| Market zinciri kataloğu (13 zincir) | ✅ | `GET /api/chains`; veritabanında, kod değişmeden eklenip düzenlenebilir |
| Yakındaki marketler (harita) | ✅ | OpenStreetMap/Overpass'tan **canlı** çekilir, 24 saat önbelleklenir |
| Şube ↔ zincir eşleştirme | ✅ | Zincirin `aliases` alanındaki takma adlarla; yeni yazım biçimi = yeni takma ad |
| Gerçek fiyat içe aktarma (CSV) | ✅ | `POST /api/prices/import`; her satır bir zincir + malzeme + paket + fiyat |
| "Yalnız yakındaki marketler" ile fiyat optimizasyonu | ✅ | Ev konumuna yakın şubesi olan zincirlerin **gerçek** fiyatları kullanılır |
| Fiyat tazeliği izleme | ✅ | `GET /api/prices/stats` (market başına fiyat sayısı, son güncelleme) |

Demo fiyatlar hayali marketlere (Ekonomi Market, Mahalle Bakkal, Süper Market) aittir ve `demo` etiketlidir.
Gerçek zincirlere **uydurma fiyat yazılmaz**; gerçek zincirler fiyatı yalnız içe aktarılan veriden alır.

---

## 2. Adımlar ve dinamik kullanım planı

### 2.1 Gerçek fiyat verisi (en kritik adım)

**Hedef:** Optimizasyonun gerçek raf fiyatlarıyla çalışması.

**Mimari (hazır):** Tüm kaynaklar aynı CSV/satır formatına dönüştürülüp `price_import.import_csv()`'den geçer.
Bu sayede kaynak değişse de uygulamanın geri kalanı değişmez.

```
[Kaynak] ──► [Dönüştürücü] ──► chain,ingredient,package_size,unit,price,brand,date ──► import_csv ──► store_prices
```

**Kaynak seçenekleri (önerilen sırayla):**

| # | Kaynak | Artı | Eksi / risk |
|---|---|---|---|
| 1 | **TÜBİTAK "Market Fiyatı"** (marketfiyati.org.tr) — A101, BİM, CarrefourSA, Hakmar, Migros, Tarım Kredi, ŞOK; ~50 bin ürün, günlük güncelleme | Resmî, 7 büyük zincir, günlük | Herkese açık, belgelenmiş bir API'si olup olmadığı doğrulanmadı. **Kullanım koşulları ve izin** gerekli (bkz. §3) |
| 2 | Zincirlerin kendi online mağaza / kampanya verileri | Marka ve paket detayı zengin | Her zincir ayrı entegrasyon; çoğunda resmî API yok, kazıma (scraping) kullanım koşullarına takılabilir |
| 3 | Kullanıcı katkısı (fiş fotoğrafı/OCR veya elle giriş) | Yerel ve gerçek fiyat, hukuki risk düşük | Kapsam başta düşük, doğrulama gerekir |
| 4 | Elle hazırlanan CSV (şu an çalışıyor) | Hemen kullanılabilir | Elle bakım |

**Dinamikleştirme adımları:**
1. `PriceProvider` arayüzü: `fetch() -> Iterable[satır]`. Her kaynak bir sağlayıcı olur (Market Fiyatı, CSV klasörü, OCR…).
2. **Ürün eşleştirme tablosu** (`product_mappings`): kaynaktaki ürün adı/barkodu → katalog malzemesi.
   Bilinmeyen ürünler bir "eşleştirme bekleyenler" listesine düşer; admin ekranından ya da yapay zekâ önerisiyle eşlenir.
3. **Zamanlanmış görev** (günde 1 kez, örn. 06:00 TSİ): sağlayıcıları çalıştır → içe aktar → `prices/stats` ile tazeliği kontrol et.
4. Fiyat geçmişi tablosu (`price_history`): "bu hafta ucuzladı" bildirimleri ve fiyat trendi için.
5. Şube bazlı fiyat gerekiyorsa (Market Fiyatı şube/il bazlı veriyor olabilir), `store_prices`'a `place_id`/`city` eklenir;
   optimizasyon o zaman doğrudan **en yakın şubenin** fiyatını kullanır.

### 2.2 Konum ve harita (çalışıyor, genişletilecek)

- **Şu an:** Tarayıcıdan konum (izinli) veya haritaya dokunma → Overpass sorgusu → zincir eşleştirme → mesafeye göre liste + harita.
- **Gizlilik:** Konum dış servise **~110 m'ye yuvarlanarak** gönderilir; ev konumu da aynı hassasiyetle saklanır.
- **Dinamikleştirme:**
  1. **Kendi Overpass sunucumuz** (veya ücretli sağlayıcı): genel Overpass sunucuları hız sınırlıdır; üretimde
     Türkiye OSM özeti (Geofabrik, ~1 GB) ile kendi Overpass/PostGIS kurulumumuz önerilir. Uç noktalar zaten
     `MEALBIRD_OVERPASS_ENDPOINTS` ile değiştirilebilir.
  2. **Gece toplu güncelleme:** İl/ilçe bazında tüm şubeleri önceden çekip `places` tablosunda tutmak (istek anında dış servise gitmeden).
  3. **Mesafe + fiyat birlikte optimizasyon:** "200 TL tasarruf için 2 km daha yürür müsün?" — yol maliyeti/zaman ağırlığı kullanıcı ayarı olur.
  4. **Rota:** Birden çok marketli alışverişte sıralı rota (OSRM / GraphHopper).
  5. Açık/kapalı durumu: OSM `opening_hours` alanı ayrıştırılıp "şu an açık" filtresi.

### 2.3 Kimlik doğrulama ve çok haneli yapı

- `api/deps.py::current_household` tek değişim noktası. Plan: e-posta + şifre veya Google/Apple ile giriş (JWT),
  `users` ↔ `households` çoka-çok (aile üyeleri aynı listeyi paylaşır).
- **Paylaşılan alışveriş listesi (Bring! deneyimi):** WebSocket/SSE ile anlık senkron; biri "alındı" deyince diğerinde düşer.

### 2.4 Veritabanı ve dağıtım

- **PostgreSQL + PostGIS** (konum sorguları için), **Alembic** migrasyonları.
  ⚠️ v0.1'den v0.2'ye geçişte şema değişti: geliştirme ortamında `backend/mealbird.db` dosyasını silip yeniden başlatın.
- Docker Compose (api + web + db), CI'da testler (GitHub Actions).
- Barındırma: Türkiye/AB bölgesi (KVKK açısından veri yerelliği avantajı).

### 2.5 PWA ve bildirimler

- Servis çalışanı + Web Push: SKT bildirimleri uygulama kapalıyken de gelir; çevrimdışı alışveriş listesi.
- Ana ekrana eklenebilir uygulama (iOS 16.4+ ve Android'de web push destekli).

### 2.6 Yapay zekâ genişletmeleri

- Fiş fotoğrafından envantere ekleme (görsel → ürün + miktar + tarih).
- Fiyat kaynaklarından gelen ürün adlarını katalogla eşleştirme önerisi.
- Haftalık plan üretimi (bütçe + besin hedefi + israf önleme birlikte).

### 2.7 Kiler (oda sıcaklığı) saklama alanı

Kuru gıdalar için üçüncü saklama alanı; raf ömrü kuralları zaten malzeme bazında olduğundan küçük bir değişiklik.

---

## 3. Senden gerekenler

Önceliğe göre sıralı. **Kalın** olanlar bir sonraki adımı doğrudan engelliyor.

| # | Ne | Neden | Format / not |
|---|---|---|---|
| 1 | **Fiyat kaynağı kararı ve izni** | Gerçek fiyat olmadan optimizasyon demo kalır | Market Fiyatı için TÜBİTAK BİLGEM'e veri erişimi/API talebi (kurumsal başvuru senden olmalı) veya zincirlerle doğrudan anlaşma. Alternatif: başlangıçta elle CSV |
| 2 | **Hedef şehir/ilçe(ler)** | Pilot bölge için şube verisini önceden çekmek ve fiyat kapsamını belirlemek | Örn. "İstanbul – Kadıköy, Ataşehir" |
| 3 | **Örnek gerçek fiyat CSV'si** (20–50 ürün) | Uçtan uca gerçek veriyle test | `GET /api/prices/template.csv` şablonu |
| 4 | Hedef platform | Mobil uygulama mı, PWA mı? | PWA önerim: tek kod tabanı, mağaza onayı gerekmez |
| 5 | Kimlik doğrulama tercihi | Çok haneli yapı | E-posta/şifre, Google, Apple — hangileri? |
| 6 | Barındırma tercihi + alan adı | Dağıtım | Türkiye/AB bölgesi önerilir (KVKK) |
| 7 | KVKK metinleri | Konum ve sağlık verisi (boy, kilo) işleniyor | Aydınlatma metni + açık rıza akışı; hukuki metin senden/hukuk danışmanından |
| 8 | Overpass kullanımı | Genel sunucular hız sınırlı | Üretimde kendi sunucumuzu mu kuralım, ücretli sağlayıcı mı? |
| 9 | (İsteğe bağlı) Anthropic API anahtarı | Yapay zekâ önerileri | Uygulamanın kendi ortamına ortam değişkeni olarak; sohbete yapıştırma |
| 10 | Marka/tasarım | Logo, renkler, uygulama adı kesinleşti mi? | "Mealbird" çalışma adı |

---

## 4. Türkiye'deki büyük süpermarket ve hipermarketler

Uygulama kataloğunda (`/api/chains`) bulunan zincirler. Mağaza sayıları **2025 yıl sonu** basın kaynaklarındandır,
hızla değiştiği için koda yazılmamıştır; resmî rakamlar için şirket açıklamalarına bakılmalıdır.

| Zincir | Tür | Bağlı grup | ~Mağaza (2025 sonu) | Market Fiyatı'nda |
|---|---|---|---|---|
| BİM | İndirim marketi | BİM Birleşik Mağazalar | ~14.500 (yurt dışı mağazalar dahil olabilir) | ✓ |
| A101 | İndirim marketi | Yeni Mağazacılık A.Ş. | ~13.500 | ✓ |
| ŞOK | İndirim marketi | Şok Marketler (Yıldız Holding) | ~11.800 | ✓ |
| Migros (M, MM, MMM, Migros Jet, 5M) | Süper/hipermarket | Migros Ticaret | ~3.900 (tüm formatlar) | ✓ |
| Macrocenter | Premium | Migros Ticaret | (Migros içinde) | — |
| CarrefourSA (Hiper, Süper, Express, Gurme) | Hipermarket | A101'in çatı şirketi çoğunluk payını devraldı | ~700 | ✓ |
| Hakmar Express | İndirim marketi | Hakmar | ~800 | ✓ |
| Tarım Kredi Kooperatif Market | Kooperatif | Tarım Kredi Kooperatifleri | — | ✓ |
| File | Süpermarket | BİM | — | — |
| Metro Toptancı Market | Toptan | Metro | — | — |
| Bizim Toptan | Toptan | Bizim Toptan Satış Mağazaları | — | — |
| Onur Market | Bölgesel (İstanbul/Trakya) | — | — | — |
| Happy Center | Bölgesel (Trakya) | — | — | — |

Yeni zincir eklemek kod gerektirmez: `chains` tablosuna bir satır (ad, tür, renk, OSM takma adları) yeterlidir.
Pilot bölgende güçlü bir bölgesel zincir varsa söylemen yeterli.

**Kaynaklar:**
[TÜBİTAK – Zincir market fiyatlarına anında erişim](https://tubitak.gov.tr/tr/haber/zincir-market-fiyatlarina-aninda-erisimin-onu-acildi) ·
[Bloomberg HT – Gıda perakendeciliğinin röntgeni](https://www.bloomberght.com/turkiye-de-120-milyar-dolari-asan-gida-perakendeciliginin-rontgeni-3782601) ·
[CNBC-e – A101/CarrefourSA birleşmesi](https://www.cnbce.com/haberler/turkiyenin-2-dev-market-zinciri-resmen-birlesti-perakende-sektorunde-pazar-payi-nasil-degisti-g34237) ·
[Webrazzi – Market Fiyatı platformu](https://webrazzi.com/2025/02/11/sanayi-ve-teknoloji-bakanligi-ndan-market-fiyatlarini-karsilastiran-platform-market-fiyati/)

---

## 5. Konum tabanlı yakın marketler — teknik özet

- **Veri:** OpenStreetMap (ODbL lisansı; haritada "© OpenStreetMap katkıcıları" atfı zorunlu ve ekli).
- **Sorgu:** `shop=supermarket|convenience|wholesale|greengrocer|department_store`, yarıçap 200 m – 10 km.
- **Eşleştirme:** `brand` → `name` sırasıyla, Türkçe karakter sadeleştirmeli, tam kelime eşleşmesi
  ("BİM", "Bim", "BIM Birleşik Mağazalar", "A-101", "Şok Market", "Migros Jet"…).
- **Önbellek:** Aynı ~110 m × 500 m'lik bölge için 24 saat (`MEALBIRD_PLACES_CACHE_HOURS`).
- **Uç noktalar:** `GET /api/places/nearby?lat=&lon=&radius_m=&only_chains=`, ev konumu: `PATCH /api/household`.
- **Optimizasyonla bağlantı:** `POST /api/shopping/optimize` içinde `"nearby_only": true`.
- **Bilinen sınır:** OSM'de bazı şubeler eksik/yanlış etiketli olabilir; kullanıcılar OSM'de düzeltebilir.
  Geliştirme ortamımızdan genel Overpass sunucusuna bağlantı kurulamadı (bağlantı sunucu tarafında kesiliyor);
  bu yüzden özellik sahte Overpass yanıtlarıyla test edildi. Gerçek ortamda ilk iş canlı doğrulama yapılmalı.
