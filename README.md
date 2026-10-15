# KartRadarı MVP

Bu proje KartRadarı.com için hazırlanmış ilk Next.js landing page / MVP taslağıdır.

## Kurulum

Bilgisayarında Node.js kurulu olmalı.

Terminalde:

```bash
npm install
npm run dev
```

Sonra tarayıcıdan şunu aç:

```bash
http://localhost:3000
```

## İçerik

- Ana sayfa
- Kart arama demo alanı
- Trend kartlar
- Hype/radar score mockup
- Sealed yatırım paneli
- Koleksiyon portföy paneli

## Sonraki aşama

Bu proje henüz demo verilerle çalışıyor. Gerçek ürün haline getirmek için sırayla:

1. Supabase database
2. Kullanıcı üyeliği
3. Kart database
4. Admin panel
5. Fiyat geçmişi
6. Koleksiyon portföyü
7. Marketplace
8. AI kart tarama

eklenmeli.

## Günlük fiyat kaydı ve canlı panel (yeni)

Bu repoda Next.js taslağından bağımsız çalışan ilk gerçek veri katmanı var:

- `pipeline/portfolio.json`: takip edilen kartlar (şimdilik örnek portföy). Kart eklemek için bir satırı kopyalayıp oyun, set, ad, numara, adet, alış fiyatı ve tarihini değiştir.
- `pipeline/fetch_prices.py`: kartları TCGplayer kataloğunda (TCGCSV aracılığıyla) bulur, güncel piyasa fiyatını ve USD karşısında TRY, EUR, GBP, JPY, CNY kurlarını çeker.
- `.github/workflows/daily-prices.yml`: bu betiği her gün 09:23'te (Türkiye saati) çalıştırır ve sonucu `docs/data/` klasörüne kaydeder. Elle çalıştırmak için: Actions → Günlük fiyat kaydı → Run workflow.
- `docs/index.html`: GitHub Pages ile yayınlanan panel. Ana fiyat USD, ikinci para birimi seçilebilir; portföy değeri grafiği, kart bazında fiyat geçmişi, kur etkisi ve grading hesaplayıcısı içerir.

GitHub Pages'i açmak için: Settings → Pages → Source: "Deploy from a branch" → Branch: `main`, klasör: `/docs` → Save.

Veri kaynakları: TCGplayer piyasa fiyatları (tcgcsv.com), Avrupa Merkez Bankası referans kurları (frankfurter). Fiyat geçmişi, görevin ilk çalıştığı günden itibaren birikir.
