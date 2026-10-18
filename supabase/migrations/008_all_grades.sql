-- Tüm derecelendirme şirketlerinin fiyatları (PSA 1–10, BGS, CGC, SGC, TAG, ACE)
-- card_prices.grades: {"bgs9_5": {"p": 512.4, "c": "high", "n": 37}, "cgc10": {...}, ...}
-- Supabase → SQL Editor → bu dosyanın tamamını yapıştır → Run (bir kez)

alter table public.card_prices add column if not exists grades jsonb;

notify pgrst, 'reload schema';
