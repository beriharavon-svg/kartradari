-- Yönetim paneli: yönetici yetkisi, anonim kullanım sayacı ve toplu istatistik fonksiyonları.
-- Gizlilik: fonksiyonlar yalnızca TOPLU veri döndürür; kimsenin alış fiyatı, sertifika no'su
-- ya da kişisel portföyü panelde görünmez. Kullanım sayacı kişiyle ilişkilendirilmez.
-- Supabase → SQL Editor → bu dosyanın tamamını yapıştır → Run (bir kez)

-- 1) Yöneticiler -------------------------------------------------------------
create table if not exists public.admins (
  user_id uuid primary key references auth.users(id) on delete cascade,
  email text,
  added_at timestamptz not null default now()
);
alter table public.admins enable row level security;
revoke all on public.admins from anon, authenticated;

-- Yönetici: sitedeki hesabın e-postası (farklıysa bu satırı değiştirip yeniden çalıştır)
insert into public.admins (user_id, email)
select id, email from auth.users where lower(email) = lower('beriharavon@gmail.com')
on conflict (user_id) do nothing;

create or replace function public.is_admin() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.admins where user_id = auth.uid());
$$;

-- 2) Anonim kullanım sayacı -------------------------------------------------
-- Kimin yaptığı tutulmaz: yalnızca ne arandı / hangi karta bakıldı ve zamanı.
create table if not exists public.events (
  id bigserial primary key,
  kind text not null check (kind in ('search', 'view')),
  q text,
  game text,
  product_id bigint,
  results integer,
  created_at timestamptz not null default now()
);
create index if not exists events_kind_time_idx on public.events (kind, created_at desc);
alter table public.events enable row level security;
revoke all on public.events from anon, authenticated;

create or replace function public.log_event(kind text, q text default null, g text default null,
                                            pid bigint default null, results integer default null)
returns void language plpgsql security definer set search_path = public as $$
begin
  if kind not in ('search', 'view') then return; end if;
  if kind = 'search' and length(btrim(coalesce(q, ''))) < 2 then return; end if;
  if kind = 'view' and pid is null then return; end if;
  insert into public.events (kind, q, game, product_id, results)
  values (kind, left(lower(btrim(q)), 80), left(g, 40), pid, results);
end;
$$;

-- 3) Yardımcılar: derece anahtarı ve bir kartın güncel fiyatı ------------------
create or replace function public._grade_key(g text) returns text
language sql immutable as $$
  select case when g = 'Ham' then 'raw'
    else (select lower(m[1]) || replace(m[2], '.', '_')
          from regexp_match(coalesce(g, ''), '^(PSA|BGS|CGC|SGC|TAG|ACE)\s*(\d+(?:\.5)?)', 'i') as m) end;
$$;

-- Portföy sayfasıyla aynı kural: o derecenin en son kaydedilmiş fiyatı (Pokemon dışı kartlarda ham fiyat)
create or replace function public._holding_price(cid bigint, g text) returns numeric
language sql stable set search_path = public as $$
  with k as (
    select case when (select source from public.cards where id = cid) = 'tcgcsv' then 'raw'
                else public._grade_key(g) end as key
  )
  select case
    when k.key is null then null
    when k.key = 'raw' then
      (select cp.raw from public.card_prices cp where cp.card_id = cid and cp.raw is not null order by cp.date desc limit 1)
    else
      (select coalesce(case when k.key = 'psa10' then cp.psa10 when k.key = 'psa9' then cp.psa9 end,
                       (cp.grades -> k.key ->> 'p')::numeric)
       from public.card_prices cp
       where cp.card_id = cid
         and (case when k.key = 'psa10' then cp.psa10 when k.key = 'psa9' then cp.psa9 end is not null
              or cp.grades ? k.key)
       order by cp.date desc limit 1)
  end
  from k;
$$;

create or replace function public._require_admin() returns void
language plpgsql stable security definer set search_path = public as $$
begin
  if not public.is_admin() then
    raise exception 'Bu işlem yalnızca yöneticiler içindir.' using errcode = '42501';
  end if;
end;
$$;

-- 4) Panel fonksiyonları (yalnızca yönetici; yalnızca toplu veri) --------------
create or replace function public.admin_overview(days integer default 30) returns jsonb
language plpgsql stable security definer set search_path = public, auth as $$
declare
  since timestamptz := now() - make_interval(days => greatest(1, least(coalesce(days, 30), 365)));
  r jsonb;
begin
  perform public._require_admin();
  select jsonb_build_object(
    'users', (select count(*) from auth.users),
    'users_new', (select count(*) from auth.users where created_at > since),
    'users_active', (select count(*) from auth.users where last_sign_in_at > since),
    'users_with_cards', (select count(distinct user_id) from public.holdings),
    'holdings', (select count(*) from public.holdings),
    'cards_qty', (select coalesce(sum(qty), 0) from public.holdings),
    'portfolio_value', (select coalesce(sum(p * qty), 0) from (
        select public._holding_price(h.card_id, h.grade) as p, h.qty from public.holdings h where h.card_id is not null) x
        where p is not null),
    'cost_total', (select coalesce(sum(cost_usd * qty), 0) from public.holdings),
    'folders', (select count(*) from public.folders),
    'match_status', (select coalesce(jsonb_object_agg(match_status, n), '{}'::jsonb)
                     from (select match_status, count(*) as n from public.holdings group by 1) s),
    'catalog_cards', (select count(*) from public.catalog),
    'catalog_last', (select value from public.job_state where key = 'catalog:last'),
    'credits_today', (select value -> 'used' from public.job_state
                      where key = 'ppt:' || to_char(now() at time zone 'utc', 'YYYY-MM-DD')),
    'last_price_date', (select max(date) from public.card_prices),
    'tracked_cards', (select count(distinct card_id) from public.holdings where card_id is not null),
    'searches', (select count(*) from public.events where kind = 'search' and created_at > since),
    'views', (select count(*) from public.events where kind = 'view' and created_at > since)
  ) into r;
  return r;
end;
$$;

create or replace function public.admin_daily(days integer default 30)
returns table (day date, signups bigint, searches bigint, views bigint)
language plpgsql stable security definer set search_path = public, auth as $$
begin
  perform public._require_admin();
  return query
  with d as (
    select generate_series((now() at time zone 'utc')::date - (greatest(1, least(coalesce(days, 30), 365)) - 1),
                           (now() at time zone 'utc')::date, interval '1 day')::date as day
  )
  select d.day,
    (select count(*) from auth.users u where (u.created_at at time zone 'utc')::date = d.day),
    (select count(*) from public.events e where e.kind = 'search' and (e.created_at at time zone 'utc')::date = d.day),
    (select count(*) from public.events e where e.kind = 'view' and (e.created_at at time zone 'utc')::date = d.day)
  from d order by d.day;
end;
$$;

create or replace function public.admin_top_held(lim integer default 20)
returns table (card_id bigint, name text, set_name text, number text, image text, game text,
               holders bigint, qty bigint, value numeric)
language plpgsql stable security definer set search_path = public as $$
begin
  perform public._require_admin();
  return query
  select k.id, k.name, k.set_name, k.number, k.image, k.game,
         count(distinct h.user_id), sum(h.qty)::bigint,
         round(sum(public._holding_price(h.card_id, h.grade) * h.qty), 2)
  from public.holdings h join public.cards k on k.id = h.card_id
  group by k.id, k.name, k.set_name, k.number, k.image, k.game
  order by count(distinct h.user_id) desc, 9 desc nulls last
  limit least(greatest(coalesce(lim, 20), 1), 100);
end;
$$;

create or replace function public.admin_top_searches(days integer default 30, lim integer default 25, zero_only boolean default false)
returns table (q text, game text, n bigint, zero bigint, avg_results numeric)
language plpgsql stable security definer set search_path = public as $$
begin
  perform public._require_admin();
  return query
  select e.q, coalesce(e.game, ''), count(*), count(*) filter (where e.results = 0), round(avg(e.results), 0)
  from public.events e
  where e.kind = 'search' and e.created_at > now() - make_interval(days => greatest(1, least(coalesce(days, 30), 365)))
  group by e.q, coalesce(e.game, '')
  having not zero_only or count(*) filter (where e.results = 0) > 0
  order by case when zero_only then count(*) filter (where e.results = 0) else count(*) end desc, e.q
  limit least(greatest(coalesce(lim, 25), 1), 100);
end;
$$;

create or replace function public.admin_top_views(days integer default 30, lim integer default 20)
returns table (product_id bigint, name text, set_name text, number text, image text, game text, market numeric, n bigint)
language plpgsql stable security definer set search_path = public as $$
begin
  perform public._require_admin();
  return query
  select e.product_id, c.name, c.set_name, c.number, c.image, c.game, c.market, count(*)
  from public.events e left join public.catalog c on c.product_id = e.product_id
  where e.kind = 'view' and e.created_at > now() - make_interval(days => greatest(1, least(coalesce(days, 30), 365)))
  group by e.product_id, c.name, c.set_name, c.number, c.image, c.game, c.market
  order by count(*) desc
  limit least(greatest(coalesce(lim, 20), 1), 100);
end;
$$;

create or replace function public.admin_mix()
returns table (dim text, label text, holdings bigint, value numeric)
language plpgsql stable security definer set search_path = public as $$
begin
  perform public._require_admin();
  return query
  select 'game', h.game || case when h.language = 'japanese' then ' (JP)' else '' end, count(*),
         round(sum(public._holding_price(h.card_id, h.grade) * h.qty), 2)
  from public.holdings h group by 2
  union all
  select 'grader', case when h.grade = 'Ham' then 'Ham' else split_part(h.grade, ' ', 1) end, count(*),
         round(sum(public._holding_price(h.card_id, h.grade) * h.qty), 2)
  from public.holdings h group by 2
  order by 1, 3 desc;
end;
$$;

-- 5) Yetkiler ----------------------------------------------------------------
revoke all on function public._grade_key(text) from public, anon, authenticated;
revoke all on function public._holding_price(bigint, text) from public, anon, authenticated;
revoke all on function public._require_admin() from public, anon, authenticated;
revoke all on function public.log_event(text, text, text, bigint, integer) from public;
revoke all on function public.is_admin() from public;
revoke all on function public.admin_overview(integer) from public, anon;
revoke all on function public.admin_daily(integer) from public, anon;
revoke all on function public.admin_top_held(integer) from public, anon;
revoke all on function public.admin_top_searches(integer, integer, boolean) from public, anon;
revoke all on function public.admin_top_views(integer, integer) from public, anon;
revoke all on function public.admin_mix() from public, anon;

grant execute on function public.log_event(text, text, text, bigint, integer) to anon, authenticated;
grant execute on function public.is_admin() to authenticated;
grant execute on function public.admin_overview(integer) to authenticated;
grant execute on function public.admin_daily(integer) to authenticated;
grant execute on function public.admin_top_held(integer) to authenticated;
grant execute on function public.admin_top_searches(integer, integer, boolean) to authenticated;
grant execute on function public.admin_top_views(integer, integer) to authenticated;
grant execute on function public.admin_mix() to authenticated;

notify pgrst, 'reload schema';
