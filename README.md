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
