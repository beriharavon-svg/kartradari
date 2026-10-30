"""Teşhis: piyasa takibi sonrası sayılar ve veritabanı boyutu (kişisel veri yok)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import build_pages as b  # noqa: E402
import sync_psa as s  # noqa: E402
out = {}
try:
    out["db_size"] = s.sb("POST", "rpc/db_size", body={})
except Exception as e:  # noqa: BLE001
    out["db_size"] = str(e)[:150]
cards = b.sb_all("cards", {"select": "id,sales", "sales": "not.is.null"})
cnt = {"cards_with_sales": len(cards)}
by = {}
for c in cards:
    for k, g in ((c.get("sales") or {}).get("g") or {}).items():
        gk = b.ggroup(k)
        d = by.setdefault(gk, {"grades": 0, "momentum": 0, "up": 0, "down": 0, "steady": 0})
        d["grades"] += 1
        m = b.momentum(g, (c.get("sales") or {}).get("from"))
        if m:
            d["momentum"] += 1; d["up"] += m["pct"] >= 10; d["down"] += m["pct"] <= -10
        if b.steadying(g):
            d["steady"] += 1
out["counts"] = cnt; out["by_grade"] = by
json.dump(out, open(os.environ["DIAG_FILE"], "w"), indent=1, ensure_ascii=False); print(out)
