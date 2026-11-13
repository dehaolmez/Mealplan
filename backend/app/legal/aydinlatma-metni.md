# Kişisel Verilerin İşlenmesine İlişkin Aydınlatma Metni

**Sürüm:** 2026-11-13.2 · **TASLAK — hukuki incelemeden geçirilmelidir**

Bu metin, 6698 sayılı Kişisel Verilerin Korunması Kanunu'nun ("KVKK") 10. maddesi ve Aydınlatma Yükümlülüğünün
Yerine Getirilmesinde Uyulacak Usul ve Esaslar Hakkında Tebliğ uyarınca, Mealbird uygulamasını ("Uygulama")
kullanırken kişisel verilerinizin nasıl işlendiği konusunda sizi bilgilendirmek amacıyla hazırlanmıştır.
Bu metin bir **bilgilendirmedir**; açık rızanız ayrıca ve ayrı bir metinle istenir.

## 1. Veri sorumlusu

| | |
|---|---|
| Veri sorumlusu | **[AD SOYAD / ŞİRKET ÜNVANI]** |
| Adres | **[AÇIK ADRES]** |
| MERSİS / Vergi no | **[MERSİS NO veya VKN — gerçek kişi ise boş bırakılabilir]** |
| İletişim | **[KVKK BAŞVURU E-POSTASI]** · KEP: **[KEP ADRESİ, varsa]** |

## 2. İşlenen kişisel veriler

| Kategori | Veriler | Ne zaman |
|---|---|---|
| Kimlik / iletişim | E-posta adresi, görünen ad | Hesap oluştururken |
| Hesap güvenliği | Şifrenin geri döndürülemez özeti (düz şifre saklanmaz), Google hesap kimliği (Google ile girişte), oturum bilgisi | Giriş yaptığınızda |
| İşlem güvenliği | IP adresi, istek zamanı, hata kayıtları | Uygulamayı kullanırken |
| **Sağlık verisi (özel nitelikli)** | Hane bireylerinin doğum tarihi, cinsiyeti, boyu, kilosu, aktivite düzeyi, beslenme hedefi ve bunlardan hesaplanan kalori/makro ihtiyaçları | **Yalnızca açık rızanızla** |
| **Konum** | Kaydettiğiniz ev konumu (yaklaşık 11 metre hassasiyete yuvarlanarak); yakın market aramasında anlık konum | Ev konumu **yalnızca açık rızanızla** saklanır; anlık konum siz istediğinizde, tarayıcı izniyle kullanılır ve saklanmaz |
| Ev/alışveriş verileri | Buzdolabı/buzluk envanteri, son kullanma tarihleri, yemek planı, alışveriş listesi, market tercihleri | Uygulamayı kullanırken |
| Fiş fotoğrafı | Yüklediğiniz market fişinin görüntüsü (fişte market adı, tarih, ürünler, tutarlar ve varsa kartın son haneleri bulunabilir) | **Yalnızca yapay zekâ iznini verip fiş taradığınızda; sunucuda saklanmaz** |
| Onay kayıtları | Hangi metni, hangi sürümde, ne zaman onayladığınız / geri çektiğiniz | Her onay işleminde |
| Pazarlama | Ticari elektronik ileti onayı | **Yalnızca ayrıca onay verirseniz** |

Hane bireyleri arasında 18 yaşından küçükler varsa, bu bireylere ait verileri yalnızca velisi veya vasisi
olarak siz girebilirsiniz.

## 3. İşleme amaçları ve hukuki sebepler

| Amaç | Hukuki sebep (KVKK) |
|---|---|
| Hesabın oluşturulması, oturum açma, hizmetin sunulması (envanter, plan, liste, fiyat karşılaştırma) | m.5/2-c: sözleşmenin kurulması ve ifası |
| Hesap ve sistem güvenliği, kötüye kullanımın önlenmesi, hata ayıklama | m.5/2-f: meşru menfaat; m.5/2-ç: hukuki yükümlülük |
| Yasal yükümlülükler (ör. 5651 sayılı Kanun kapsamındaki kayıtlar, resmî makam talepleri) | m.5/2-ç: hukuki yükümlülük |
| Onay/geri çekme kayıtlarının ispatı | m.5/2-ç ve m.5/2-e: bir hakkın tesisi, kullanılması veya korunması |
| Kalori ve makro besin ihtiyacının hesaplanması, tarif önerilerinin buna göre sıralanması | **m.6/3: açık rıza** (sağlık verisi) |
| Ev konumunun saklanıp yakın marketlerin listelenmesi | **m.5/1: açık rıza** |
| Yapay zekâ destekli tarif önerisi ve fiş fotoğrafından envantere ekleme (isteğe bağlı) | **m.5/1: açık rıza** ve yurt dışı aktarım için m.9 (bkz. 4. bölüm) |
| Yakın marketlerdeki güncel fiyatların gösterilmesi | m.5/2-c: sözleşmenin ifası (konum kimliğinizle ilişkilendirilmeden, ~1 km'ye yuvarlanarak kullanılır) |
| Kampanya/bilgilendirme e-postaları | **Açık rıza** ve 6563 sayılı Kanun kapsamında ticari ileti onayı |

Sağlık verisi ve konum için rıza vermemeniz Uygulamanın temel özelliklerini (envanter, son kullanma tarihi
uyarıları, alışveriş listesi, fiyat karşılaştırma) kullanmanıza engel değildir; yalnızca ilgili özellik kapalı kalır.

## 4. Aktarım

| Alıcı | Aktarılan | Amaç | Konum |
|---|---|---|---|
| Barındırma: Render Services, Inc. (uygulama sunucusu) ve Neon (veritabanı) | Uygulamadaki tüm veriler | Altyapı | **Yurt dışı** (Frankfurt, Almanya bölgesi) |
| OpenStreetMap hizmetleri (Overpass, Nominatim, harita karoları) | Yaklaşık konum (~11 m'ye yuvarlanmış koordinat) veya yazdığınız adres; harita karoları için tarayıcınızın IP adresi | Yakın marketleri ve haritayı göstermek | **Yurt dışı** (Almanya/Birleşik Krallık) |
| Google LLC (yalnız Google ile girişi seçerseniz) | Google'ın size ait kimlik doğrulama bilgisi | Oturum açma | **Yurt dışı** |
| Google LLC — Gemini API (yalnız yapay zekâ iznini verirseniz) | Fiş fotoğrafı; envanterdeki ürün adları, kalan gün sayıları, aday tarif listesi. **Kimlik, e-posta, boy/kilo gönderilmez.** | Fiş okuma, tarif önerisi | **Yurt dışı** |
| TÜBİTAK BİLGEM — Market Fiyatı (marketfiyati.org.tr) | Yaklaşık konum (~1 km'ye yuvarlanmış koordinat) ve aranan ürün adları; kimlik bilgisi gönderilmez | Yakın şubelerdeki güncel fiyatları almak | Türkiye |
| E-posta gönderim hizmeti (Google LLC — Gmail) | E-posta adresiniz | Doğrulama ve şifre sıfırlama | Yurt dışı |
| Yetkili kamu kurum ve kuruluşları | Talep edilen veriler | Hukuki yükümlülük | Türkiye |

Yurt dışına aktarımlar KVKK m.9 uyarınca; yeterlilik kararı bulunan ülkelere, bulunmuyorsa Kurulca ilan edilen
**standart sözleşmeler** gibi uygun güvencelerle (sözleşmenin imzasından itibaren 5 iş günü içinde Kurum'a
bildirilerek) yapılır. Bu güvencelerin sağlanamadığı arızi durumlarda açık rızanıza başvurulur.
Uygulama verileri tarayıcınızda veya sunucumuzda başka hiçbir üçüncü kişiyle paylaşılmaz ve satılmaz.

## 5. Toplama yöntemi

Veriler; Uygulamadaki formlara girdiğiniz bilgilerle, Google ile girişte Google'dan, konum için tarayıcınızın
konum izniyle veya haritaya dokunarak seçtiğiniz noktadan ve kullanım sırasında sunucularımızda oluşan kayıtlarla
**elektronik ortamda, otomatik ve kısmen otomatik yollarla** toplanır.

## 6. Saklama süreleri

| Veri | Süre |
|---|---|
| Hesap, hane ve kullanım verileri | Hesabınız silinene kadar; hesap silindiğinde en geç 30 gün içinde yedeklerden de silinir |
| Sağlık verisi / ev konumu | Rızanızı geri çektiğiniz anda silinir |
| Onay kayıtları | Hesap silindikten sonra kimliğinizle ilişkilendirilmeden (anahtarlı özet ile) **10 yıl** (genel zamanaşımı) |
| Güvenlik/erişim kayıtları | İlgili mevzuattaki süre kadar (ör. 5651 sayılı Kanun ve ikincil düzenlemeleri) |

Süresi dolan veriler Kişisel Verilerin Silinmesi, Yok Edilmesi veya Anonim Hale Getirilmesi Hakkında Yönetmelik
uyarınca silinir, yok edilir veya anonim hale getirilir.

## 7. Haklarınız (KVKK m.11)

Veri sorumlusuna başvurarak; kişisel verilerinizin işlenip işlenmediğini öğrenme, işlenmişse bilgi talep etme,
işleme amacını ve amacına uygun kullanılıp kullanılmadığını öğrenme, yurt içinde/yurt dışında aktarıldığı
üçüncü kişileri bilme, eksik/yanlış işlenmişse düzeltilmesini, KVKK m.7 çerçevesinde silinmesini veya yok
edilmesini ve bu işlemlerin aktarılan üçüncü kişilere bildirilmesini isteme, münhasıran otomatik sistemlerle
analiz edilmesi sonucu aleyhinize bir sonuç çıkmasına itiraz etme ve kanuna aykırı işleme sebebiyle zarara
uğramanız hâlinde zararın giderilmesini talep etme haklarına sahipsiniz.

**Uygulama içinden:** Profil › Gizlilik bölümünden verilerinizin dökümünü (JSON) indirebilir, rızalarınızı
geri çekebilir ve hesabınızı silebilirsiniz.

**Başvuru:** Veri Sorumlusuna Başvuru Usul ve Esasları Hakkında Tebliğ uyarınca, kimliğinizi tespit edici bilgilerle
**[KVKK BAŞVURU E-POSTASI]** adresine (kayıtlı e-posta adresinizden), KEP ile veya yazılı olarak **[ADRES]**
adresine başvurabilirsiniz. Başvurular en geç **30 gün** içinde ücretsiz sonuçlandırılır. Başvurunuzun
reddedilmesi, cevabı yetersiz bulmanız veya süresinde cevap verilmemesi hâlinde Kişisel Verileri Koruma
Kurulu'na şikâyette bulunabilirsiniz.
