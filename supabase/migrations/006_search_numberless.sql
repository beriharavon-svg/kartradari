-- Aramaya numarası olmayan kartları da dahil et (ör. Japon "Vending Machine cards" serisi).
-- Kapalı ürünler (kutu, paket) hem numarası hem nadirliği olmadığı için yine aramaya girmez.
-- Supabase → SQL Editor → bu dosyanın tamamını yapıştır → Run (bir kez)

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

notify pgrst, 'reload schema';
