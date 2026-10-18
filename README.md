# Holotique

TCG koleksiyonu için fiyat takibi ve portföy uygulaması — https://holotique.com

Canlı site `docs/` klasöründen GitHub Pages ile yayınlanır (aşağıda). Kökteki Next.js dosyaları ilk taslaktır, yayında kullanılmıyor.

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

## Canlı uygulama (docs/)

https://beriharavon-svg.github.io/kartradari/ adresinde yayınlanan uygulama:

- Supabase ile üyelik (e-posta + şifre). Her kullanıcı yalnızca kendi portföyünü görür; alış fiyatları ve PSA numaraları satır düzeyinde güvenlik (RLS) ile korunur.
- Excel/CSV'den toplu içe aktarma ya da tek tek kart ekleme.
- Ham, PSA 9 ve PSA 10 fiyatları, fiyat güven düzeyi, portföy değeri grafiği, kur etkisi ve grading hesaplayıcısı.

Parçalar:

- `supabase/schema.sql`: veritabanı tabloları ve güvenlik kuralları. Supabase → SQL Editor'da bir kez çalıştırılır.
- `pipeline/sync_psa.py` + `.github/workflows/psa-sync.yml`: iki saatte bir çalışır. Yeni kartları PokemonPriceTracker kataloğunda eşleştirir, ham/PSA fiyatlarını günde bir kez kaydeder, kurları günceller. Günlük kredi bütçesini (`PPT_DAILY_BUDGET`, varsayılan 95) aşmaz.
- Gerekli GitHub Secrets: `SUPABASE_SECRET_KEY`, `POKEMONPRICETRACKER_API_KEY`.

Veri kaynakları: PokemonPriceTracker (TCGplayer ham fiyatları ve eBay PSA satışları), Avrupa Merkez Bankası kurları (Frankfurter). Şu an yalnızca Pokemon kartları fiyatlanıyor.

Eski örnek panelin TCGCSV görevi (`pipeline/fetch_prices.py`) artık yalnızca elle çalıştırılıyor.

## Herkese açık kart arama (docs/ara.html)

Giriş gerektirmeyen arama sayfası: https://beriharavon-svg.github.io/kartradari/ara.html

- `pipeline/sync_catalog.py` + `.github/workflows/catalog-sync.yml`: her gece TCGCSV'den Pokemon (İngilizce/Japonca), One Piece ve Lorcana kataloğunu ve TCGplayer piyasa fiyatlarını `catalog` tablosuna yükler.
- `supabase/migrations/003_catalog.sql`: katalog tablosu ve herkese açık `search_catalog`, `card_history`, `latest_fx` fonksiyonları. Tabloya doğrudan erişim yoktur; arama en fazla 60 sonuç döndürür.
- Portföylerde takip edilen kartlar için PSA 10/9 fiyatları ve fiyat geçmişi de gösterilir. "Portföyüme ekle" kartı bilgileri doldurulmuş olarak portföy sayfasına gönderir.
