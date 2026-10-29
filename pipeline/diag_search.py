"""Teşhis: arama RPC'sini herkese açık anahtarla çağırır, hata ve süreyi yazar (kişisel veri okumaz)."""
import json, os, time, urllib.request, urllib.error
SUPA = os.environ["SUPABASE_URL"].rstrip("/")
PUB = "sb_publishable_IFtbpaxlRhYiB7kjJydiIA_ilx0aRI1"
out = []
for body in ({"q": "", "g": None, "gid": None, "sort": "relevance", "lim": 5, "off": 0},
             {"q": "charizard", "g": None, "gid": None, "sort": "relevance", "lim": 5, "off": 0},
             {"q": "", "g": None, "lim": 2000, "_fn": "search_sets"},
             {"q": "", "g": "Magic", "lim": 2000, "_fn": "search_sets"},
             {"q": "", "g": "Magic", "gid": None, "sort": "relevance", "lim": 48, "off": 0}):
    fn = body.pop("_fn", None) or ("search_cards" if "sort" in body else "search_catalog")
    t = time.time()
    req = urllib.request.Request(f"{SUPA}/rest/v1/rpc/{fn}", data=json.dumps(body).encode(), method="POST",
                                 headers={"apikey": PUB, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read())
            out.append({"fn": fn, "q": body["q"], "status": r.status, "rows": len(d) if isinstance(d, list) else type(d).__name__,
                        "keys": sorted(d[0].keys())[:30] if isinstance(d, list) and d else None, "sec": round(time.time() - t, 2)})
    except urllib.error.HTTPError as e:
        out.append({"fn": fn, "q": body["q"], "status": e.code, "error": e.read().decode("utf-8", "replace")[:500], "sec": round(time.time() - t, 2)})
    except Exception as e:  # noqa: BLE001
        out.append({"fn": fn, "q": body["q"], "error": str(e)[:300], "sec": round(time.time() - t, 2)})
json.dump(out, open(os.environ["DIAG_FILE"], "w"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False))
