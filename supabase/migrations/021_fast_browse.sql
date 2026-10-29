-- Arama sayfası açılışı hızlandırma: arama kutusu boşken (kart tarayıcısı) tüm katalog sıralanıp sayılırken
-- zaman aşımına düşüyordu (Magic ve Riftbound eklenince katalog büyüdü). Boş aramada artık doğrudan
-- indeksle sıralanmış ilk sayfa okunur ve toplam ayrıca sayılır. Arama yapıldığında davranış aynıdır.
-- Supabase → SQL Editor → bu dosyanın tamamını yapıştır → Run (bir kez)

create index if not exists catalog_browse_idx on public.catalog (market desc nulls last, product_id)
  where number is not null or rarity is not null;
create index if not exists catalog_game_browse_idx on public.catalog (game, market desc nulls last, product_id)
  where number is not null or rarity is not null;

create or replace function public.search_cards(
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
language plpgsql stable security definer set search_path = public, extensions as $$
#variable_conflict use_column
declare
  n bigint;
  l integer := least(greatest(coalesce(lim, 48), 1), 60);
  o integer := least(greatest(coalesce(off, 0), 0), 5000);
begin
  if btrim(coalesce(q, '')) <> '' then
    -- Arama var: eski (sonuç kümesi küçük) yol
    return query
    with words as (
      select string_agg(w, ' ') as txt
      from unnest(regexp_split_to_array(lower(btrim(coalesce(q, ''))), '\s+')) as t(w)
      where w <> '' and w !~ '[0-9]'
    ),
    hits as (
      select h.*, count(*) over () as cnt,
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
    pg as (
      select * from hits
      order by
        case when coalesce(sort, 'relevance') = 'relevance' then hits.rk end,
        case when sort = 'new' then hits.released end desc nulls last,
        case when sort in ('new', 'number') then hits.group_id end,
        case when sort in ('new', 'number') then hits.nnum end,
        case when sort = 'value_asc' then hits.market end asc nulls last,
        hits.market desc nulls last,
        hits.product_id
      limit l offset o
    )
    select pg.product_id, pg.game, pg.group_id, pg.set_name, pg.set_code, pg.released,
           pg.name, pg.number, pg.rarity, pg.image, pg.url, pg.sub_type, pg.market, pg.low, pg.price_date,
           p.psa10, p.psa10_conf, p.psa10_n, p.psa9, p.psa9_conf, p.psa9_n, (k.id is not null), pg.cnt
    from pg
    left join public.cards k on k.source = 'ppt' and k.ext_id = pg.product_id::text
    left join lateral (select cp.* from public.card_prices cp where cp.card_id = k.id order by cp.date desc limit 1) p on true
    order by
      case when coalesce(sort, 'relevance') = 'relevance' then pg.rk end,
      case when sort = 'new' then pg.released end desc nulls last,
      case when sort in ('new', 'number') then pg.group_id end,
      case when sort in ('new', 'number') then pg.nnum end,
      case when sort = 'value_asc' then pg.market end asc nulls last,
      pg.market desc nulls last,
      pg.product_id;
    return;
  end if;

  -- Boş arama (kart tarayıcısı): pencere fonksiyonu yok; toplam ayrı sayılır, ilk sayfa indeksle okunur
  select count(*) into n from public.catalog c
  where (c.number is not null or c.rarity is not null)
    and (coalesce(g, '') = '' or c.game = g) and (gid is null or c.group_id = gid);

  return query
  with pg as (
    select c.*, coalesce(nullif(left(regexp_replace(c.num_tail, '[^0-9]', '', 'g'), 12), ''), '0')::bigint as nnum
    from public.catalog c
    where (c.number is not null or c.rarity is not null)
      and (coalesce(g, '') = '' or c.game = g) and (gid is null or c.group_id = gid)
    order by
      case when sort = 'new' then c.released end desc nulls last,
      case when sort in ('new', 'number') then c.group_id end,
      case when sort in ('new', 'number') then coalesce(nullif(left(regexp_replace(c.num_tail, '[^0-9]', '', 'g'), 12), ''), '0')::bigint end,
      case when sort = 'value_asc' then c.market end asc nulls last,
      c.market desc nulls last,
      c.product_id
    limit l offset o
  )
  select pg.product_id, pg.game, pg.group_id, pg.set_name, pg.set_code, pg.released,
         pg.name, pg.number, pg.rarity, pg.image, pg.url, pg.sub_type, pg.market, pg.low, pg.price_date,
         p.psa10, p.psa10_conf, p.psa10_n, p.psa9, p.psa9_conf, p.psa9_n, (k.id is not null), n
  from pg
  left join public.cards k on k.source = 'ppt' and k.ext_id = pg.product_id::text
  left join lateral (select cp.* from public.card_prices cp where cp.card_id = k.id order by cp.date desc limit 1) p on true
  order by
    case when sort = 'new' then pg.released end desc nulls last,
    case when sort in ('new', 'number') then pg.group_id end,
    case when sort in ('new', 'number') then pg.nnum end,
    case when sort = 'value_asc' then pg.market end asc nulls last,
    pg.market desc nulls last,
    pg.product_id;
end $$;

revoke all on function public.search_cards(text, text, integer, text, integer, integer) from public;
grant execute on function public.search_cards(text, text, integer, text, integer, integer) to anon, authenticated;

notify pgrst, 'reload schema';
