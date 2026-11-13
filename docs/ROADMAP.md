# Mealbird — Yol Haritası, Dinamik Kullanım ve İhtiyaç Listesi

Son güncelleme: 13 Kasım 2026 (v0.3)

Bu belge üç şeyi anlatır:
1. MVP'den sonraki adımların **sabit kod yerine dinamik veriyle** nasıl çalışacağı,
2. bu adımlar için **senden (proje sahibinden) gerekenler**,
3. Türkiye'deki büyük market zincirleri ve **konum tabanlı yakın market** özelliği.

---

## 0. Kararlar ve durum (v0.3 — 13 Kasım 2026)

| Konu | Karar | Durum |
|---|---|---|
| Fiyat kaynağı | Kurumsal erişim yok. Market Fiyatı'nın belgelenmemiş API'si denendi (bkz. §0.1) | ⏸ Proje sahibinin kararını bekliyor |
| Pilot bölge | **Ankara / Etimesgut** | ✅ Harita varsayılan merkezi, adres araması, test fiyatları |
| Test fiyatları | Gerçek veri gelene kadar üretilmiş, **"test" etiketli** fiyatlar | ✅ `backend/scripts/generate_test_prices.py` |
| Platform | **PWA** (web uygulaması, telefona kurulabilir, çevrimdışı açılır) | ✅ Manifest + servis çalışanı |
| APK | PWA'nın aynısı, alan adı + HTTPS ile yayına alındıktan sonra paketlenir | ⏭ Barındırmadan sonra (§0.2) |
| Giriş | **E-posta + Google** | ✅ (Google için istemci kimliği gerekli) |
| Barındırma | **Türkiye** | ⏭ Sağlayıcı seçimi bekliyor |
| KVKK | Güncel mevzuata göre taslak metinler + rıza kayıtları + veri dökümü/silme | ✅ Taslak; hukukçu incelemesi bekliyor (`docs/legal/README.md`) |
| Harita servisleri | **Ücretsiz** (OSM Overpass, Nominatim, karolar); üretimde kendi sunucumuz önerilir | ✅ |
| Konum hassasiyeti | 110 m → **~11 m** (4 ondalık), ayarlanabilir (`MEALBIRD_LOCATION_PRECISION`) | ✅ |
| Yapay zekâ | Gemini değerlendirmesi sonraya; sağlayıcı soyutlaması o zaman eklenecek | ⏭ |
| Veritabanı | Alembic migrasyonları, açılışta otomatik güncelleme, eski SQLite otomatik yedeklenir | ✅ |

### 0.1 Market Fiyatı API'si — ne denendi, ne oldu?

- `https://api.marketfiyati.org.tr/api/v2` **çalışıyor**. `POST /api/v2/search` (anahtar kelime + enlem/boylam +
  km cinsinden mesafe) ürünleri, şube bazlı fiyatlarıyla döndürüyor. Denemede "süt" araması 474 ürün getirdi.
  Topluluk projeleri ayrıca `/api/v2/nearest` (yakın şubeler) ve `/api/v2/searchByCategories` kullanıyor.
- API, standart bir istemciye 404 döndürüyor; yanıt yalnız tarayıcı kimliğiyle (User-Agent) geliyor.
  **Belgelenmiş, herkese açık bir API değil.**
- Geliştirme ortamındaki güvenlik denetimi bu nedenle Etimesgut için yapılacak ikinci denemeyi
  **"yetkisiz erişim"** olarak değerlendirip durdurdu. Bu yüzden entegrasyon kodu **yazılmadı**.
- Değerlendirme:
  - **Webhook:** Sitenin webhook'u yok; olsa olsa günde bir kez sorgulama (polling) yapılabilir. Bu da aynı izin sorusunu doğurur.
  - **Yapay zekâ anahtarı:** Erişim/izin sorununu çözmez. Yapay zekâ ancak gelen ürün adlarını katalogla
    eşleştirmede işe yarar.
  - **Market sitelerinden çekmek:** Çoğu sitenin kullanım koşulları otomatik veri toplamayı yasaklar;
    her site ayrı bakım ister. Önerilmez.
- **Önerilen yol (kurumsal başvuru gerektirmez):**
  1. TÜBİTAK BİLGEM / Market Fiyatı iletişim adresine **bireysel bir e-posta** ile kâr amacı gütmeyen
     kullanım için izin istemek.
  2. Bu arada **kullanıcı katkılı fiyat**: fiş fotoğrafı → yapay zekâ (ör. Gemini) ile ürün, fiyat ve tarih okuma →
     hem envantere hem fiyat tablosuna yazma. Hukuken temiz, yereldir ve Gemini anahtarının en verimli kullanımı olur.
  3. CSV içe aktarma (hazır) her durumda yedek yol olarak kalır.

### 0.2 PWA nedir, APK ne zaman?

**PWA (Progressive Web App):** Tarayıcıda açılan ama telefona **uygulama gibi kurulabilen** web uygulamasıdır.
- Android'de Chrome'un "Uygulamayı yükle" düğmesiyle, iPhone'da Safari › Paylaş › "Ana Ekrana Ekle" ile kurulur.
- Kurulunca kendi simgesiyle tam ekran açılır ve internet yokken de son görülen sayfalar açılır.
- Ayrı bir Android/iOS kodu yazmak gerekmez; güncellemeler mağaza onayı beklemeden herkese anında ulaşır.

**APK:** Aynı PWA, Google'ın "Trusted Web Activity" yöntemiyle (Bubblewrap aracı) Play Store'a konabilen bir
APK/AAB paketine sarılır. Bunun için uygulamanın **kendi alan adında HTTPS ile yayında** olması gerekir
(alan adı doğrulaması `assetlinks.json` ile yapılır). Bu yüzden APK **barındırmadan sonra** yapılmalı.
Kod tarafında ek bir iş yoktur; birkaç saatlik paketleme ve Play Console kaydı (bir kerelik 25 USD) gerekir.

---

## 1. v0.2'de eklenenler

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
- **Gizlilik:** Konum dış servise **~11 m'ye yuvarlanarak** gönderilir; ev konumu da aynı hassasiyetle saklanır (v0.3'te 110 m'den düşürüldü).
- **Dinamikleştirme:**
  1. **Kendi Overpass sunucumuz** (veya ücretli sağlayıcı): genel Overpass sunucuları hız sınırlıdır; üretimde
     Türkiye OSM özeti (Geofabrik, ~1 GB) ile kendi Overpass/PostGIS kurulumumuz önerilir. Uç noktalar zaten
     `MEALBIRD_OVERPASS_ENDPOINTS` ile değiştirilebilir.
  2. **Gece toplu güncelleme:** İl/ilçe bazında tüm şubeleri önceden çekip `places` tablosunda tutmak (istek anında dış servise gitmeden).
  3. **Mesafe + fiyat birlikte optimizasyon:** "200 TL tasarruf için 2 km daha yürür müsün?" — yol maliyeti/zaman ağırlığı kullanıcı ayarı olur.
  4. **Rota:** Birden çok marketli alışverişte sıralı rota (OSRM / GraphHopper).
  5. Açık/kapalı durumu: OSM `opening_hours` alanı ayrıştırılıp "şu an açık" filtresi.

### 2.3 Kimlik doğrulama ve çok haneli yapı — ✅ v0.3

- E-posta + şifre (scrypt özeti), Google ile giriş (Google ID token doğrulaması), HttpOnly oturum çerezi
  (APK/mobil istemciler için `Authorization: Bearer` da desteklenir).
- Şifre sıfırlama ve e-posta doğrulama bağlantıları (SMTP yoksa sunucu günlüğüne yazılır), giriş denemesi sınırı,
  şifre değişince diğer cihazlardaki oturumların kapanması.
- Her hesabın kendi hanesi; **davet koduyla** aile üyeleri aynı haneye katılır.
- Sırada: paylaşılan listede anlık senkron (SSE/WebSocket), Apple ile giriş (iOS'ta gerekirse).

### 2.4 Veritabanı ve dağıtım

- ✅ **Alembic** migrasyonları; açılışta otomatik `upgrade`. Migrasyon kaydı olmayan eski SQLite dosyası
  `mealbird.db.bak-ZAMAN` olarak yedeklenip yenisi oluşturulur. Elle bir şey yapmak gerekmez.
- Sırada: PostgreSQL (+ PostGIS), Docker Compose, GitHub Actions'ta testler.
- Barındırma: **Türkiye** (karar verildi). Kendi Overpass/Nominatim sunucumuz da aynı yerde çalıştırılabilir
  (ücretsiz yazılım; Türkiye OSM verisi için yaklaşık 4–8 GB RAM ve 50 GB disk gerekir).

### 2.5 PWA ve bildirimler — ✅ temel PWA v0.3

- ✅ Manifest, simgeler, servis çalışanı. Uygulama kabuğu ve son görülen veriler çevrimdışı açılır; çıkışta
  önbellekteki kişisel veriler silinir.
- Sırada: **Web Push** ile SKT bildirimleri (uygulama kapalıyken de). VAPID anahtarı gerekir, ücretsizdir.

### 2.6 Yapay zekâ genişletmeleri

- Fiş fotoğrafından envantere ekleme (görsel → ürün + miktar + tarih).
- Fiyat kaynaklarından gelen ürün adlarını katalogla eşleştirme önerisi.
- Haftalık plan üretimi (bütçe + besin hedefi + israf önleme birlikte).

### 2.7 Kiler (oda sıcaklığı) saklama alanı

Kuru gıdalar için üçüncü saklama alanı; raf ömrü kuralları zaten malzeme bazında olduğundan küçük bir değişiklik.

---

## 3. Senden gerekenler (v0.3 güncel)

| # | Ne | Neden | Not |
|---|---|---|---|
| 1 | **Market Fiyatı API'si kararı** | Gerçek fiyat | Seçenekler §0.1'de. Bireysel izin e-postasını gönderebilir veya hazır bir taslak isteyebilirsin |
| 2 | **Google OAuth istemci kimliği** (ücretsiz) | Google ile giriş | Google Cloud Console › API'ler ve Hizmetler › Kimlik bilgileri › OAuth istemci kimliği (Web uygulaması); "Yetkili JavaScript kaynakları"na sitenin adresi. Kimlik `MEALBIRD_GOOGLE_CLIENT_ID`'ye yazılır (gizli değildir) |
| 3 | **Barındırma sağlayıcısı + alan adı (Türkiye)** | Yayına çıkış, APK, Google girişi, e-posta | Küçük bir sanal sunucu yeterli |
| 4 | **E-posta gönderim hesabı (SMTP)** | Doğrulama ve şifre sıfırlama | Alan adınla kurulacak bir e-posta hizmeti |
| 5 | **KVKK metinlerindeki köşeli parantezli alanlar** ve hukukçu incelemesi | Yayına çıkmadan önce | `docs/legal/README.md` |
| 6 | Gemini API anahtarı (sonra) | Fiş fotoğrafı okuma, öneriler | Sohbete yapıştırma; sunucuya ortam değişkeni olarak eklenir |
| 7 | Marka/tasarım onayı | Simge ve ad | Yeni simge `frontend/public/icons/` altında |

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
- **Önbellek:** Aynı ~11 m'lik nokta ve 500 m'lik yarıçap basamağı için 24 saat (`MEALBIRD_PLACES_CACHE_HOURS`).
- **Uç noktalar:** `GET /api/places/nearby?lat=&lon=&radius_m=&only_chains=`, ev konumu: `PATCH /api/household`.
- **Optimizasyonla bağlantı:** `POST /api/shopping/optimize` içinde `"nearby_only": true`.
- **Bilinen sınır:** OSM'de bazı şubeler eksik/yanlış etiketli olabilir; kullanıcılar OSM'de düzeltebilir.
  Geliştirme ortamımızdan genel Overpass sunucusuna bağlantı kurulamadı (bağlantı sunucu tarafında kesiliyor);
  bu yüzden özellik sahte Overpass yanıtlarıyla test edildi. Gerçek ortamda ilk iş canlı doğrulama yapılmalı.
