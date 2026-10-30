"""Teşhis: tek bir kartın piyasa verisi (katalog/fiyat/satış; kişisel veri yok)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import build_pages as b  # noqa: E402
cards = b.sb_all("cards", {"select": "id,source,ext_id,name,set_name,number,sales", "name": "ilike.*Mega Charizard X ex*", "number": "ilike.*125*"})
out = []
for c in cards:
    pr = b.sb_all("card_prices", {"select": "date,raw,psa10,psa10_n,psa10_conf,psa9,psa9_n,grades", "card_id": f"eq.{c['id']}", "order": "date.asc"})
    cat = b.sb("catalog", {"select": "product_id,market,low,price_date,sub_type", "product_id": f"eq.{c['ext_id']}"}) if str(c["ext_id"]).isdigit() else []
    out.append({"card": {k: c[k] for k in ("id", "source", "ext_id", "name", "set_name", "number")}, "sales": c.get("sales"), "catalog": cat,
                "prices": [{k: v for k, v in p.items() if k != "grades"} | {"g": {k: v for k, v in (p.get("grades") or {}).items() if k in ("psa10", "psa9", "bgs10", "bgs9_5", "cgc10", "tag10")}} for p in pr]})
json.dump(out, open(os.environ["DIAG_FILE"], "w"), indent=1, ensure_ascii=False); print(len(out))
