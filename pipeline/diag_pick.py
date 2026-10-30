"""Teşhis: 2019 öncesi Pokemon kartlarında 250–550 $ aralığında, satışı düzenli derece/kartlar (piyasa verisi)."""
import json, os, sys
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(__file__))
import build_pages as b  # noqa: E402
cards = b.sb_all("cards", {"select": "id,ext_id,name,set_name,number,game,language,sales", "sales": "not.is.null", "source": "eq.ppt"})
pids = [c["ext_id"] for c in cards if str(c["ext_id"]).isdigit()]
rel = {}
for i in range(0, len(pids), 200):
    for r in b.sb("catalog", {"select": "product_id,released,market,game", "product_id": f"in.({','.join(pids[i:i + 200])})"}):
        rel[str(r["product_id"])] = r
T = date.today(); c30 = (T - timedelta(days=30)).isoformat(); c15 = (T - timedelta(days=15)).isoformat()
out = []
for c in cards:
    r = rel.get(str(c["ext_id"])) or {}
    if not r.get("released") or r["released"] >= "2019-01-01":
        continue
    for k, g in ((c.get("sales") or {}).get("g") or {}).items():
        d = [x for x in (g.get("d") or []) if x[0] >= c30]
        n = sum(x[1] for x in d)
        if n < 4:
            continue
        a = [x for x in d if x[0] < c15]; z = [x for x in d if x[0] >= c15]
        wa = b.wmed(a) if a else None; wz = b.wmed(z) if z else None
        med = b.wmed(d)
        if not med or not (200 <= med <= 600):
            continue
        out.append({"name": c["name"], "set": c["set_name"], "num": c["number"], "lang": c["language"], "rel": r["released"],
                    "grade": b.grade_label(k), "n30": n, "med30": med, "first15": wa, "last15": wz,
                    "chg": round((wz / wa - 1) * 100, 1) if wa and wz else None, "trend": g.get("trend"), "raw": r.get("market"),
                    "min": g.get("min"), "max": g.get("max"), "last": g.get("last")})
out.sort(key=lambda x: -x["n30"])
json.dump(out, open(os.environ["DIAG_FILE"], "w"), ensure_ascii=False); print(len(out))
