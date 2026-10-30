"""Teşhis: piyasa görevinin ilerlemesi (yalnızca sayılar)."""
import json, os, urllib.request
SUPA = os.environ["SUPABASE_URL"].rstrip("/"); KEY = os.environ["SUPABASE_SECRET_KEY"]
from datetime import datetime, timezone
T = datetime.now(timezone.utc).date().isoformat()
def get(q, cnt=False):
    h = {"apikey": KEY}
    if cnt: h.update({"Prefer": "count=exact", "Range": "0-0"})
    with urllib.request.urlopen(urllib.request.Request(f"{SUPA}/rest/v1/{q}", headers=h), timeout=60) as r:
        return r.headers.get("Content-Range") if cnt else json.loads(r.read())
out = {"utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
       "ppt_cards": get("cards?select=id&source=eq.ppt", True), "priced_today": get(f"cards?select=id&source=eq.ppt&last_priced=eq.{T}", True),
       "budget": get(f"job_state?select=key,value,updated_at&key=in.(ppt-market:{T},ppt:{T})")}
json.dump(out, open(os.environ["DIAG_FILE"], "w"), indent=1); print(out)
