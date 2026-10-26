-- eBay ilan aramalarının kısa süreli önbelleği (eBay API günlük sınırını korumak için).
-- Yalnızca ilan özetleri (başlık, fiyat, bağlantı) tutulur; eBay kullanıcılarına ait kişisel veri saklanmaz.
-- Supabase → SQL Editor → bu dosyanın tamamını yapıştır → Run (bir kez)

create table if not exists public.ebay_cache (
  q text primary key,
  data jsonb not null,
  fetched_at timestamptz not null default now()
);
alter table public.ebay_cache enable row level security;
revoke all on public.ebay_cache from anon, authenticated;
grant all on public.ebay_cache to service_role;

-- 2 günden eski kayıtları temizle (fiyat görevi her çalıştığında çağrılabilir)
create or replace function public.ebay_cache_prune() returns void
language sql security definer set search_path = public as $$
  delete from public.ebay_cache where fetched_at < now() - interval '2 days';
$$;
revoke all on function public.ebay_cache_prune() from public, anon, authenticated;
grant execute on function public.ebay_cache_prune() to service_role;
