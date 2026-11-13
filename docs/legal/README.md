# Hukuki metinler (TASLAK)

Uygulamada gösterilen metinlerin kaynağı: `backend/app/legal/*.md` (uygulama içinde `/api/legal/{slug}` ile sunulur).

| Metin | Dosya | Uygulamada |
|---|---|---|
| Aydınlatma Metni | `backend/app/legal/aydinlatma-metni.md` | Kayıt ekranı, Profil › Gizlilik |
| Açık Rıza Metni | `backend/app/legal/acik-riza-metni.md` | Kayıt ekranı (isteğe bağlı izinler), Profil › Gizlilik |
| Kullanım Koşulları | `backend/app/legal/kullanim-kosullari.md` | Kayıt ekranı |
| Çerez ve Yerel Depolama | `backend/app/legal/cerez-ve-yerel-depolama.md` | Giriş ekranı, Profil |

Metni değiştirince `backend/app/legal/__init__.py` içindeki `LEGAL_VERSION`'ı güncelleyin; kullanıcılardan
bir sonraki açılışta yeniden onay istenir. Her onay/geri çekme, sürümüyle birlikte `consent_records`
tablosunda silinmeden saklanır.

## Doldurulması gereken alanlar

`[AD SOYAD / ŞİRKET ÜNVANI]`, `[AÇIK ADRES]`, `[MERSİS NO veya VKN]`, `[KVKK BAŞVURU E-POSTASI]`, `[KEP ADRESİ]`,
`[DESTEK E-POSTASI]`. Sağlayıcılar (Render + Neon / Frankfurt, Gmail, Google Gemini, TÜBİTAK Market Fiyatı,
OpenStreetMap) v0.4'te metinlere işlendi.

## Hukukçunun özellikle bakması önerilen noktalar

1. **Boy/kilo/hedef bilgisinin "sağlık verisi" sayılması** — taslak ihtiyatlı davranıp özel nitelikli kabul etti
   ve açık rızaya bağladı (KVKK m.6/3). Kurum'un Şubat 2025 tarihli özel nitelikli veri rehberi ile kontrol edilmeli.
2. **Yurt dışı aktarım (m.9, 7499 s. Kanunla değişik):** v0.4'te ücretsiz barındırma (Render + Neon, Frankfurt)
   seçildiği için **tüm veriler** yurt dışında tutuluyor; ayrıca Gemini, Gmail, Google ile giriş ve OpenStreetMap
   servisleri. Açık rıza artık yalnız arızi aktarımlar için; düzenli aktarımlar için standart sözleşme + imzadan
   itibaren 5 iş günü içinde Kurum'a bildirim gerekir. Overpass/Nominatim'i Türkiye'deki kendi sunucumuzda
   çalıştırmak bu aktarımı ortadan kaldırır (yazılımlar ücretsiz, açık kaynak).
3. **18 yaş altı bireyler:** Veli/vasi beyanı yeterli mi?
4. **VERBİS kayıt yükümlülüğü:** Çalışan sayısı/ciro eşikleri ve ana faaliyetin özel nitelikli veri işleme olup
   olmadığına göre değerlendirilmeli.
5. **Saklama süreleri:** Rıza kayıtları için 10 yıl, 5651 kapsamındaki kayıtlar.
6. **Ticari ileti:** 6563 s. Kanun ve İYS kaydı; doğrulama e-postalarında reklam olmaması
   (Kurul'un 2025/1072 s. ilke kararı SMS içindi, aynı yaklaşım e-postaya da uygulandı).

## Yararlanılan kaynaklar

- [KVKK — Kişisel Verilerin Yurt Dışına Aktarılması Rehberi](https://www.kvkk.gov.tr/Icerik/8142/Kisisel-Verilerin-Yurt-Disina-Aktarilmasi-Rehberi)
- [KVKK — Kanunda yapılan değişiklikler (7499 s. Kanun)](https://kvkk.gov.tr/SharedFolderServer/CMSFiles/4eba766b-7425-4cd4-97f5-cb09c4cf4ef9.pdf)
- [Mondaq — KVKK Yurt Dışına Veri Aktarımı Rehberi (2026)](https://www.mondaq.com/turkey/privacy-protection/1740066/kvkk-yurt-d%C4%B1%C5%9F%C4%B1na-veri-aktar%C4%B1m%C4%B1-rehberi-2026-g%C3%BCncel-d%C3%BCzenlemeler)
- [Erdem & Erdem — 2025/1072 s. ilke kararı (SMS doğrulama)](https://www.erdem-erdem.av.tr/bilgi-bankasi/kisisel-verileri-koruma-kurulunun-urun-ve-hizmet-sunumlarinda-sms-ile-dogrulama-kodu-gonderilmesi-hakkinda-ilke-karari-yayimlandi)
- [Medikal Akademi — Sağlık bilgileri ve güncel Kurul kararları](https://www.medikalakademi.com.tr/?p=218216)
