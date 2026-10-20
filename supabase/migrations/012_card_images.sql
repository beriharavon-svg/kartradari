-- Kart görsellerinin kendi depomuzdaki kopyası (vitrin görseli bunları çizebilsin diye).
-- Fiyat görevi takip edilen kartların görsellerini 'card-images' deposuna kopyalar.
-- Supabase → SQL Editor → bu dosyanın tamamını yapıştır → Run (bir kez)

alter table public.cards add column if not exists image_cached text;

-- Herkese açık okunabilen görsel deposu (yalnızca fiyat görevi yazabilir)
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('card-images', 'card-images', true, 2097152, array['image/jpeg', 'image/png', 'image/webp'])
on conflict (id) do update set public = true;

create or replace function public.showcase(s text) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  v public.showcases;
  items jsonb;
  wish jsonb;
  tot numeric;
  n bigint;
begin
  select * into v from public.showcases where slug = lower(btrim(coalesce(s, ''))) and enabled;
  if not found then return null; end if;
  update public.showcases set views = views + 1 where user_id = v.user_id;

  with x as (
    select coalesce(k.name, h.name_input) as name, coalesce(k.set_name, h.set_input) as set_name,
           coalesce(k.number, h.number_input) as number, coalesce(k.image_cached, k.image) as image, h.game, h.language, h.grade, h.qty,
           round(public._holding_price(h.card_id, h.grade) * h.qty, 2) as val
    from public.holdings h left join public.cards k on k.id = h.card_id
    where h.user_id = v.user_id
      and (v.folder_id is null
           or exists (select 1 from public.folder_items fi where fi.folder_id = v.folder_id and fi.holding_id = h.id))
  )
  select coalesce(jsonb_agg(jsonb_build_object(
           'name', name, 'set', set_name, 'number', number, 'image', image, 'game', game,
           'jp', language = 'japanese', 'grade', grade, 'qty', qty,
           'value', case when v.show_values then val end)
         order by val desc nulls last, name), '[]'::jsonb),
         sum(val), sum(qty)
    into items, tot, n
  from (select * from x order by val desc nulls last, name limit 500) x;

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

  return jsonb_build_object(
    'slug', v.slug, 'title', v.title, 'bio', v.bio, 'contact', v.contact,
    'show_values', v.show_values, 'updated', v.updated_at,
    'count', coalesce(n, 0), 'total', case when v.show_values then coalesce(tot, 0) end,
    'cards', items, 'wishlist', coalesce(wish, '[]'::jsonb));
end;
$$;

notify pgrst, 'reload schema';
