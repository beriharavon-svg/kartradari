"""Tek seferlik: takip edilen kartların eBay satış özetini (cards.sales) hemen doldurur. Kart başına ~2 kredi."""
import json, os, sys, time, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(__file__))
import sync_psa as s  # noqa: E402

cards = s.sb("GET", "cards", {"select": "id,ext_id,language", "source": "eq.ppt", "sales": "is.null", "limit": "500"}) or []
done, fails = 0, []
for c in cards:
    try:
        url = f"{s.PPT}/cards?" + urllib.parse.urlencode({"tcgPlayerId": c["ext_id"], "language": c.get("language") or "english",
                                                         "includeEbay": "true", "limit": 1})
        time.sleep(1.1)
        body = s.http("GET", url, {"Authorization": f"Bearer {s.PKEY}"}) or {}
        d = body.get("data")
        d = d[0] if isinstance(d, list) and d else (d if isinstance(d, dict) else {})
        sm = s.sales_summary(d.get("ebay"))
        if sm:
            s.sb("PATCH", "cards", {"id": f"eq.{c['id']}"}, {"sales": sm})
            done += 1
    except Exception as e:  # noqa: BLE001
        fails.append(str(e)[:150])
out = {"cards": len(cards), "filled": done, "failed": len(fails), "examples": fails[:3]}
json.dump(out, open(os.environ["DIAG_FILE"], "w"), indent=1)
print(out)
