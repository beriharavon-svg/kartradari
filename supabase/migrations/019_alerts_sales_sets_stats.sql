-- 019: Hatalı fiyat ayıklama, portföy fiyat alarmları, haftalık özet maili, satışlar (gerçekleşen kâr),
--      set tamamlama ve vitrin istatistikleri.
-- Supabase → SQL Editor → bu dosyanın tamamını yapıştır → Run (bir kez)

-- 1) Fiyat: bir kartın belirli bir derecedeki fiyatı (tarih itibarıyla), tek günlük hatalı sıçramalar ayıklanmış ----------
-- Kural (portföy sayfasıyla aynı): son fiyat, önceki 4 kaydın ortancasından 2,5 kat saparsa ortanca kullanılır.
create or replace function public._key_price_at(cid bigint, key text, d date) returns numeric
language plpgsql stable set search_path = public as $$
declare
  a numeric[];
  m numeric;
begin
  if cid is null or key is null then return null; end if;
  select array_agg(p order by dt desc) into a from (
    select cp.date as dt,
           case when key = 'raw' then cp.raw
                when key = 'psa10' then coalesce(cp.psa10, (cp.grades -> 'psa10' ->> 'p')::numeric)
                when key = 'psa9' then coalesce(cp.psa9, (cp.grades -> 'psa9' ->> 'p')::numeric)
                else (cp.grades -> key ->> 'p')::numeric end as p
    from public.card_prices cp
    where cp.card_id = cid and cp.date <= d
      and (case when key = 'raw' then cp.raw
                when key = 'psa10' then coalesce(cp.psa10, (cp.grades -> 'psa10' ->> 'p')::numeric)
                when key = 'psa9' then coalesce(cp.psa9, (cp.grades -> 'psa9' ->> 'p')::numeric)
                else (cp.grades -> key ->> 'p')::numeric end) is not null
    order by cp.date desc
    limit 5) s;
  if a is null then return null; end if;
  if array_length(a, 1) >= 4 then
    select percentile_cont(0.5) within group (order by x) into m from unnest(a[2:5]) as x;
    if m > 0 and (a[1] > m * 2.5 or a[1] < m / 2.5) then return round(m, 2); end if;
  end if;
  return a[1];
end $$;

create or replace function public._holding_price_at(cid bigint, g text, d date) returns numeric
language sql stable set search_path = public as $$
  select public._key_price_at(cid,
    case when (select source from public.cards where id = cid) = 'tcgcsv' then 'raw' else public._grade_key(g) end, d);
$$;

-- Vitrin, alarm ve yönetim sayfası bunu kullanır: artık hatalı sıçramalar ayıklanmış güncel fiyat
create or replace function public._holding_price(cid bigint, g text) returns numeric
language sql stable set search_path = public as $$
  select public._holding_price_at(cid, g, current_date);
$$;

revoke all on function public._key_price_at(bigint, text, date) from public, anon, authenticated;
revoke all on function public._holding_price_at(bigint, text, date) from public, anon, authenticated;
revoke all on function public._holding_price(bigint, text) from public, anon, authenticated;


-- 2) Kullanıcı bildirim ayarları --------------------------------------------------------------------------------
create table if not exists public.user_prefs (
  user_id uuid primary key default auth.uid() references auth.users(id) on delete cascade,
  weekly_mail boolean not null default true,
  move_pct numeric check (move_pct is null or move_pct between 5 and 100),
  weekly_sent_on date,
  updated_at timestamptz not null default now()
);
alter table public.user_prefs enable row level security;
drop policy if exists "kendi ayarim" on public.user_prefs;
create policy "kendi ayarim" on public.user_prefs for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());
grant select, insert, update on public.user_prefs to authenticated;
grant all on public.user_prefs to service_role;


-- 3) Portföy fiyat alarmları: kart başına hedef (üstüne çıkınca / altına inince) ve genel % hareket alarmı ----------
alter table public.holdings add column if not exists alert_above numeric check (alert_above is null or alert_above > 0);
alter table public.holdings add column if not exists alert_below numeric check (alert_below is null or alert_below > 0);
alter table public.holdings add column if not exists alert_ref numeric;   -- % alarmı için son referans fiyat

create or replace function public.holding_alerts_due()
returns table (holding_id uuid, email text, kind text, name text, set_name text, number text, grade text,
               image text, price numeric, ref numeric, pct numeric)
language plpgsql security definer set search_path = public, auth as $$
#variable_conflict use_column
begin
  -- % alarmı açık kullanıcıların yeni kartları için referans fiyatı belirle (ilk seferde mail gitmez)
  update public.holdings h set alert_ref = public._holding_price(h.card_id, h.grade)
  where h.alert_ref is null and h.card_id is not null and h.sold_at is null
    and exists (select 1 from public.user_prefs u where u.user_id = h.user_id and u.move_pct is not null);

  return query
  with x as (
    select h.id, h.user_id, h.alert_above, h.alert_below, h.alert_ref, h.grade, u.move_pct,
           coalesce(k.name, h.name_input) as nm, coalesce(k.set_name, h.set_input) as st,
           coalesce(k.number, h.number_input) as nu, coalesce(k.image_cached, k.image) as im,
           public._holding_price(h.card_id, h.grade) as p
    from public.holdings h
    left join public.user_prefs u on u.user_id = h.user_id
    left join public.cards k on k.id = h.card_id
    where h.card_id is not null and h.sold_at is null
      and (h.alert_above is not null or h.alert_below is not null or u.move_pct is not null)
  ), y as (
    select x.*, case
      when x.alert_above is not null and x.p >= x.alert_above then 'above'
      when x.alert_below is not null and x.p <= x.alert_below then 'below'
      when x.move_pct is not null and x.alert_ref > 0 and x.p >= x.alert_ref * (1 + x.move_pct / 100) then 'up'
      when x.move_pct is not null and x.alert_ref > 0 and x.p <= x.alert_ref * (1 - x.move_pct / 100) then 'down'
    end as kd
    from x where x.p is not null
  )
  select y.id, us.email::text, y.kd, y.nm, y.st, y.nu, y.grade, y.im, round(y.p, 2),
         case y.kd when 'above' then y.alert_above when 'below' then y.alert_below else y.alert_ref end,
         case when y.alert_ref > 0 then round((y.p / y.alert_ref - 1) * 100, 1) end
  from y join auth.users us on us.id = y.user_id
  where y.kd is not null and us.email is not null and us.email_confirmed_at is not null
  order by us.email
  limit 1000;
end $$;

-- Mail gittikten sonra: tetiklenen hedefler silinir (tek seferlik), % alarmının referansı güncel fiyata çekilir
create or replace function public.holding_alerts_mark(ids uuid[]) returns void
language sql security definer set search_path = public as $$
  update public.holdings h set
    alert_above = case when h.alert_above is not null and p.v >= h.alert_above then null else h.alert_above end,
    alert_below = case when h.alert_below is not null and p.v <= h.alert_below then null else h.alert_below end,
    alert_ref = coalesce(p.v, h.alert_ref)
  from (select hh.id, public._holding_price(hh.card_id, hh.grade) as v from public.holdings hh where hh.id = any(ids)) p
  where h.id = p.id;
$$;

revoke all on function public.holding_alerts_due() from public, anon, authenticated;
revoke all on function public.holding_alerts_mark(uuid[]) from public, anon, authenticated;
grant execute on function public.holding_alerts_due() to service_role;
grant execute on function public.holding_alerts_mark(uuid[]) to service_role;


-- 4) Haftalık özet maili (pazartesi): portföy değeri ve haftalık değişim, en çok yükselen/düşen kartlar,
--    istek listesinde hedefe yaklaşanlar. Ayarlardan kapatılabilir.
create or replace function public.weekly_digest()
returns table (user_id uuid, email text, data jsonb)
language plpgsql security definer set search_path = public, auth as $$
#variable_conflict use_column
begin
  return query
  with u as (
    select au.id, au.email::text as em
    from auth.users au left join public.user_prefs p on p.user_id = au.id
    where au.email is not null and au.email_confirmed_at is not null
      and coalesce(p.weekly_mail, true)
      and (p.weekly_sent_on is null or p.weekly_sent_on <= current_date - 6)
  ), h as (
    select h.user_id, h.qty, h.cost_usd, h.grade, coalesce(k.name, h.name_input) as name,
           coalesce(k.set_name, h.set_input) as set_name, coalesce(h.photo_url, k.image_cached, k.image) as image,
           case when h.card_id is null then h.manual_value else public._holding_price(h.card_id, h.grade) end as now_p,
           case when h.card_id is null then h.manual_value else public._holding_price_at(h.card_id, h.grade, current_date - 7) end as prev_p
    from public.holdings h join u on u.id = h.user_id left join public.cards k on k.id = h.card_id
    where h.sold_at is null
  ), m as (
    select h.*, case when h.prev_p > 0 and h.now_p is not null then (h.now_p / h.prev_p - 1) * 100 end as chg
    from h
  ), agg as (
    select m.user_id,
           count(*) as cards,
           round(sum(m.now_p * m.qty), 2) as total,
           round(sum(coalesce(m.prev_p, m.now_p) * m.qty) filter (where m.now_p is not null), 2) as prev_total,
           round(sum(m.cost_usd * m.qty) filter (where m.now_p is not null), 2) as cost
    from m group by m.user_id
  ), up as (
    select z.user_id, jsonb_agg(jsonb_build_object('name', z.name, 'set', z.set_name, 'grade', z.grade, 'image', z.image,
             'price', round(z.now_p, 2), 'chg', round(z.chg, 1)) order by z.chg desc) as j
    from (select m.*, row_number() over (partition by m.user_id order by m.chg desc) as rn
          from m where m.chg > 0.5 and abs(m.now_p - m.prev_p) >= 1) z
    where z.rn <= 3 group by z.user_id
  ), dn as (
    select z.user_id, jsonb_agg(jsonb_build_object('name', z.name, 'set', z.set_name, 'grade', z.grade, 'image', z.image,
             'price', round(z.now_p, 2), 'chg', round(z.chg, 1)) order by z.chg) as j
    from (select m.*, row_number() over (partition by m.user_id order by m.chg) as rn
          from m where m.chg < -0.5 and abs(m.now_p - m.prev_p) >= 1) z
    where z.rn <= 3 group by z.user_id
  ), w as (
    select z.user_id, jsonb_agg(jsonb_build_object('name', z.name, 'grade', z.grade, 'image', z.image,
             'price', round(z.p, 2), 'target', z.target_usd) order by z.p / z.target_usd) as j
    from (select wl.user_id, wl.grade, wl.target_usd, coalesce(c.name, k.name) as name,
                 coalesce(k.image_cached, k.image, c.image) as image,
                 public._holding_price(wl.card_id, wl.grade) as p
          from public.wishlist wl join u on u.id = wl.user_id
          left join public.catalog c on c.product_id = wl.product_id
          left join public.cards k on k.id = wl.card_id
          where wl.target_usd is not null) z
    where z.p is not null and z.p <= z.target_usd * 1.10
    group by z.user_id
  )
  select u.id, u.em, jsonb_build_object(
           'cards', coalesce(agg.cards, 0), 'total', agg.total, 'prev_total', agg.prev_total, 'cost', agg.cost,
           'up', coalesce(up.j, '[]'::jsonb), 'down', coalesce(dn.j, '[]'::jsonb), 'wish', coalesce(w.j, '[]'::jsonb))
  from u
  left join agg on agg.user_id = u.id
  left join up on up.user_id = u.id
  left join dn on dn.user_id = u.id
  left join w on w.user_id = u.id
  where coalesce(agg.cards, 0) > 0 or w.j is not null
  limit 2000;
end $$;

create or replace function public.weekly_mark_sent(ids uuid[]) returns void
language sql security definer set search_path = public as $$
  insert into public.user_prefs (user_id, weekly_sent_on)
  select x, current_date from unnest(ids) as x
  on conflict (user_id) do update set weekly_sent_on = current_date;
$$;

revoke all on function public.weekly_digest() from public, anon, authenticated;
revoke all on function public.weekly_mark_sent(uuid[]) from public, anon, authenticated;
grant execute on function public.weekly_digest() to service_role;
grant execute on function public.weekly_mark_sent(uuid[]) to service_role;


-- 5) Satışlar: satış fiyatı, para birimi, satış anındaki kur; gerçekleşen kâr hesabı için ------------------------
alter table public.holdings add column if not exists sold_price numeric check (sold_price is null or sold_price >= 0);
alter table public.holdings add column if not exists sold_ccy text check (sold_ccy is null or sold_ccy in ('TRY', 'USD', 'EUR', 'GBP'));
alter table public.holdings add column if not exists sold_usd numeric;      -- adet başına, USD
alter table public.holdings add column if not exists sold_note text check (sold_note is null or char_length(sold_note) <= 140);
alter table public.holdings add column if not exists sold_try_rate numeric; -- satış günü 1 USD = ? TL
alter table public.holdings add column if not exists cost_try_rate numeric; -- alış günü 1 USD = ? TL

-- Satış fiyatı ya da tarihi değişince USD karşılığı ve kurlar yeniden hesaplanır
create or replace function public.holdings_sold_calc() returns trigger
language plpgsql security definer set search_path = public as $$
declare
  rs jsonb;
  rb jsonb;
begin
  if new.sold_at is null then
    new.sold_price := null; new.sold_ccy := null; new.sold_usd := null; new.sold_note := null;
    new.sold_try_rate := null; new.cost_try_rate := null;
    return new;
  end if;
  select f.rates into rs from public.fx_rates f where f.date <= new.sold_at::date order by f.date desc limit 1;
  if rs is null then select f.rates into rs from public.fx_rates f order by f.date asc limit 1; end if;
  select f.rates into rb from public.fx_rates f where f.date <= coalesce(new.bought, new.created_at::date) order by f.date desc limit 1;
  if rb is null then select f.rates into rb from public.fx_rates f order by f.date asc limit 1; end if;
  new.sold_try_rate := (rs ->> 'TRY')::numeric;
  new.cost_try_rate := (rb ->> 'TRY')::numeric;
  new.sold_usd := case
    when new.sold_price is null then null
    when coalesce(new.sold_ccy, 'USD') = 'USD' then new.sold_price
    when (rs ->> new.sold_ccy)::numeric > 0 then round(new.sold_price / (rs ->> new.sold_ccy)::numeric, 4)
  end;
  return new;
end $$;
drop trigger if exists holdings_sold_calc on public.holdings;
create trigger holdings_sold_calc before insert or update of sold_at, sold_price, sold_ccy, bought on public.holdings
  for each row execute function public.holdings_sold_calc();

-- Kart sat: adetin bir kısmı satılırsa kart ikiye ayrılır (kalan adet portföyde kalır)
create or replace function public.sell_holding(hid uuid, n integer, price numeric, ccy text, d date, note text default null)
returns uuid
language plpgsql security definer set search_path = public as $$
declare
  h public.holdings;
  nid uuid;
begin
  select * into h from public.holdings where id = hid and user_id = auth.uid() for update;
  if not found then raise exception 'Kart bulunamadı.' using errcode = '42501'; end if;
  if h.sold_at is not null then raise exception 'Bu kart zaten satıldı olarak işaretli.' using errcode = '22023'; end if;
  if n is null or n < 1 or n > h.qty then raise exception 'Adet 1 ile % arasında olmalı.', h.qty using errcode = '22023'; end if;
  if price is not null and price < 0 then raise exception 'Fiyat negatif olamaz.' using errcode = '22023'; end if;
  if ccy not in ('TRY', 'USD', 'EUR', 'GBP') then ccy := 'USD'; end if;
  if d is null or d > current_date + 1 then d := current_date; end if;
  if n < h.qty then
    update public.holdings set qty = qty - n where id = hid;
    nid := gen_random_uuid();
    insert into public.holdings
    select (jsonb_populate_record(null::public.holdings, to_jsonb(h) || jsonb_build_object(
      'id', nid, 'qty', n, 'created_at', h.created_at, 'sold_at', (d::timestamp + time '12:00') at time zone 'Europe/Istanbul',
      'sold_price', price, 'sold_ccy', ccy, 'sold_note', left(note, 140)))).*;
    return nid;
  end if;
  update public.holdings set sold_at = (d::timestamp + time '12:00') at time zone 'Europe/Istanbul',
    sold_price = price, sold_ccy = ccy, sold_note = left(note, 140)
  where id = hid;
  return hid;
end $$;
revoke all on function public.sell_holding(uuid, integer, numeric, text, date, text) from public, anon;
grant execute on function public.sell_holding(uuid, integer, numeric, text, date, text) to authenticated;

-- Mevcut satılmış kartların kurlarını doldur
update public.holdings set sold_at = sold_at where sold_at is not null and sold_try_rate is null;


-- 6) Set tamamlama: kullanıcının kartı olan setlerde kaç kart var, kaçı eksik, eksiklerin piyasa değeri --------------
create or replace function public.my_sets()
returns table (group_id integer, game text, set_name text, total bigint, owned bigint, missing_value numeric)
language sql stable security definer set search_path = public as $$
  with o as (
    select distinct c.group_id, c.product_id
    from public.holdings h
    join public.cards k on k.id = h.card_id
    join public.catalog c on c.product_id = case when k.ext_id ~ '^\d{1,18}$' then k.ext_id::bigint end
    where h.user_id = auth.uid() and h.sold_at is null and c.group_id is not null and c.number is not null
  ), g as (
    select o.group_id, count(*) as owned from o group by o.group_id
  )
  select g.group_id, max(c.game), max(c.set_name), count(*), g.owned,
         round(coalesce(sum(c.market) filter (where not exists (select 1 from o where o.product_id = c.product_id)), 0), 2)
  from g join public.catalog c on c.group_id = g.group_id and c.number is not null
  group by g.group_id, g.owned
  order by g.owned::numeric / greatest(count(*), 1) desc, max(c.set_name);
$$;

create or replace function public.my_set_cards(gid integer)
returns table (product_id bigint, name text, number text, rarity text, image text, market numeric, owned boolean, game text, set_name text)
language sql stable security definer set search_path = public as $$
  with o as (
    select distinct k.ext_id
    from public.holdings h join public.cards k on k.id = h.card_id
    where h.user_id = auth.uid() and h.sold_at is null
  )
  select c.product_id, c.name, c.number, c.rarity, c.image, c.market,
         exists (select 1 from o where o.ext_id = c.product_id::text), c.game, c.set_name
  from public.catalog c
  where c.group_id = gid and c.number is not null
  order by nullif(regexp_replace(split_part(c.number, '/', 1), '\D', '', 'g'), '')::numeric nulls last, c.number, c.name
  limit 1500;
$$;
revoke all on function public.my_sets() from public, anon;
revoke all on function public.my_set_cards(integer) from public, anon;
grant execute on function public.my_sets() to authenticated;
grant execute on function public.my_set_cards(integer) to authenticated;


-- 7) Vitrin istatistikleri: günlük görüntülenme, iletişim tıklamaları (kanal ve kart bazında) ---------------------
alter table public.events add column if not exists ref text;
alter table public.events add column if not exists item text;
alter table public.events drop constraint if exists events_kind_check;
alter table public.events add constraint events_kind_check check (kind in ('search', 'view', 'contact', 'sview'));
create index if not exists events_ref_idx on public.events (ref, created_at desc) where ref is not null;

drop function if exists public.showcase_contact(text, text);
create or replace function public.showcase_contact(s text, ch text, item text default null) returns void
language plpgsql security definer set search_path = public as $$
declare
  key text := lower(split_part(btrim(coalesce(s, ''), '/ '), '/', 1));
begin
  if ch not in ('wa', 'ig') or key = '' then return; end if;
  update public.showcases set contact_clicks = contact_clicks + 1 where code = key and enabled;
  if found then
    insert into public.events (kind, q, game, ref, item) values ('contact', ch, left(key, 40), left(key, 40), left(item, 120));
  end if;
end $$;
revoke all on function public.showcase_contact(text, text, text) from public;
grant execute on function public.showcase_contact(text, text, text) to anon, authenticated;

-- Vitrin sahibinin kendi istatistikleri (yalnızca sahibi görebilir)
create or replace function public.my_showcase_stats(sid uuid) returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  v public.showcases;
  days jsonb;
  ch jsonb;
  items jsonb;
  v30 bigint;
  c30 bigint;
begin
  select * into v from public.showcases where id = sid and user_id = auth.uid();
  if not found then return null; end if;
  select coalesce(jsonb_agg(jsonb_build_object('d', to_char(d, 'YYYY-MM-DD'), 'n', coalesce(e.n, 0)) order by d), '[]'::jsonb) into days
  from generate_series(current_date - 29, current_date, interval '1 day') as d
  left join (select (created_at at time zone 'Europe/Istanbul')::date as dd, count(*) as n
             from public.events where kind = 'sview' and ref = v.code and created_at > now() - interval '31 days'
             group by 1) e on e.dd = d::date;
  select count(*) into v30 from public.events where kind = 'sview' and ref = v.code and created_at > now() - interval '30 days';
  select count(*), coalesce(jsonb_object_agg(q, n), '{}'::jsonb) into c30, ch
  from (select q, count(*) as n from public.events
        where kind = 'contact' and (ref = v.code or game = v.code) and created_at > now() - interval '30 days' group by q) z;
  select coalesce(jsonb_agg(jsonb_build_object('item', item, 'n', n) order by n desc), '[]'::jsonb) into items
  from (select item, count(*) as n from public.events
        where kind = 'contact' and (ref = v.code or game = v.code) and item is not null
          and created_at > now() - interval '90 days'
        group by item order by count(*) desc limit 10) z;
  return jsonb_build_object('views_total', v.views, 'contacts_total', v.contact_clicks,
    'views_30', v30, 'contacts_30', coalesce((select sum((value)::bigint) from jsonb_each_text(ch)), 0),
    'channels', ch, 'days', days, 'items', items);
end $$;
revoke all on function public.my_showcase_stats(uuid) from public, anon;
grant execute on function public.my_showcase_stats(uuid) to authenticated;

-- Herkese açık vitrin: görüntülenme yalnızca o vitrine sayılır (sahibin kendi bakışı sayılmaz), günlük kayıt tutulur.
-- Satılan kartlar vitrinin toplamına katılmaz; 14 gün "Satıldı" etiketiyle görünür.
create or replace function public.showcase(s text) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  v public.showcases;
  key text := lower(split_part(btrim(coalesce(s, ''), '/ '), '/', 1));
  items jsonb;
  wish jsonb;
  tot numeric;
  n bigint;
  nsale bigint;
  fx jsonb;
begin
  if key = '' then return null; end if;
  select * into v from public.showcases where code = key and enabled;
  if not found then
    select * into v from public.showcases where slug = key and enabled;
  end if;
  if not found then return null; end if;
  if auth.uid() is distinct from v.user_id then
    update public.showcases set views = views + 1 where id = v.id;
    insert into public.events (kind, ref) values ('sview', v.code);
  end if;

  with x as (
    select coalesce(k.name, h.name_input) as name, coalesce(k.set_name, h.set_input) as set_name,
           coalesce(k.number, h.number_input) as number, coalesce(h.photo_url, k.image_cached, k.image) as image, h.game, h.language, h.grade, h.qty,
           h.variant, h.sport,
           coalesce(public._holding_price(h.card_id, h.grade), h.manual_value) as unit,
           h.for_sale, h.ask_price, h.ask_ccy, h.sale_note, h.sold_at
    from public.holdings h left join public.cards k on k.id = h.card_id
    where h.user_id = v.user_id
      and (v.folder_id is null
           or exists (select 1 from public.folder_items fi where fi.folder_id = v.folder_id and fi.holding_id = h.id))
      and (not v.only_for_sale or h.for_sale)
      and (h.sold_at is null or (h.for_sale and h.sold_at > now() - interval '14 days'))
  ), y as (
    select *, round(unit * qty, 2) as val from x
  )
  select coalesce(jsonb_agg(jsonb_build_object(
           'name', name, 'set', set_name, 'number', number, 'image', image, 'game', game,
           'jp', language = 'japanese', 'grade', grade, 'qty', qty, 'variant', variant, 'sport', sport,
           'value', case when v.show_values then val end,
           'sale', for_sale,
           'ask', case when for_sale then ask_price end,
           'ccy', case when for_sale then ask_ccy end,
           'note', case when for_sale then sale_note end,
           'sold', for_sale and sold_at is not null,
           'market', case when for_sale and v.show_market then round(unit, 2) end)
         order by (for_sale and sold_at is null) desc, val desc nulls last, name), '[]'::jsonb),
         sum(val) filter (where sold_at is null), sum(qty) filter (where sold_at is null),
         count(*) filter (where for_sale and sold_at is null)
    into items, tot, n, nsale
  from (select * from y order by (for_sale and sold_at is null) desc, val desc nulls last, name limit 500) y;

  if v.show_wishlist then
    select coalesce(jsonb_agg(jsonb_build_object(
             'name', coalesce(c.name, k.name), 'set', coalesce(c.set_name, k.set_name),
             'number', coalesce(c.number, k.number), 'image', coalesce(k.image_cached, k.image, c.image),
             'game', c.game, 'grade', w.grade) order by w.created_at desc), '[]'::jsonb)
      into wish
    from (select * from public.wishlist where user_id = v.user_id order by created_at desc limit 200) w
    left join public.catalog c on c.product_id = w.product_id
    left join public.cards k on k.id = w.card_id;
  end if;

  select f.rates into fx from public.fx_rates f order by f.date desc limit 1;

  return jsonb_build_object(
    'code', v.code, 'slug', v.code, 'title', v.title, 'bio', v.bio, 'contact', v.contact,
    'whatsapp', v.whatsapp, 'instagram', v.instagram,
    'show_values', v.show_values, 'show_market', v.show_market, 'only_for_sale', v.only_for_sale,
    'updated', v.updated_at, 'fx', fx,
    'count', coalesce(n, 0), 'for_sale', coalesce(nsale, 0),
    'total', case when v.show_values then coalesce(tot, 0) end,
    'cards', items, 'wishlist', coalesce(wish, '[]'::jsonb));
end;
$$;
revoke all on function public.showcase(text) from public;
grant execute on function public.showcase(text) to anon, authenticated;

notify pgrst, 'reload schema';
