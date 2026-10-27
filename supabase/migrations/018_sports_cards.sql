-- Spor kartları: elle eklenen kartlar (oyuncu, yıl/set, numara, paralel), kullanıcının kendi fotoğrafı ve elle girilen değer.
-- Bu kartlar katalogla eşleştirilmez (durum: 'manual'); değerlerini kullanıcı belirler.
-- Supabase → SQL Editor → bu dosyanın tamamını yapıştır → Run (bir kez)

alter table public.holdings add column if not exists sport text check (sport is null or char_length(sport) <= 30);
alter table public.holdings add column if not exists variant text check (variant is null or char_length(variant) <= 80);
alter table public.holdings add column if not exists photo_url text check (photo_url is null or photo_url ~ '^https://');
alter table public.holdings add column if not exists manual_value numeric check (manual_value is null or manual_value >= 0);

-- Spor kartları her zaman 'manual' kalır (eşleştirme görevi bunlara dokunmaz).
-- Ad "z" ile başlıyor ki diğer tetikleyicilerden (ör. holdings_rematch) sonra çalışsın.
create or replace function public.holdings_zmanual() returns trigger
language plpgsql as $$
begin
  if new.game = 'Sports' then
    new.match_status := 'manual';
    new.card_id := null;
    new.match_note := null;
  elsif tg_op = 'UPDATE' and old.match_status = 'manual' and new.match_status = 'manual' then
    new.match_status := 'pending';   -- spor kartı başka bir oyuna çevrildiyse normal eşleştirmeye dön
  end if;
  return new;
end $$;
drop trigger if exists holdings_zmanual on public.holdings;
create trigger holdings_zmanual before insert or update on public.holdings
  for each row execute function public.holdings_zmanual();

-- Kullanıcı fotoğrafları: herkese açık okunur, her kullanıcı yalnızca kendi klasörüne yazar
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('user-photos', 'user-photos', true, 3145728, array['image/jpeg', 'image/png', 'image/webp'])
on conflict (id) do update set public = true;

drop policy if exists "user-photos insert own" on storage.objects;
create policy "user-photos insert own" on storage.objects for insert to authenticated
  with check (bucket_id = 'user-photos' and (storage.foldername(name))[1] = auth.uid()::text);
drop policy if exists "user-photos update own" on storage.objects;
create policy "user-photos update own" on storage.objects for update to authenticated
  using (bucket_id = 'user-photos' and (storage.foldername(name))[1] = auth.uid()::text);
drop policy if exists "user-photos delete own" on storage.objects;
create policy "user-photos delete own" on storage.objects for delete to authenticated
  using (bucket_id = 'user-photos' and (storage.foldername(name))[1] = auth.uid()::text);

-- Vitrin: spor kartlarının fotoğrafı ve elle girilen değeri de görünsün
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
           coalesce(k.number, h.number_input) as number, coalesce(h.photo_url, k.image_cached, k.image) as image, h.game, h.language, h.grade, h.qty,
           h.variant, h.sport,
           coalesce(public._holding_price(h.card_id, h.grade), h.manual_value) as unit,
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

notify pgrst, 'reload schema';
