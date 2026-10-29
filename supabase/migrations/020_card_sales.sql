-- eBay satış özeti: her derece için satış adedi, ortanca, aralık, son satış tarihi, yön ve son 30 günün günlük satışları.
-- Fiyat görevi her gün doldurur (ek kredi harcamaz; aynı yanıttan gelir).
-- Supabase → SQL Editor → bu dosyanın tamamını yapıştır → Run (bir kez)

alter table public.cards add column if not exists sales jsonb;

notify pgrst, 'reload schema';
