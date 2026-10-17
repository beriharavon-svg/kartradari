-- Herkese açık kart kataloğu ve arama
-- Supabase → SQL Editor → bu dosyanın tamamını yapıştır → Run (bir kez)

create extension if not exists pg_trgm with schema extensions;

create table if not exists public.catalog (
  product_id bigint primary key,
  category_id integer not null,
  game text not null,
  group_id integer,
  set_name text,
  name text not null,
  clean_name text,
  number text,
  rarity text,
  image text,
  url text,
  sub_type text,
  market numeric,
  low numeric,
  price_date date,
  search text generated always as (
    lower(coalesce(clean_name, name) || ' ' || coalesce(number, '') || ' ' || coalesce(set_name, ''))
  ) stored,
  updated_at timestamptz not null default now()
);
create index if not exists catalog_search_trgm on public.catalog using gin (search extensions.gin_trgm_ops);
create index if not exists catalog_game_idx on public.catalog (game);
create index if not exists catalog_market_idx on public.catalog (market desc nulls last);

-- Tabloya doğrudan erişim yok; herkes yalnızca aşağıdaki fonksiyonlarla sınırlı sonuç alır.
alter table public.catalog enable row level security;
revoke all on public.catalog from anon, authenticated;
grant all on public.catalog to service_role;

create or replace function public.search_catalog(q text default '', g text default null, lim integer default 40)
returns table (
  product_id bigint, game text, set_name text, name text, number text, rarity text, image text, url text,
  sub_type text, market numeric, low numeric, price_date date,
  psa10 numeric, psa10_conf text, psa10_n integer, psa9 numeric, psa9_conf text, psa9_n integer, tracked boolean
)
language sql stable security definer set search_path = public, extensions as $$
  with terms as (
    select array_agg('%' || t || '%') as pats
    from unnest(string_to_array(lower(trim(coalesce(q, ''))), ' ')) t
    where length(t) > 0
  ),
  hits as (
    select c.*
    from public.catalog c, terms
    where (g is null or g = '' or c.game = g)
      and (terms.pats is null and c.number is not null or c.search ilike all (terms.pats))
    order by
      case when terms.pats is null then 0 else similarity(c.search, lower(trim(q))) end desc,
      c.market desc nulls last
    limit least(greatest(coalesce(lim, 40), 1), 60)
  )
  select h.product_id, h.game, h.set_name, h.name, h.number, h.rarity, h.image, h.url, h.sub_type,
         h.market, h.low, h.price_date,
         p.psa10, p.psa10_conf, p.psa10_n, p.psa9, p.psa9_conf, p.psa9_n, (k.id is not null) as tracked
  from hits h
  left join public.cards k on k.source = 'ppt' and k.ext_id = h.product_id::text
  left join lateral (
    select cp.* from public.card_prices cp where cp.card_id = k.id order by cp.date desc limit 1
  ) p on true
  order by
    case when coalesce(q, '') = '' then 0 else similarity(h.search, lower(trim(q))) end desc,
    h.market desc nulls last;
$$;

create or replace function public.card_history(pid bigint)
returns table (date date, raw numeric, psa10 numeric, psa9 numeric)
language sql stable security definer set search_path = public as $$
  select cp.date, cp.raw, cp.psa10, cp.psa9
  from public.cards k join public.card_prices cp on cp.card_id = k.id
  where k.source = 'ppt' and k.ext_id = pid::text
  order by cp.date
  limit 400;
$$;

create or replace function public.latest_fx()
returns table (date date, rates jsonb)
language sql stable security definer set search_path = public as $$
  select f.date, f.rates from public.fx_rates f order by f.date desc limit 1;
$$;

revoke all on function public.search_catalog(text, text, integer) from public;
revoke all on function public.card_history(bigint) from public;
revoke all on function public.latest_fx() from public;
grant execute on function public.search_catalog(text, text, integer) to anon, authenticated;
grant execute on function public.card_history(bigint) to anon, authenticated;
grant execute on function public.latest_fx() to anon, authenticated;

notify pgrst, 'reload schema';
