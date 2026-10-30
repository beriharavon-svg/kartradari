-- Kart eklerken öneriden seçilen kartın katalog numarası (TCGplayer ürün no). Varsa eşleştirme tahmin yapmaz, doğrudan o kartı alır.
-- Supabase → SQL Editor → bu dosyanın tamamını yapıştır → Run (bir kez)

alter table public.holdings add column if not exists product_id bigint;

-- Kart bilgisi ya da seçilen katalog kartı değişirse yeniden eşleştirilsin
create or replace function public.holdings_rematch() returns trigger
language plpgsql as $$
begin
  if (new.name_input, new.set_input, new.number_input, new.language, new.game, new.product_id)
     is distinct from (old.name_input, old.set_input, old.number_input, old.language, old.game, old.product_id) then
    new.card_id := null;
    new.match_status := 'pending';
    new.match_note := null;
  end if;
  if new.bought is distinct from old.bought then
    new.buy_fx := null;
  end if;
  if new.cert is distinct from old.cert then
    new.psa := null; new.psa_front := null; new.psa_back := null; new.psa_checked := null; new.psa_status := null;
  end if;
  return new;
end $$;

notify pgrst, 'reload schema';
