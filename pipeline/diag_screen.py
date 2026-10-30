"""Teşhis: takip edilen kartlarda haftalık satış ortalamaları ve adetleri (piyasa verisi; kişisel veri yok)."""
import json, os, sys
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(__file__))
import build_pages as b  # noqa: E402
cards = b.sb_all("cards", {"select": "id,name,set_name,number,game,sales", "sales": "not.is.null"})
T = date.today()
weeks = [((T - timedelta(days=7 * (i + 1))).isoformat(), (T - timedelta(days=7 * i)).isoformat()) for i in range(4)][::-1]
out = []
for c in cards:
    hist = {}
    try:
        for p in b.sb_all("card_prices", {"select": "date,raw,psa10,psa9,grades", "card_id": f"eq.{c['id']}", "date": f"gte.{(T - timedelta(days=200)).isoformat()}", "order": "date.asc"}):
            hist[p["date"]] = p
    except Exception:  # noqa: BLE001
        pass
    for k, g in ((c.get("sales") or {}).get("g") or {}).items():
        W = []
        for a, z in weeks:
            x = [d for d in (g.get("d") or []) if a <= d[0] < z]
            n = sum(d[1] for d in x)
            W.append([n, round(sum(d[1] * d[2] for d in x) / n, 2) if n else None])
        if sum(w[0] for w in W) < 8:
            continue
        def gv(p):
            if not p: return None
            if k in ("psa10", "psa9") and p.get(k) is not None: return p[k]
            return ((p.get("grades") or {}).get(k) or {}).get("p")
        ds = sorted(hist)
        old = next((gv(hist[d]) for d in ds if gv(hist[d]) is not None), None)
        out.append({"name": c["name"], "set": c["set_name"], "num": c["number"], "game": c["game"], "grade": k, "weeks": W,
                    "first": old, "first_date": next((d for d in ds if gv(hist[d]) is not None), None), "trend": g.get("trend"), "n_all": g.get("n")})
json.dump({"weeks": weeks, "rows": out}, open(os.environ["DIAG_FILE"], "w"), ensure_ascii=False)
print(len(out))
