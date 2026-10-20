-- Satılık kartlar: satıcı kartına fiyat ve not yazar, vitrinde alıcı WhatsApp ya da Instagram'dan satıcıya ulaşır.
-- Holotique satışa aracılık etmez; ödeme ve teslimat tamamen taraflar arasındadır.
-- Supabase → SQL Editor → bu dosyanın tamamını yapıştır → Run (bir kez)

-- 1) Kart başına satış bilgisi (yalnızca sahibi düzenler; vitrin açıksa satış bilgisi orada görünür)
alter table public.holdings add column if not exists for_sale boolean not null default false;
alter table public.holdings add column if not exists ask_price numeric check (ask_price is null or ask_price >= 0);
alter table public.holdings add column if not exists ask_ccy text not null default 'TRY' check (ask_ccy in ('TRY', 'USD', 'EUR', 'GBP'));
alter table public.holdings add column if not exists sale_note text check (sale_note is null or char_length(sale_note) <= 140);
alter table public.holdings add column if not exists sold_at timestamptz;

-- 2) Vitrin ayarları
alter table public.showcases add column if not exists only_for_sale boolean not null default false;
alter table public.showcases add column if not exists show_market boolean not null default true;
alter table public.showcases add column if not exists whatsapp text check (whatsapp is null or whatsapp ~ '^[0-9]{8,15}$');
alter table public.showcases add column if not exists instagram text check (instagram is null or instagram ~ '^[A-Za-z0-9._]{1,30}$');
alter table public.showcases add column if not exists contact_clicks integer not null default 0;

-- 3) Anonim sayaç: alıcı satıcıya yazmak için tıkladığında (kim olduğu tutulmaz)
alter table public.events drop constraint if exists events_kind_check;
alter table public.events add constraint events_kind_check check (kind in ('search', 'view', 'contact'));

create or replace function public.showcase_contact(s text, ch text) returns void
language plpgsql security definer set search_path = public as $$
declare
  key text := lower(split_part(btrim(coalesce(s, ''), '/ '), '/', 1));
begin
  if ch not in ('wa', 'ig') or key = '' then return; end if;
  update public.showcases set contact_clicks = contact_clicks + 1 where code = key and enabled;
  if found then
    insert into public.events (kind, q, game) values ('contact', ch, left(key, 40));
  end if;
end;
$$;

-- 4) Herkese açık vitrin (satış bilgisiyle)
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
  update public.showcases set views = views + 1 where user_id = v.user_id;

  with x as (
    select coalesce(k.name, h.name_input) as name, coalesce(k.set_name, h.set_input) as set_name,
           coalesce(k.number, h.number_input) as number, coalesce(k.image_cached, k.image) as image, h.game, h.language, h.grade, h.qty,
           public._holding_price(h.card_id, h.grade) as unit,
           h.for_sale, h.ask_price, h.ask_ccy, h.sale_note, h.sold_at
    from public.holdings h left join public.cards k on k.id = h.card_id
    where h.user_id = v.user_id
      and (v.folder_id is null
           or exists (select 1 from public.folder_items fi where fi.folder_id = v.folder_id and fi.holding_id = h.id))
      and (not v.only_for_sale or h.for_sale)
      -- satılan kartlar 14 gün "Satıldı" etiketiyle görünür, sonra vitrinden düşer
      and (h.sold_at is null or h.sold_at > now() - interval '14 days')
  ), y as (
    select *, round(unit * qty, 2) as val from x
  )
  select coalesce(jsonb_agg(jsonb_build_object(
           'name', name, 'set', set_name, 'number', number, 'image', image, 'game', game,
           'jp', language = 'japanese', 'grade', grade, 'qty', qty,
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

revoke all on function public.showcase_contact(text, text) from public;
grant execute on function public.showcase_contact(text, text) to anon, authenticated;
revoke all on function public.showcase(text) from public;
grant execute on function public.showcase(text) to anon, authenticated;

notify pgrst, 'reload schema';
