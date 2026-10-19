-- İstek listesi (sahip olmadığın ama takip ettiğin kartlar) ve herkese açık vitrin sayfası.
-- Gizlilik: istek listesi yalnızca sahibine görünür. Vitrin yalnızca kullanıcı açarsa yayına girer ve
-- alış fiyatı, alış tarihi, sertifika numarası ya da e-posta adresi İÇERMEZ.
-- Supabase → SQL Editor → bu dosyanın tamamını yapıştır → Run (bir kez)

-- 1) İstek listesi ---------------------------------------------------------------
create table if not exists public.wishlist (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  product_id bigint not null,
  grade text not null default 'Ham' check (char_length(grade) between 1 and 30),
  target_usd numeric check (target_usd is null or target_usd >= 0),
  note text check (note is null or char_length(note) <= 120),
  card_id bigint references public.cards(id),
  added_price numeric,
  created_at timestamptz not null default now(),
  unique (user_id, product_id, grade)
);
create index if not exists wishlist_user_idx on public.wishlist (user_id);
create index if not exists wishlist_card_idx on public.wishlist (card_id);

alter table public.wishlist enable row level security;
drop policy if exists wishlist_owner on public.wishlist;
create policy wishlist_owner on public.wishlist for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());
revoke all on public.wishlist from anon;
grant select, insert, update, delete on public.wishlist to authenticated;
grant all on public.wishlist to service_role;

-- Eklenen kart fiyat takibine alınır (fiyat görevi bundan sonra her gün fiyatlar).
create or replace function public.wishlist_track() returns trigger
language plpgsql security definer set search_path = public as $$
declare
  c public.catalog;
  src text;
  cid bigint;
begin
  if tg_op = 'INSERT' and (select count(*) from public.wishlist where user_id = new.user_id) >= 300 then
    raise exception 'İstek listesi en fazla 300 kart olabilir.' using errcode = '22023';
  end if;
  select * into c from public.catalog where product_id = new.product_id;
  if not found then
    raise exception 'Kart katalogda bulunamadı.' using errcode = '22023';
  end if;
  src := case when c.game in ('Pokemon', 'Pokemon JP') then 'ppt' else 'tcgcsv' end;
  if src = 'tcgcsv' then new.grade := 'Ham'; end if;  -- bu oyunlarda yalnızca ham fiyat var
  insert into public.cards (source, ext_id, game, language, name, set_name, number, rarity, image, url)
  values (src, c.product_id::text, case when c.game = 'Pokemon JP' then 'Pokemon' else c.game end,
          case when c.game = 'Pokemon JP' then 'japanese' else 'english' end,
          c.name, c.set_name, c.number, c.rarity, c.image, c.url)
  on conflict (source, ext_id) do update set image = coalesce(public.cards.image, excluded.image)
  returning id into cid;
  new.card_id := cid;
  if tg_op = 'INSERT' or new.grade is distinct from old.grade or new.product_id is distinct from old.product_id then
    new.added_price := coalesce(public._holding_price(cid, new.grade), case when new.grade = 'Ham' then c.market end);
  end if;
  return new;
end $$;
drop trigger if exists wishlist_track on public.wishlist;
create trigger wishlist_track before insert or update of product_id, grade on public.wishlist
  for each row execute function public.wishlist_track();

-- Kullanıcının kendi listesi, katalog bilgisiyle birlikte
create or replace function public.my_wishlist()
returns table (id uuid, product_id bigint, grade text, target_usd numeric, note text, card_id bigint,
               added_price numeric, created_at timestamptz, game text, name text, set_name text, number text,
               image text, url text, market numeric, source text)
language sql stable security definer set search_path = public as $$
  select w.id, w.product_id, w.grade, w.target_usd, w.note, w.card_id, w.added_price, w.created_at,
         c.game, coalesce(c.name, k.name), coalesce(c.set_name, k.set_name), coalesce(c.number, k.number),
         coalesce(k.image, c.image), coalesce(c.url, k.url), c.market, k.source
  from public.wishlist w
  left join public.catalog c on c.product_id = w.product_id
  left join public.cards k on k.id = w.card_id
  where w.user_id = auth.uid()
  order by w.created_at desc;
$$;

-- 2) Vitrin ------------------------------------------------------------------------
create table if not exists public.showcases (
  user_id uuid primary key default auth.uid() references auth.users(id) on delete cascade,
  slug text not null unique
    check (slug ~ '^[a-z0-9][a-z0-9_-]{2,23}$'
           and slug not in ('admin', 'api', 'www', 'holotique', 'destek', 'support', 'help', 'yonetim', 'vitrin', 'portfoy')),
  title text check (title is null or char_length(title) <= 60),
  bio text check (bio is null or char_length(bio) <= 280),
  contact text check (contact is null or char_length(contact) <= 80),
  enabled boolean not null default false,
  folder_id uuid references public.folders(id) on delete set null,
  show_values boolean not null default true,
  show_wishlist boolean not null default true,
  views integer not null default 0,
  updated_at timestamptz not null default now()
);
alter table public.showcases enable row level security;
drop policy if exists showcases_owner on public.showcases;
create policy showcases_owner on public.showcases for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());
revoke all on public.showcases from anon;
grant select, insert, update, delete on public.showcases to authenticated;
grant all on public.showcases to service_role;

create or replace function public.showcase_slug_free(s text) returns boolean
language sql stable security definer set search_path = public as $$
  select not exists (select 1 from public.showcases where slug = lower(btrim(s)) and user_id is distinct from auth.uid());
$$;

-- Herkese açık vitrin: yalnızca kart, derece, adet ve (sahibi izin verdiyse) güncel piyasa değeri
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
           coalesce(k.number, h.number_input) as number, k.image, h.game, h.language, h.grade, h.qty,
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
             'number', coalesce(c.number, k.number), 'image', coalesce(k.image, c.image),
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

-- 3) Yetkiler ----------------------------------------------------------------------
revoke all on function public.wishlist_track() from public, anon, authenticated;
revoke all on function public.my_wishlist() from public, anon;
revoke all on function public.showcase_slug_free(text) from public, anon;
revoke all on function public.showcase(text) from public;
grant execute on function public.my_wishlist() to authenticated;
grant execute on function public.showcase_slug_free(text) to authenticated;
grant execute on function public.showcase(text) to anon, authenticated;

notify pgrst, 'reload schema';
