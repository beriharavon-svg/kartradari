"""Teşhis: piyasa sayfasında kaç kart çıkacağını sayar (yalnızca sayılar)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import build_pages as b  # noqa: E402
cards = b.sb_all("cards", {"select": "id,sales", "sales": "not.is.null"})
grades = ms = ups = downs = 0
days_span = []
for c in cards:
    for k, g in ((c.get("sales") or {}).get("g") or {}).items():
        grades += 1
        if g.get("d"):
            days_span.append(len(g["d"]))
        m = b.momentum(g)
        if m:
            ms += 1
            ups += m["pct"] >= 10
            downs += m["pct"] <= -10
out = {"cards": len(cards), "card_grades": grades, "with_momentum": ms, "rising": ups, "falling": downs,
       "max_days": max(days_span or [0]), "median_days": sorted(days_span)[len(days_span) // 2] if days_span else 0}
json.dump(out, open(os.environ["DIAG_FILE"], "w"), indent=1); print(out)
