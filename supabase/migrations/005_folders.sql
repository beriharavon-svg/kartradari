-- Portföy klasörleri: kullanıcı kendi başlıklarını açar, kartlarını içine koyar.
-- Bir kart birden fazla klasörde olabilir. Klasörler yalnızca sahibine görünür.
-- Supabase → SQL Editor → bu dosyanın tamamını yapıştır → Run (bir kez)

create table if not exists public.folders (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  name text not null check (char_length(btrim(name)) between 1 and 40),
  position integer not null default 0,
  created_at timestamptz not null default now(),
  unique (user_id, name)
);

create table if not exists public.folder_items (
  folder_id uuid not null references public.folders(id) on delete cascade,
  holding_id uuid not null references public.holdings(id) on delete cascade,
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  added_at timestamptz not null default now(),
  primary key (folder_id, holding_id)
);
create index if not exists folder_items_holding_idx on public.folder_items (holding_id);
create index if not exists folders_user_idx on public.folders (user_id);

alter table public.folders enable row level security;
alter table public.folder_items enable row level security;

drop policy if exists folders_owner on public.folders;
create policy folders_owner on public.folders for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

-- Klasör de kart da aynı kullanıcıya ait olmalı.
drop policy if exists folder_items_owner on public.folder_items;
create policy folder_items_owner on public.folder_items for all to authenticated
  using (user_id = auth.uid())
  with check (
    user_id = auth.uid()
    and exists (select 1 from public.folders f where f.id = folder_id and f.user_id = auth.uid())
    and exists (select 1 from public.holdings h where h.id = holding_id and h.user_id = auth.uid())
  );

revoke all on public.folders, public.folder_items from anon;
grant select, insert, update, delete on public.folders, public.folder_items to authenticated;
grant all on public.folders, public.folder_items to service_role;

notify pgrst, 'reload schema';
