-- Vitrin bağlantısı: holotique.com/v/<rastgele kimlik>/<vitrin adı>
-- Kimlik her vitrine bir kez verilir ve değişmez; addaki değişiklik eski bağlantıları bozmaz.
-- E-posta adresinden türetilen eski adresler de çalışmaya devam eder.
-- Supabase → SQL Editor → bu dosyanın tamamını yapıştır → Run (bir kez)

create or replace function public._rand_code(n integer default 7) returns text
language sql volatile as $$
  select string_agg(substr('abcdefghjkmnpqrstuvwxyz23456789', 1 + floor(random() * 31)::int, 1), '')
  from generate_series(1, n);
$$;

alter table public.showcases add column if not exists code text;
update public.showcases set code = public._rand_code() where code is null;
alter table public.showcases alter column code set default public._rand_code();
alter table public.showcases alter column code set not null;
create unique index if not exists showcases_code_key on public.showcases (code);

-- Eski kullanıcı seçimli adres artık zorunlu değil; boş bırakılırsa kimlik kullanılır.
alter table public.showcases alter column slug drop not null;
create or replace function public.showcases_defaults() returns trigger
language plpgsql as $$
begin
  if new.code is null then new.code := public._rand_code(); end if;
  if tg_op = 'UPDATE' then new.code := old.code; end if;  -- kimlik değiştirilemez
  if new.slug is null then new.slug := new.code; end if;
  return new;
end $$;
drop trigger if exists showcases_defaults on public.showcases;
create trigger showcases_defaults before insert or update on public.showcases
  for each row execute function public.showcases_defaults();

-- Herkese açık vitrin: "kimlik", "kimlik/ad" ya da eski adres kabul edilir
create or replace function public.showcase(s text) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  v public.showcases;
  key text := lower(split_part(btrim(coalesce(s, ''), '/ '), '/', 1));
  items jsonb;
  wish jsonb;
  tot numeric;
  n bigint;
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
    'code', v.code, 'slug', v.code, 'title', v.title, 'bio', v.bio, 'contact', v.contact,
    'show_values', v.show_values, 'updated', v.updated_at,
    'count', coalesce(n, 0), 'total', case when v.show_values then coalesce(tot, 0) end,
    'cards', items, 'wishlist', coalesce(wish, '[]'::jsonb));
end;
$$;

revoke all on function public._rand_code(integer) from public, anon;
grant execute on function public._rand_code(integer) to authenticated;
revoke all on function public.showcase(text) from public;
grant execute on function public.showcase(text) to anon, authenticated;

notify pgrst, 'reload schema';
