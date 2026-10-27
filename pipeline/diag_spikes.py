"""Tek seferlik teşhis: belirli bir tarih aralığında fiyatı bir günlüğüne sıçrayan kartları bulur.
Yalnızca kart kataloğu ve günlük fiyatlara bakar; kimin portföyünde olduğuna bakmaz.
Çıktı: DIAG_FILE (json)."""
import json, os, statistics, urllib.parse, urllib.request

SUPA = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SECRET_KEY"]
FROM, TO = os.environ.get("DIAG_FROM", "2026-09-10"), os.environ.get("DIAG_TO", "2026-10-27")
H = {"apikey": KEY, "Content-Type": "application/json"}
if KEY.startswith("ey"):
    H["Authorization"] = "Bearer " + KEY


def get(path, params):
    out, off = [], 0
    while True:
        q = urllib.parse.urlencode(params)
        req = urllib.request.Request(f"{SUPA}/rest/v1/{path}?{q}", headers={**H, "Range": f"{off}-{off+999}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            rows = json.loads(r.read())
        out += rows
        if len(rows) < 1000:
            return out
        off += 1000


rows = get("card_prices", {"select": "card_id,date,raw,psa10,psa9,grades,psa10_n,psa9_n,psa10_conf",
                            "and": f"(date.gte.{FROM},date.lte.{TO})", "order": "card_id,date"})
series = {}
for r in rows:
    vals = {"raw": r.get("raw"), "psa10": r.get("psa10"), "psa9": r.get("psa9")}
    for k, g in (r.get("grades") or {}).items():
        if isinstance(g, dict) and g.get("p") is not None and k not in vals:
            vals[k] = g.get("p")
    for k, v in vals.items():
        if v is not None:
            series.setdefault((r["card_id"], k), []).append((r["date"], float(v), r))

found = []
for (cid, k), s in series.items():
    for i, (d, v, r) in enumerate(s):
        nb = [x[1] for x in s[max(0, i - 4):i] + s[i + 1:i + 5]]
        if len(nb) < 3:
            continue
        m = statistics.median(nb)
        if m > 0 and (v / m >= 1.8 or v / m <= 0.55) and abs(v - m) >= 150:
            found.append({"card_id": cid, "grade": k, "date": d, "value": v, "normal": round(m, 2),
                          "jump": round(v - m, 2), "n": r.get(k + "_n") if k in ("psa10", "psa9") else ((r.get("grades") or {}).get(k) or {}).get("n"),
                          "around": [(x[0], x[1]) for x in s[max(0, i - 3):i + 4]]})
found.sort(key=lambda x: -abs(x["jump"]))
found = found[:40]
ids = sorted({f["card_id"] for f in found})
cards = {c["id"]: c for c in (get("cards", {"select": "id,name,set_name,number,game", "id": f"in.({','.join(map(str, ids))})"}) if ids else [])}
for f in found:
    c = cards.get(f["card_id"], {})
    f["card"] = f'{c.get("name")} · {c.get("set_name")} · {c.get("number")}'
json.dump({"range": [FROM, TO], "rows_checked": len(rows), "spikes": found}, open(os.environ["DIAG_FILE"], "w"), ensure_ascii=False, indent=1)
print(len(rows), "satır,", len(found), "sıçrama")
