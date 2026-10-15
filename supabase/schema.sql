-- KartRadarı veritabanı şeması
-- Supabase → SQL Editor → New query → bu dosyanın tamamını yapıştır → Run

-- Kart kataloğu (fiyatı takip edilen kartlar)
create table if not exists public.cards (
  id bigint generated always as identity primary key,
  source text not null default 'ppt',
  ext_id text not null,
  game text not null default 'Pokemon',
  language text not null default 'english',
  name text not null,
  set_name text,
  number text,
  rarity text,
  image text,
  url text,
  last_priced date,
  created_at timestamptz not null default now(),
  unique (source, ext_id)
);

-- Günlük fiyat kaydı: ham + PSA 10 + PSA 9
create table if not exists public.card_prices (
  card_id bigint not null references public.cards(id) on delete cascade,
  date date not null,
  raw numeric,
  psa10 numeric,
  psa10_conf text,
  psa10_n integer,
  psa9 numeric,
  psa9_conf text,
  psa9_n integer,
  primary key (card_id, date)
);

-- Günlük kurlar (1 USD karşılığı)
create table if not exists public.fx_rates (
  date date primary key,
  rates jsonb not null
);

-- Kullanıcı portföyleri (yalnızca sahibi görebilir)
create table if not exists public.holdings (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  game text not null default 'Pokemon',
  set_input text,
  name_input text not null,
  number_input text,
  language text not null default 'english',
  grade text not null default 'PSA 10',
  cert text,
  qty integer not null default 1 check (qty > 0),
  cost_usd numeric not null default 0 check (cost_usd >= 0),
  bought date,
  buy_fx jsonb,
  card_id bigint references public.cards(id),
  match_status text not null default 'pending',
  match_note text,
  created_at timestamptz not null default now()
);
create index if not exists holdings_user_idx on public.holdings(user_id);
create index if not exists holdings_status_idx on public.holdings(match_status);

-- Otomatik görevin iç durumu (kredi sayacı vb.)
create table if not exists public.job_state (
  key text primary key,
  value jsonb,
  updated_at timestamptz not null default now()
);

-- Kart bilgisi değişirse yeniden eşleştirilsin
create or replace function public.holdings_rematch() returns trigger
language plpgsql as $$
begin
  if (new.name_input, new.set_input, new.number_input, new.language, new.game)
     is distinct from (old.name_input, old.set_input, old.number_input, old.language, old.game) then
    new.card_id := null;
    new.match_status := 'pending';
    new.match_note := null;
  end if;
  if new.bought is distinct from old.bought then
    new.buy_fx := null;
  end if;
  return new;
end $$;
drop trigger if exists holdings_rematch on public.holdings;
create trigger holdings_rematch before update on public.holdings
  for each row execute function public.holdings_rematch();

-- Satır düzeyinde güvenlik
alter table public.cards enable row level security;
alter table public.card_prices enable row level security;
alter table public.fx_rates enable row level security;
alter table public.holdings enable row level security;
alter table public.job_state enable row level security;

drop policy if exists "giris yapan okur" on public.cards;
create policy "giris yapan okur" on public.cards for select to authenticated using (true);
drop policy if exists "giris yapan okur" on public.card_prices;
create policy "giris yapan okur" on public.card_prices for select to authenticated using (true);
drop policy if exists "giris yapan okur" on public.fx_rates;
create policy "giris yapan okur" on public.fx_rates for select to authenticated using (true);

drop policy if exists "sahibi okur" on public.holdings;
create policy "sahibi okur" on public.holdings for select to authenticated using (user_id = auth.uid());
drop policy if exists "sahibi ekler" on public.holdings;
create policy "sahibi ekler" on public.holdings for insert to authenticated with check (user_id = auth.uid());
drop policy if exists "sahibi gunceller" on public.holdings;
create policy "sahibi gunceller" on public.holdings for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
drop policy if exists "sahibi siler" on public.holdings;
create policy "sahibi siler" on public.holdings for delete to authenticated using (user_id = auth.uid());
-- job_state için politika yok: yalnızca gizli anahtarla çalışan görev erişebilir.

-- Yetkiler
revoke all on public.cards, public.card_prices, public.fx_rates, public.holdings, public.job_state from anon;
grant select on public.cards, public.card_prices, public.fx_rates to authenticated;
grant select, insert, update, delete on public.holdings to authenticated;
revoke all on public.job_state from authenticated;
grant all on public.cards, public.card_prices, public.fx_rates, public.holdings, public.job_state to service_role;

-- Tabloların API'de hemen görünmesi için
notify pgrst, 'reload schema';
