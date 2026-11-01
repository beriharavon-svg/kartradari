"""Teşhis: tek kartın PSA 10 günlük satışları (piyasa verisi)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import build_pages as b  # noqa: E402
cs = b.sb_all("cards", {"select": "id,ext_id,name,set_name,number,language,sales,last_priced", "name": "ilike.Psyduck*", "set_name": "ilike.*Promo*"})
out = []
for c in cs:
    g = ((c.get("sales") or {}).get("g") or {})
    pr = b.sb_all("card_prices", {"select": "date,psa10,psa10_n,psa10_conf", "card_id": f"eq.{c['id']}", "order": "date.asc"})
    out.append({"card": {k: c[k] for k in ("id", "ext_id", "name", "set_name", "number", "language", "last_priced")},
                "psa10": {k: v for k, v in (g.get("psa10") or {}).items()}, "psa9": {k: (g.get("psa9") or {}).get(k) for k in ("n", "med", "min", "max")},
                "range": [(c.get("sales") or {}).get("from"), (c.get("sales") or {}).get("to")], "prices": pr})
json.dump(out, open(os.environ["DIAG_FILE"], "w"), ensure_ascii=False, indent=1); print(len(out))
