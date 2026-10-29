"""Teşhis: cards.sales sütunu var mı, kaç kartta dolu (yalnızca sayılar)."""
import json, os, urllib.request, urllib.error
SUPA = os.environ["SUPABASE_URL"].rstrip("/"); KEY = os.environ["SUPABASE_SECRET_KEY"]
H = {"apikey": KEY, "Prefer": "count=exact", "Range": "0-0"}
if KEY.startswith("ey"): H["Authorization"] = "Bearer " + KEY
def cnt(q):
    try:
        with urllib.request.urlopen(urllib.request.Request(f"{SUPA}/rest/v1/{q}", headers=H), timeout=60) as r:
            return r.headers.get("Content-Range")
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}: {e.read().decode()[:200]}"
out = {"cards_total": cnt("cards?select=id"), "cards_with_sales": cnt("cards?select=id&sales=not.is.null"),
       "ppt_cards": cnt("cards?select=id&source=eq.ppt"), "priced_today": cnt("cards?select=id&source=eq.ppt&last_priced=gte.2026-10-29"),
       "search_fn_021": cnt("rpc/search_cards?q=&lim=1")}
json.dump(out, open(os.environ["DIAG_FILE"], "w"), indent=1); print(out)
