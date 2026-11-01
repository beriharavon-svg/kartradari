"""Teşhis: Japonca Reshiram GX 060/053 (SM6a, HR) için fiyat kaynağından PSA satış özeti (2 kredi)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import build_pages as b  # noqa: E402
import sync_psa as s  # noqa: E402
cat = b.sb("catalog", {"select": "product_id,name,set_name,number,market", "game": "eq.Pokemon JP", "name": "ilike.Reshiram GX*", "set_name": "ilike.*Dragon Storm*"})
out = {"catalog": cat, "ppt": []}
for c in cat:
    body = s.http("GET", f"{s.PPT}/cards?tcgPlayerId={c['product_id']}&language=japanese&includeEbay=true&limit=1", {"Authorization": f"Bearer {s.PKEY}"}) or {}
    d = body.get("data"); d = d[0] if isinstance(d, list) and d else (d if isinstance(d, dict) else {})
    sm = s.sales_summary((d or {}).get("ebay")) or {}
    out["ppt"].append({"pid": c["product_id"], "name": (d or {}).get("name"), "set": (d or {}).get("setName"),
                       "raw": ((d or {}).get("prices") or {}).get("market"),
                       "grades": {k: {x: v.get(x) for x in ("n", "med", "min", "max", "last", "trend")} | {"d": v.get("d")} for k, v in (sm.get("g") or {}).items() if k in ("psa10", "psa9", "bgs9_5", "cgc10")}})
json.dump(out, open(os.environ["DIAG_FILE"], "w"), ensure_ascii=False, indent=1); print("ok")
