"""Teşhis: Reshiram GX kartları (katalog + takip edilen kartların PSA satışları)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import build_pages as b  # noqa: E402
cat = b.sb("catalog", {"select": "product_id,game,name,set_name,number,rarity,market,released", "name": "ilike.Reshiram*GX*", "order": "market.desc.nullslast", "limit": "40"})
ids = [str(c["product_id"]) for c in cat]
cards = b.sb("cards", {"select": "id,ext_id,name,set_name,number,language,sales", "ext_id": f"in.({','.join(ids)})"}) if ids else []
by = {c["ext_id"]: c for c in cards}
out = []
for c in cat:
    k = by.get(str(c["product_id"]))
    g = ((k or {}).get("sales") or {}).get("g") or {}
    out.append({**c, "tracked": bool(k), "psa10": {x: (g.get("psa10") or {}).get(x) for x in ("n", "med", "min", "max", "last", "trend")},
                "psa10_d": (g.get("psa10") or {}).get("d"), "psa9": {x: (g.get("psa9") or {}).get(x) for x in ("n", "med", "last")}})
json.dump(out, open(os.environ["DIAG_FILE"], "w"), ensure_ascii=False, indent=1); print(len(out))
