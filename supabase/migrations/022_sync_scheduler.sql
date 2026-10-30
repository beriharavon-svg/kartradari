-- Zamanlayıcıyı GitHub'dan Supabase'e taşıma: fiyat/eşleştirme görevi (psa-sync) artık
--   * her 15 dakikada bir Supabase'in kendi zamanlayıcısıyla (pg_cron) başlatılır,
--   * kullanıcı yeni kart / istek listesi kartı eklediğinde de birkaç dakika içinde ayrıca başlatılır.
-- Görevi başlatmak için GitHub erişim anahtarı Supabase Vault'ta "github_dispatch_token" adıyla durur
-- (bu dosyada anahtar yok; anahtarı Vault ekranından sen eklersin).
-- Supabase → SQL Editor → bu dosyanın tamamını yapıştır → Run (bir kez)

create extension if not exists pg_net;
create extension if not exists pg_cron;

create table if not exists public.job_kick (
  id integer primary key default 1 check (id = 1),
  last_at timestamptz not null default '2000-01-01',
  last_reason text,
  last_request bigint
);
insert into public.job_kick (id) values (1) on conflict (id) do nothing;
alter table public.job_kick enable row level security;
revoke all on public.job_kick from anon, authenticated;

-- GitHub'daki görevi başlatır. Aynı görev 3 dakikadan sık başlatılmaz (zamanlayıcı her zaman başlatabilir).
create or replace function public.kick_sync(reason text default 'cron', force boolean default false) returns void
language plpgsql security definer set search_path = public, extensions as $$
declare
  tok text;
  rid bigint;
begin
  if not force and exists (select 1 from public.job_kick where id = 1 and last_at > now() - interval '3 minutes') then
    return;
  end if;
  select decrypted_secret into tok from vault.decrypted_secrets where name = 'github_dispatch_token' limit 1;
  if tok is null or tok = '' then return; end if;
  select net.http_post(
    url := 'https://api.github.com/repos/beriharavon-svg/kartradari/actions/workflows/psa-sync.yml/dispatches',
    headers := jsonb_build_object(
      'Authorization', 'Bearer ' || tok,
      'Accept', 'application/vnd.github+json',
      'X-GitHub-Api-Version', '2022-11-28',
      'User-Agent', 'holotique-supabase',
      'Content-Type', 'application/json'),
    body := '{"ref":"main"}'::jsonb
  ) into rid;
  update public.job_kick set last_at = now(), last_reason = left(reason, 40), last_request = rid where id = 1;
end $$;
revoke all on function public.kick_sync(text, boolean) from public, anon, authenticated;

-- Yeni kart eklenince (ya da kart bilgisi değişip yeniden eşleştirme gerekince) görevi hemen başlat.
-- Hata olursa (ör. anahtar yok) kart kaydı asla engellenmez.
create or replace function public.holdings_kick() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  if new.match_status = 'pending' then
    begin
      perform public.kick_sync('yeni kart', false);
    exception when others then null;
    end;
  end if;
  return null;
end $$;
drop trigger if exists holdings_kick on public.holdings;
create trigger holdings_kick after insert or update of name_input, set_input, number_input, game, language on public.holdings
  for each row execute function public.holdings_kick();

create or replace function public.wishlist_kick() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  begin
    perform public.kick_sync('istek listesi', false);
  exception when others then null;
  end;
  return null;
end $$;
drop trigger if exists wishlist_kick on public.wishlist;
create trigger wishlist_kick after insert on public.wishlist
  for each row execute function public.wishlist_kick();

-- Her 15 dakikada bir (GitHub'ın kendi zamanlayıcısı saatlerce gecikebiliyor)
select cron.unschedule(jobid) from cron.job where jobname = 'holotique-sync';
select cron.schedule('holotique-sync', '*/15 * * * *', $$select public.kick_sync('cron', true)$$);

-- Durum: son başlatma ve GitHub'ın yanıtı (204 = başarılı)
create or replace view public.job_kick_status as
  select k.last_at, k.last_reason, r.status_code, left(r.content::text, 200) as response, r.error_msg
  from public.job_kick k left join net._http_response r on r.id = k.last_request;
revoke all on public.job_kick_status from anon, authenticated;

-- Anahtar Vault'a eklendiyse ilk başlatmayı hemen yap
select public.kick_sync('kurulum', true);
