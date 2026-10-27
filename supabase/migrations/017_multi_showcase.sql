-- Birden fazla vitrin: her kullanıcı istediği kadar vitrin açabilir (ör. her klasör için ayrı bağlantı).
-- Her vitrinin kendi kodu ve bağlantısı vardır; eski vitrin ve bağlantısı aynen çalışmaya devam eder.
-- Supabase → SQL Editor → bu dosyanın tamamını yapıştır → Run (bir kez)

alter table public.showcases add column if not exists id uuid not null default gen_random_uuid();
alter table public.showcases add column if not exists created_at timestamptz not null default now();
alter table public.showcases drop constraint if exists showcases_pkey;
alter table public.showcases add primary key (id);
create index if not exists showcases_user_idx on public.showcases (user_id);

-- Kullanıcı başına en fazla 20 vitrin
create or replace function public.showcases_limit() returns trigger
language plpgsql as $$
begin
  if (select count(*) from public.showcases where user_id = new.user_id) >= 20 then
    raise exception 'En fazla 20 vitrin açılabilir.' using errcode = '22023';
  end if;
  return new;
end $$;
drop trigger if exists showcases_limit on public.showcases;
create trigger showcases_limit before insert on public.showcases
  for each row execute function public.showcases_limit();

-- Bir klasör silinirse o klasörü gösteren vitrin kapanır (yoksa tüm kartları göstermeye başlardı)
create or replace function public.folders_close_showcases() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  update public.showcases set enabled = false, folder_id = null where folder_id = old.id;
  return old;
end $$;
drop trigger if exists folders_close_showcases on public.folders;
create trigger folders_close_showcases before delete on public.folders
  for each row execute function public.folders_close_showcases();

notify pgrst, 'reload schema';
