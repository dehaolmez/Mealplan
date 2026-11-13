# Mealbird'ü ücretsiz yayına alma (GitHub + Render + Neon)

Sunucu satın almadan, GitHub deposundan otomatik yayın. Toplam tıklama süresi ~15 dakika.

## Neden yalnız GitHub yetmiyor?

GitHub Pages yalnız **statik** dosya sunar (HTML/JS). Mealbird'ün sunucu tarafı (Python API + veritabanı)
çalışan bir süreç ister. Bu yüzden:

| Parça | Nerede | Ücret | Not |
|---|---|---|---|
| Kod, testler (CI) | **GitHub** | Ücretsiz | Her push'ta testler + Docker derlemesi (`.github/workflows/ci.yml`) |
| Uygulama (API + arayüz tek adres) | **Render** — GitHub'a bağlı, `main`'e her push'ta otomatik yayın | Ücretsiz | 15 dk istek gelmezse uyur; ilk açılış ~1 dk sürer |
| Veritabanı (PostgreSQL) | **Neon** | Ücretsiz | 1 GB depolama; boşta uyur, ilk sorgu birkaç saniye |
| E-posta | **Gmail** (uygulama şifresi) | Ücretsiz | Günde ~500 alıcı |
| Fiyatlar | TÜBİTAK Market Fiyatı | Ücretsiz | Uygulama kendisi çeker |
| Harita | OpenStreetMap | Ücretsiz | |

> ⚖️ **KVKK notu:** Render ve Neon'un ücretsiz sunucuları Türkiye'de değil (Frankfurt seçilir). Bu, verilerin
> yurt dışına aktarılması demektir; Aydınlatma Metni buna göre güncellendi. Türkiye'de barındırma ücretsiz
> değildir; kullanıcı sayısı artınca yerli bir sağlayıcıya taşımak kod değişikliği gerektirmez (yalnız
> `MEALBIRD_DATABASE_URL` değişir).

## Adım 1 — Kodu `main` dalına almak

Render `main` dalını yayınlar. Çalışma dalındaki (`ccr-653fe998-ngbtix`) değişiklikler için bir Pull Request açıp
birleştirin (isterseniz PR'ı ben açarım).

## Adım 2 — Neon veritabanı (3 dk)

1. https://neon.com → GitHub hesabınızla kaydolun (kredi kartı istemez).
2. **New Project** → ad: `mealbird`, Postgres sürümü: 16+, bölge: **AWS Europe Central (Frankfurt)**.
3. Proje panelinde **Connect** → bağlantı adresini kopyalayın: `postgresql://...neon.tech/neondb?sslmode=require`

Tabloları uygulama ilk açılışta kendisi kurar; elle bir şey yapmayın.

## Adım 3 — Render servisi (5 dk)

1. https://render.com → **GitHub ile kaydol** → depoya erişim izni verin (`dehaolmez/mealplan`).
2. **New → Blueprint** → depoyu seçin. Render `render.yaml` dosyasını okuyup servisi hazırlar.
3. İstenen değerleri girin:

| Değişken | Değer |
|---|---|
| `MEALBIRD_DATABASE_URL` | Neon'dan kopyaladığınız adres |
| `MEALBIRD_PUBLIC_BASE_URL` | Render'ın verdiği adres, ör. `https://mealbird.onrender.com` (ilk kurulumdan sonra öğrenilir; sonradan girilebilir) |
| `MEALBIRD_GEMINI_API_KEY` | Gemini anahtarınız (fiş okuma ve yapay zekâ önerileri) |
| `MEALBIRD_GOOGLE_CLIENT_ID` | Adım 5 (isteğe bağlı) |
| `MEALBIRD_ADMIN_EMAIL` / `MEALBIRD_ADMIN_PASSWORD` | Yönetici hesabınız (Profil'de "🛠️ Yönetim" bölümü açılır) |
| `MEALBIRD_SMTP_USER` / `MEALBIRD_SMTP_PASSWORD` / `MEALBIRD_SMTP_FROM` | Adım 4 |

`MEALBIRD_SECRET_KEY` Render tarafından otomatik üretilir. **Apply** deyin; ilk derleme ~5 dk sürer.

Sonrasında `main`'e her push otomatik yayınlanır; GitHub'daki CI testleri kırmızıysa birleştirmeyin.

## Adım 4 — Gmail ile e-posta (3 dk)

Doğrulama ve şifre sıfırlama e-postaları için:

1. Google hesabınızda **2 adımlı doğrulama** açık olmalı.
2. https://myaccount.google.com/apppasswords → uygulama adı "Mealbird" → **16 karakterlik şifreyi** kopyalayın.
3. Render'da: `MEALBIRD_SMTP_USER` = Gmail adresiniz, `MEALBIRD_SMTP_PASSWORD` = bu şifre,
   `MEALBIRD_SMTP_FROM` = `Mealbird <adresiniz@gmail.com>`.

Bu adımı atlarsanız uygulama çalışır; e-postalar yalnız sunucu günlüğüne yazılır (şifre sıfırlama çalışmaz).
Daha sonra alan adınızla profesyonel bir adrese geçmek yalnız bu üç değeri değiştirmektir.

## Adım 5 — Google ile giriş (isteğe bağlı, 4 dk)

1. https://console.cloud.google.com → yeni proje "Mealbird".
2. **API'ler ve Hizmetler → OAuth izin ekranı**: Harici, uygulama adı Mealbird, destek e-postanız.
3. **Kimlik bilgileri → Kimlik bilgisi oluştur → OAuth istemci kimliği → Web uygulaması**.
   "Yetkili JavaScript kaynakları"na Render adresinizi ekleyin (ör. `https://mealbird.onrender.com`).
4. Oluşan **istemci kimliğini** (`...apps.googleusercontent.com`) Render'da `MEALBIRD_GOOGLE_CLIENT_ID`'ye girin.
   Bu kimlik gizli değildir; istemci gizli anahtarına (client secret) gerek yoktur.

## Adım 6 — Telefona kurmak

Render adresini telefonda açın: Android'de Chrome menüsü → **Uygulamayı yükle**; iPhone'da Safari → Paylaş →
**Ana Ekrana Ekle**.

## Sorun giderme

| Belirti | Neden / çözüm |
|---|---|
| İlk açılış 30–60 sn sürüyor | Render ücretsiz servis uyuyordu; normal |
| "Market Fiyatı'na ulaşılamadı" | Kaynak geçici olarak yanıt vermiyor; önbellekteki fiyatlar kullanılır |
| "Gemini şu an yanıt vermiyor" | Model yoğun; uygulama sırayla 3 model dener, biraz sonra tekrar deneyin |
| Google düğmesi görünmüyor | `MEALBIRD_GOOGLE_CLIENT_ID` boş veya adres "Yetkili JavaScript kaynakları"nda yok |
| Yakındaki marketler boş | OpenStreetMap Overpass sunucusu yoğun; birkaç dakika sonra tekrar deneyin |

## Yerelde Docker ile çalıştırma

```bash
docker build -t mealbird .
docker run -p 8000:8000 -e MEALBIRD_COOKIE_SECURE=false mealbird   # http://localhost:8000
```
