-- Vitrinde gösterilecek fiyatı vitrin sahibi seçer:
--   market: her kartta güncel piyasa değeri ve vitrinin toplamı (satılık kartlarda da; satış fiyatı gizli)
--   ask:    satılık kartlarda senin satış fiyatın (istersen yanında piyasa referansı); diğer kartlarda fiyat yok
--   none:   fiyat gösterilmez
-- Supabase → SQL Editor → bu dosyanın tamamını yapıştır → Run (bir kez)

alter table public.showcases add column if not exists price_mode text check (price_mode in ('market', 'ask', 'none'));
update public.showcases set price_mode = case when only_for_sale then 'ask' when show_values then 'market' else 'none' end
where price_mode is null;

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
  pm text;
begin
  if key = '' then return null; end if;
  select * into v from public.showcases where code = key and enabled;
  if not found then
    select * into v from public.showcases where slug = key and enabled;
  end if;
  if not found then return null; end if;
  pm := coalesce(v.price_mode, case when v.show_values then 'market' else 'none' end);
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
           'value', case when pm = 'market' then val end,
           'sale', for_sale,
           'ask', case when for_sale and pm = 'ask' then ask_price end,
           'ccy', case when for_sale and pm = 'ask' then ask_ccy end,
           'note', case when for_sale then sale_note end,
           'sold', for_sale and sold_at is not null,
           'market', case when for_sale and pm = 'ask' and v.show_market then round(unit, 2) end)
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
    'show_values', pm = 'market', 'price_mode', pm, 'show_market', v.show_market, 'only_for_sale', v.only_for_sale,
    'updated', v.updated_at, 'fx', fx,
    'count', coalesce(n, 0), 'for_sale', coalesce(nsale, 0),
    'total', case when pm = 'market' then coalesce(tot, 0) end,
    'cards', items, 'wishlist', coalesce(wish, '[]'::jsonb));
end;
$$;

revoke all on function public.showcase(text) from public;
grant execute on function public.showcase(text) to anon, authenticated;

notify pgrst, 'reload schema';
