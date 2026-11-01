"""Teşhis: 2019 öncesi, PSA 10 son 30 gün ortancası 300–1200 $ olan kartlar (piyasa verisi)."""
import json, os, sys
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(__file__))
import build_pages as b  # noqa: E402
cards = b.sb_all("cards", {"select": "id,ext_id,name,set_name,number,game,language,sales", "sales": "not.is.null", "source": "eq.ppt"})
pids = [c["ext_id"] for c in cards if str(c["ext_id"]).isdigit()]
rel = {}
for i in range(0, len(pids), 200):
    for r in b.sb("catalog", {"select": "product_id,released,market,rarity", "product_id": f"in.({','.join(pids[i:i + 200])})"}):
        rel[str(r["product_id"])] = r
T = date.today(); c30 = (T - timedelta(days=30)).isoformat(); c15 = (T - timedelta(days=15)).isoformat()
out = []
for c in cards:
    r = rel.get(str(c["ext_id"])) or {}
    if not r.get("released") or r["released"] >= "2019-01-01":
        continue
    g = ((c.get("sales") or {}).get("g") or {}).get("psa10")
    if not g:
        continue
    d30 = [x for x in (g.get("d") or []) if x[0] >= c30]
    n = sum(x[1] for x in d30)
    med = b.wmed(d30) if d30 else None
    ref = med or g.get("med")
    if not ref or not (200 <= ref <= 2000):
        continue
    a = [x for x in d30 if x[0] < c15]; z = [x for x in d30 if x[0] >= c15]
    out.append({"name": c["name"], "set": c["set_name"], "num": c["number"], "lang": c["language"], "rel": r["released"], "rarity": r.get("rarity"),
                "n30": n, "med30": med, "med_all": g.get("med"), "n_all": g.get("n"), "first15": b.wmed(a) if a else None, "last15": b.wmed(z) if z else None,
                "min": g.get("min"), "max": g.get("max"), "last": g.get("last"), "trend": g.get("trend"), "raw": r.get("market"),
                "d60": [x for x in (g.get("d") or []) if x[0] >= (T - timedelta(days=60)).isoformat()]})
out.sort(key=lambda x: x["rel"])
json.dump(out, open(os.environ["DIAG_FILE"], "w"), ensure_ascii=False); print(len(out))
