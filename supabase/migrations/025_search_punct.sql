-- Aramada kelimelerin başındaki/sonundaki noktalama yok sayılır: "Roaring Moon ex - 218/187" içindeki "-",
-- "Rayquaza GX (Secret)" içindeki parantezler; "Monkey.D.Luffy" gibi noktalı adlar da bulunur. Numaralar (OP05-119, 020/M-P) aynen kalır.
-- Önerilerden ya da son aramalardan gelen tam kart adlarıyla arama artık sonuç verir.
-- Supabase → SQL Editor → bu dosyanın tamamını yapıştır → Run (bir kez)

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
      from unnest(regexp_split_to_array(lower(btrim(coalesce(q, ''))), '\s+')) as t0(w0),
           lateral (select regexp_replace(w0, '^[^[:alnum:]]+|[^[:alnum:]]+$', '', 'g') as w) t
      where w <> '' and not (
        case
          when w ~ '^[0-9]+$' then
            c.num_key = coalesce(nullif(ltrim(w, '0'), ''), '0')
            or c.num_tail = coalesce(nullif(ltrim(w, '0'), ''), '0')
            or lower(coalesce(c.set_name, '')) ~ ('(^|[^0-9])' || w || '($|[^0-9])')
            or (c.number is null and c.search ~ ('(^|[^0-9])' || w || '($|[^0-9])'))
          when w ~ '/' then
            -- Tam numara: "63/193" yalnızca 063/193'ü bulur (başka setlerdeki 63 numaralar değil)
            regexp_replace(lower(coalesce(c.number, '')), '(^|/|[a-z])0+([0-9])', '\1\2', 'g')
              = regexp_replace(w, '(^|/|[a-z])0+([0-9])', '\1\2', 'g')
          else
            c.search like '%' || public._like_esc(w) || '%'
            or c.search like '%' || public._like_esc(regexp_replace(w, '[^[:alnum:]]', '', 'g')) || '%'
            or lower(coalesce(c.set_code, '')) = w
            or c.num_key = w
        end
      )
    );
$$;

notify pgrst, 'reload schema';
