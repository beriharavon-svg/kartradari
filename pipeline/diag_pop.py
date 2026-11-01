"""Teşhis: PokemonPriceTracker nüfus (population) uç noktası planımızda açık mı? (1 istek)"""
import json, os, urllib.request, urllib.error
KEY = os.environ["PPT_KEY"]
out = {}
for tid in ("42382",):
    req = urllib.request.Request(f"https://www.pokemonpricetracker.com/api/v2/population?tcgPlayerId={tid}", headers={"Authorization": f"Bearer {KEY}"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = json.loads(r.read())
            def shape(v, d=0):
                if d > 4: return "…"
                if isinstance(v, dict): return {k: shape(v[k], d + 1) for k in list(v)[:25]}
                if isinstance(v, list): return {"_len": len(v), "_item": shape(v[0], d + 1) if v else None}
                return type(v).__name__
            out[tid] = {"status": r.status, "shape": shape(body)}
    except urllib.error.HTTPError as e:
        out[tid] = {"status": e.code, "body": e.read().decode("utf-8", "replace")[:300]}
json.dump(out, open(os.environ["DIAG_FILE"], "w"), indent=1); print(out)
