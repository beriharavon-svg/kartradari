-- Yönetim paneli: kullanıcı listesi, portföy büyüklük dağılımı ve isimsiz portföyler.
-- İsimsiz portföylerde e-posta, alış fiyatı, alış tarihi ve sertifika numarası YOKTUR.
-- Kullanıcı listesinde kart sayısı gösterilmez (iki tablo eşleştirilip kimlik çıkarılamasın diye).
-- Supabase → SQL Editor → bu dosyanın tamamını yapıştır → Run (bir kez)

-- Kullanıcılar: yalnızca hesap bilgisi
create or replace function public.admin_users(lim integer default 200)
returns table (email text, created_at timestamptz, last_sign_in_at timestamptz, confirmed boolean)
language plpgsql stable security definer set search_path = public, auth as $$
begin
  perform public._require_admin();
  return query
  select u.email::text, u.created_at, u.last_sign_in_at, (u.email_confirmed_at is not null)
  from auth.users u order by u.created_at desc
  limit least(greatest(coalesce(lim, 200), 1), 1000);
end;
$$;

-- Portföy büyüklüğü dağılımı (kişi sayısı)
create or replace function public.admin_buckets()
returns table (dim text, bucket text, ord integer, users bigint)
language plpgsql stable security definer set search_path = public as $$
begin
  perform public._require_admin();
  return query
  with p as (
    select h.user_id, sum(h.qty) as qty,
           coalesce(sum(public._holding_price(h.card_id, h.grade) * h.qty), 0) as val
    from public.holdings h group by h.user_id
  )
  select 'cards', b.label, b.ord, count(p.user_id)
  from (values (1, '1–10', 1, 10), (2, '11–50', 11, 50), (3, '51–200', 51, 200), (4, '200+', 201, 1000000000))
       as b(ord, label, lo, hi)
  left join p on p.qty between b.lo and b.hi
  group by b.label, b.ord
  union all
  select 'value', b.label, b.ord, count(p.user_id)
  from (values (1, '$0–1K', 0, 1000), (2, '$1K–10K', 1000, 10000), (3, '$10K–50K', 10000, 50000), (4, '$50K+', 50000, 1e15))
       as b(ord, label, lo, hi)
  left join p on p.val >= b.lo and p.val < b.hi
  group by b.label, b.ord
  order by 1, 3;
end;
$$;

-- İsimsiz portföyler: rastgele kod + kartlar, derece, adet, güncel değer
create or replace function public.admin_portfolios(lim integer default 50)
returns table (code text, cards bigint, qty bigint, value numeric, games jsonb, graders jsonb, items jsonb)
language plpgsql stable security definer set search_path = public as $$
begin
  perform public._require_admin();
  return query
  with h as (
    select h.user_id, h.game, h.language, h.grade, h.qty, k.name, k.set_name, k.number, k.image,
           coalesce(k.name, h.name_input) as label,
           public._holding_price(h.card_id, h.grade) as price
    from public.holdings h left join public.cards k on k.id = h.card_id
  ),
  per as (
    select h.user_id,
      count(*) as cards, sum(h.qty)::bigint as qty, round(coalesce(sum(h.price * h.qty), 0), 2) as value,
      jsonb_agg(jsonb_build_object('name', h.label, 'set', h.set_name, 'number', h.number, 'image', h.image,
                                   'game', h.game, 'grade', h.grade, 'qty', h.qty,
                                   'value', round(h.price * h.qty, 2))
                order by h.price * h.qty desc nulls last) as items
    from h group by h.user_id
  )
  select left(md5(per.user_id::text || 'holotique-anon'), 6),
         per.cards, per.qty, per.value,
         (select jsonb_object_agg(g, n) from (select x.game || case when x.language = 'japanese' then ' (JP)' else '' end as g, count(*) as n
                                              from h x where x.user_id = per.user_id group by 1) gg),
         (select jsonb_object_agg(g, n) from (select case when x.grade = 'Ham' then 'Ham' else split_part(x.grade, ' ', 1) end as g, count(*) as n
                                              from h x where x.user_id = per.user_id group by 1) gr),
         per.items
  from per order by per.value desc
  limit least(greatest(coalesce(lim, 50), 1), 500);
end;
$$;

revoke all on function public.admin_users(integer) from public, anon;
revoke all on function public.admin_buckets() from public, anon;
revoke all on function public.admin_portfolios(integer) from public, anon;
grant execute on function public.admin_users(integer) to authenticated;
grant execute on function public.admin_buckets() to authenticated;
grant execute on function public.admin_portfolios(integer) to authenticated;

notify pgrst, 'reload schema';
