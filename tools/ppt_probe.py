"""PokemonPriceTracker API keşif testi.

Birkaç farklı kart türü için API'nin ne döndürdüğünü (özellikle PSA fiyatlarını)
tools/out/probe.json dosyasına yazar. Kişisel veri (alış fiyatı, PSA numarası) içermez.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

KEY = os.environ.get("PPT_KEY", "")
BASE = "https://www.pokemonpricetracker.com/api/v2"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "probe.json")

QUERIES = [
    {"label": "EN modern SIR", "params": {"search": "espeon ex prismatic evolutions", "limit": 3, "includeEbay": "true"}},
    {"label": "EN trainer gallery", "params": {"search": "umbreon vmax brilliant stars", "limit": 3, "includeEbay": "true"}},
    {"label": "EN mega", "params": {"search": "mega charizard x ex phantasmal flames", "limit": 3, "includeEbay": "true"}},
    {"label": "EN promo", "params": {"search": "charizard gx sm211", "limit": 3, "includeEbay": "true"}},
    {"label": "EN vintage 1st", "params": {"search": "dark hypno team rocket", "limit": 3, "includeEbay": "true"}},
    {"label": "JP modern", "params": {"search": "umbreon ex terastal festival", "language": "japanese", "limit": 3, "includeEbay": "true"}},
    {"label": "JP promo", "params": {"search": "pikachu yu nagaba", "language": "japanese", "limit": 3, "includeEbay": "true"}},
    {"label": "JP vintage", "params": {"search": "scyther vending", "language": "japanese", "limit": 3, "includeEbay": "true"}},
    {"label": "history", "params": {"search": "espeon ex prismatic evolutions", "limit": 1, "includeHistory": "true", "days": 30}},
]


def trim(obj, depth=0):
    if isinstance(obj, list):
        out = [trim(x, depth + 1) for x in obj[:6]]
        if len(obj) > 6:
            out.append(f"... {len(obj) - 6} öğe daha")
        return out
    if isinstance(obj, dict):
        return {k: trim(v, depth + 1) for k, v in obj.items()}
    if isinstance(obj, str) and len(obj) > 300:
        return obj[:300] + "..."
    return obj


def call(path, params):
    url = f"{BASE}/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {KEY}", "User-Agent": "KartRadari/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return {"status": r.status, "body": json.loads(r.read().decode("utf-8"))}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "body": e.read().decode("utf-8", "replace")[:1000]}
    except Exception as e:  # noqa: BLE001
        return {"status": None, "body": str(e)}


def main():
    if not KEY:
        raise SystemExit("PPT_KEY tanımlı değil")
    results = []
    for q in QUERIES:
        r = call("cards", q["params"])
        results.append({"label": q["label"], "params": q["params"], "status": r["status"], "body": trim(r["body"])})
        print(q["label"], r["status"])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
