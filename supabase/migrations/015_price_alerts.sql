-- Fiyat alarmı: istek listesindeki kart hedef fiyata (ya da altına) inince kullanıcıya bir kez mail gider.
-- Fiyat tekrar hedefin üstüne çıkarsa alarm sıfırlanır; sonraki inişte yeniden haber verilir.
-- Supabase → SQL Editor → bu dosyanın tamamını yapıştır → Run (bir kez)

alter table public.wishlist add column if not exists notify boolean not null default true;
alter table public.wishlist add column if not exists alert_sent_at timestamptz;
alter table public.wishlist add column if not exists alert_price numeric;

-- Fiyat görevi çağırır (yalnızca service_role): mail gönderilecek kartlar
create or replace function public.alerts_due()
returns table (wish_id uuid, email text, name text, set_name text, number text, image text, grade text,
               price numeric, target numeric, added_price numeric)
language plpgsql security definer set search_path = public, auth as $$
begin
  -- fiyatı yeniden hedefin üstüne çıkanların alarmını sıfırla
  update public.wishlist w set alert_sent_at = null, alert_price = null
  where w.alert_sent_at is not null and w.target_usd is not null
    and coalesce(public._holding_price(w.card_id, w.grade), 0) > w.target_usd;

  return query
  select w.id, u.email::text, coalesce(c.name, k.name), coalesce(c.set_name, k.set_name),
         coalesce(c.number, k.number), coalesce(k.image_cached, k.image, c.image), w.grade,
         round(p.price, 2), w.target_usd, w.added_price
  from public.wishlist w
  join auth.users u on u.id = w.user_id
  left join public.cards k on k.id = w.card_id
  left join public.catalog c on c.product_id = w.product_id
  cross join lateral (select public._holding_price(w.card_id, w.grade) as price) p
  where w.notify and w.target_usd is not null and w.alert_sent_at is null
    and p.price is not null and p.price <= w.target_usd
    and u.email is not null and u.email_confirmed_at is not null
  order by u.email, p.price desc
  limit 500;
end;
$$;

create or replace function public.alerts_mark_sent(ids uuid[]) returns void
language sql security definer set search_path = public as $$
  update public.wishlist w
  set alert_sent_at = now(), alert_price = public._holding_price(w.card_id, w.grade)
  where w.id = any(ids);
$$;

revoke all on function public.alerts_due() from public, anon, authenticated;
revoke all on function public.alerts_mark_sent(uuid[]) from public, anon, authenticated;
grant execute on function public.alerts_due() to service_role;
grant execute on function public.alerts_mark_sent(uuid[]) to service_role;

-- Kullanıcının listesi: alarm ayarı da dönsün
drop function if exists public.my_wishlist();
create function public.my_wishlist()
returns table (id uuid, product_id bigint, grade text, target_usd numeric, note text, card_id bigint,
               added_price numeric, created_at timestamptz, game text, name text, set_name text, number text,
               image text, url text, market numeric, source text, notify boolean, alert_sent_at timestamptz)
language sql stable security definer set search_path = public as $$
  select w.id, w.product_id, w.grade, w.target_usd, w.note, w.card_id, w.added_price, w.created_at,
         c.game, coalesce(c.name, k.name), coalesce(c.set_name, k.set_name), coalesce(c.number, k.number),
         coalesce(k.image_cached, k.image, c.image), coalesce(c.url, k.url), c.market, k.source,
         w.notify, w.alert_sent_at
  from public.wishlist w
  left join public.catalog c on c.product_id = w.product_id
  left join public.cards k on k.id = w.card_id
  where w.user_id = auth.uid()
  order by w.created_at desc;
$$;
revoke all on function public.my_wishlist() from public, anon;
grant execute on function public.my_wishlist() to authenticated;

notify pgrst, 'reload schema';
