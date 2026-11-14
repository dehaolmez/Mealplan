# Meall'ı GitHub Codespaces'te çalıştırma (sunucusuz, telefondan erişim)

Codespace, GitHub'ın sizin hesabınızda açtığı geçici bir bulut bilgisayardır. Bu depo açılınca Meall kendiliğinden
kurulur ve başlar; size `https://<ad>-8080.app.github.dev` biçiminde bir adres verir.

## Açmak (ilk sefer 3–5 dk)

1. github.com'da depoyu açın → yeşil **Code** düğmesi → **Codespaces** sekmesi → **Create codespace on …**
   (PR birleştirilmediyse önce dal seçiciden `ccr-653fe998-ngbtix` dalını seçin).
2. Kurulum bitince alttaki **Ports** (Bağlantı noktaları) sekmesinde **Meall (8080)** satırı çıkar.
   Adresin yanındaki 🌐 simgesine basın; uygulama açılır. Bu adresi kopyalayın.
3. Telefonda, **GitHub'a giriş yapmış** tarayıcıda bu adresi açın. İsterseniz menüden "Ana ekrana ekle".

> Aileden birinin GitHub girişi olmadan açabilmesi için: Ports sekmesinde 8080'e sağ tık → **Port Visibility → Public**.
> Bu durumda adresi bilen herkes açabilir; yalnız test için kullanın.

## Ports sekmesinde "Çalışan İşlem" boşsa

Meall başlamamış demektir. **Terminal** sekmesine şunu yazın:

```bash
bash .devcontainer/start.sh && sleep 6 && tail -20 ~/.meall/server.log
```

## Bilmeniz gerekenler

- Kişisel GitHub hesaplarında aylık ücretsiz kota vardır (2 çekirdekli makinede yaklaşık 60 saat).
- 30 dakika kullanılmazsa Codespace uyur; github.com/codespaces sayfasından tekrar başlatınca Meall da başlar.
- Veriler Codespace silinene kadar kalır (`~/.meall/meall.db`).
- **Fiş okuma / yapay zekâ tarifleri** için: GitHub → Settings → Codespaces → **Secrets** → `MEALBIRD_GEMINI_API_KEY`
  ekleyin ve bu depoya izin verin (sonra Codespace'i yeniden başlatın). Eklemezseniz bu iki özellik kapalı kalır.
- Kalıcı, her zaman açık bir adres için `docs/DEPLOY.md` (Render + Neon) kullanılır.
