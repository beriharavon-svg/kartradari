-- PSA sertifika verisi için yeni alanlar
-- Supabase → SQL Editor → bu dosyanın tamamını yapıştır → Run (bir kez)

alter table public.holdings
  add column if not exists psa jsonb,
  add column if not exists psa_front text,
  add column if not exists psa_back text,
  add column if not exists psa_checked date,
  add column if not exists psa_status text;

create or replace function public.holdings_rematch() returns trigger
language plpgsql as $$
begin
  if (new.name_input, new.set_input, new.number_input, new.language, new.game)
     is distinct from (old.name_input, old.set_input, old.number_input, old.language, old.game) then
    new.card_id := null;
    new.match_status := 'pending';
    new.match_note := null;
  end if;
  if new.bought is distinct from old.bought then
    new.buy_fx := null;
  end if;
  if new.cert is distinct from old.cert then
    new.psa := null;
    new.psa_front := null;
    new.psa_back := null;
    new.psa_checked := null;
    new.psa_status := null;
  end if;
  return new;
end $$;

notify pgrst, 'reload schema';
