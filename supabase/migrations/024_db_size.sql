-- Veritabanı boyutu kontrolü (ücretsiz planda sınır 500 MB). Yalnızca arka plan görevi okuyabilir.
-- Supabase → SQL Editor → bu dosyanın tamamını yapıştır → Run (bir kez)

create or replace function public.db_size() returns jsonb
language sql stable security definer set search_path = public, pg_catalog as $$
  select jsonb_build_object(
    'total_mb', round(pg_database_size(current_database()) / 1048576.0, 1),
    'tables', (select jsonb_object_agg(t.relname, round(pg_total_relation_size(t.oid) / 1048576.0, 1))
               from (select c.oid, c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace
                     where n.nspname = 'public' and c.relkind = 'r'
                     order by pg_total_relation_size(c.oid) desc limit 8) t));
$$;
revoke all on function public.db_size() from public, anon, authenticated;
grant execute on function public.db_size() to service_role;

notify pgrst, 'reload schema';

-- Şu anki boyutu hemen göster
select public.db_size();
