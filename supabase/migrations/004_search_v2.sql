-- Akıllı kart arama: ad / set / numara ayrımı, set filtresi, sıralama, sayfalama
-- Supabase → SQL Editor → bu dosyanın tamamını yapıştır → Run (bir kez)

alter table public.catalog add column if not exists set_code text;
alter table public.catalog add column if not exists released date;

-- Kart numarasının sade hâli: "004/102" → "4", "OP05-119" → "op05-119", "TG12/TG30" → "tg12"
alter table public.catalog add column if not exists num_key text generated always as (
  regexp_replace(lower(split_part(coalesce(number, ''), '/', 1)), '^0+([0-9])', '\1')
) stored;
-- Numaranın yalnızca sayı kısmı: "OP05-119" → "119", "TG12" → "12", "SWSH050" → "50"
alter table public.catalog add column if not exists num_tail text generated always as (
  regexp_replace(regexp_replace(lower(split_part(coalesce(number, ''), '/', 1)), '^.*-', ''), '^[a-z]*0*([0-9])', '\1')
) stored;

create index if not exists catalog_num_key_idx on public.catalog (num_key);
create index if not exists catalog_num_tail_idx on public.catalog (num_tail);
create index if not exists catalog_group_idx on public.catalog (group_id);

create or replace function public._like_esc(s text) returns text
language sql immutable as $$
  select replace(replace(replace(s, '\', '\\'), '%', '\%'), '_', '\_');
$$;

-- Arama kuralı: her kelime eşleşmeli.
--   Yalnız rakam ("199")           → kart numarası (199/165, OP05-199, TG199 …) ya da set adındaki sayı ("151")
--   Bölü işaretli ("4/102")        → tam kart numarası
--   Diğer her şey ("charizard", "evolving", "op05", "sv8a") → kart adı, set adı veya set kodu
-- Kapalı ürünler (kutu, paket; numarası ve nadirliği olmayanlar) aramaya girmez.
-- Numarası olmayan kartlar (ör. Japon Vending serisi) nadirliği olduğu için aramada kalır.
create or replace function public._catalog_hits(q text, g text, gid integer)
returns setof public.catalog
language sql stable set search_path = public, extensions as $$
  select c.*
  from public.catalog c
  where (c.number is not null or c.rarity is not null)
    and (coalesce(g, '') = '' or c.game = g)
    and (gid is null or c.group_id = gid)
    and not exists (
      select 1
      from unnest(regexp_split_to_array(lower(btrim(coalesce(q, ''))), '\s+')) as t(w)
      where w <> '' and not (
        case
          when w ~ '^[0-9]+$' then
            c.num_key = coalesce(nullif(ltrim(w, '0'), ''), '0')
            or c.num_tail = coalesce(nullif(ltrim(w, '0'), ''), '0')
            or lower(coalesce(c.set_name, '')) ~ ('(^|[^0-9])' || w || '($|[^0-9])')
            or (c.number is null and c.search ~ ('(^|[^0-9])' || w || '($|[^0-9])'))
          when w ~ '/' then
            lower(c.number) = w
            or c.num_key = regexp_replace(split_part(w, '/', 1), '^0+([0-9])', '\1')
          else
            c.search like '%' || public._like_esc(w) || '%'
            or lower(coalesce(c.set_code, '')) = w
            or c.num_key = w
        end
      )
    );
$$;

drop function if exists public.search_cards(text, text, integer, text, integer, integer);
create function public.search_cards(
  q text default '', g text default null, gid integer default null,
  sort text default 'relevance', lim integer default 48, off integer default 0
)
returns table (
  product_id bigint, game text, group_id integer, set_name text, set_code text, released date,
  name text, number text, rarity text, image text, url text,
  sub_type text, market numeric, low numeric, price_date date,
  psa10 numeric, psa10_conf text, psa10_n integer, psa9 numeric, psa9_conf text, psa9_n integer,
  tracked boolean, total bigint
)
language sql stable security definer set search_path = public, extensions as $$
  with words as (
    select string_agg(w, ' ') as txt
    from unnest(regexp_split_to_array(lower(btrim(coalesce(q, ''))), '\s+')) as t(w)
    where w <> '' and w !~ '[0-9]'
  ),
  hits as (
    select h.*, count(*) over () as total,
      case
        when wd.txt is null then 0
        when lower(coalesce(h.clean_name, h.name)) = wd.txt then 0
        when lower(coalesce(h.clean_name, h.name)) like public._like_esc(wd.txt) || '%' then 1
        when lower(coalesce(h.clean_name, h.name)) like '%' || public._like_esc(wd.txt) || '%' then 2
        else 3
      end as rk,
      coalesce(nullif(left(regexp_replace(h.num_tail, '[^0-9]', '', 'g'), 12), ''), '0')::bigint as nnum
    from public._catalog_hits(q, g, gid) h, words wd
  ),
  page as (
    select * from hits
    order by
      case when coalesce(sort, 'relevance') = 'relevance' then rk end,
      case when sort = 'new' then released end desc nulls last,
      case when sort in ('new', 'number') then hits.group_id end,
      case when sort in ('new', 'number') then nnum end,
      case when sort = 'value_asc' then market end asc nulls last,
      market desc nulls last,
      hits.product_id
    limit least(greatest(coalesce(lim, 48), 1), 60)
    offset least(greatest(coalesce(off, 0), 0), 5000)
  )
  select pg.product_id, pg.game, pg.group_id, pg.set_name, pg.set_code, pg.released,
         pg.name, pg.number, pg.rarity, pg.image, pg.url, pg.sub_type, pg.market, pg.low, pg.price_date,
         p.psa10, p.psa10_conf, p.psa10_n, p.psa9, p.psa9_conf, p.psa9_n, (k.id is not null) as tracked, pg.total
  from page pg
  left join public.cards k on k.source = 'ppt' and k.ext_id = pg.product_id::text
  left join lateral (
    select cp.* from public.card_prices cp where cp.card_id = k.id order by cp.date desc limit 1
  ) p on true
  order by
    case when coalesce(sort, 'relevance') = 'relevance' then pg.rk end,
    case when sort = 'new' then pg.released end desc nulls last,
    case when sort in ('new', 'number') then pg.group_id end,
    case when sort in ('new', 'number') then pg.nnum end,
    case when sort = 'value_asc' then pg.market end asc nulls last,
    pg.market desc nulls last,
    pg.product_id;
$$;

-- Setler: arama boşsa oyunun tüm setleri (yeniden eskiye), doluysa aramaya uyan setler (en çok sonuç verenden)
drop function if exists public.search_sets(text, text, integer);
create function public.search_sets(q text default '', g text default null, lim integer default 40)
returns table (group_id integer, set_name text, set_code text, game text, released date, n bigint)
language sql stable security definer set search_path = public, extensions as $$
  select h.group_id, max(h.set_name), max(h.set_code), max(h.game), max(h.released), count(*)
  from public._catalog_hits(q, g, null) h
  group by h.group_id
  order by
    case when coalesce(btrim(q), '') = '' then null else count(*) end desc nulls last,
    max(h.released) desc nulls last,
    max(h.set_name)
  limit least(greatest(coalesce(lim, 40), 1), 2000);
$$;

revoke all on function public._like_esc(text) from public, anon, authenticated;
revoke all on function public._catalog_hits(text, text, integer) from public, anon, authenticated;
revoke all on function public.search_cards(text, text, integer, text, integer, integer) from public;
revoke all on function public.search_sets(text, text, integer) from public;
grant execute on function public.search_cards(text, text, integer, text, integer, integer) to anon, authenticated;
grant execute on function public.search_sets(text, text, integer) to anon, authenticated;

notify pgrst, 'reload schema';
