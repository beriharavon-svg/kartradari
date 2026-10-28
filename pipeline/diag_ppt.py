"""Tek seferlik teşhis: PokemonPriceTracker eBay verisinin YAPISINI çıkarır (alan adları, tipler, liste uzunlukları).
Değerleri değil yalnızca şemayı yazar; 1 kart, ~2 kredi."""
import json, os, urllib.parse, urllib.request

KEY = os.environ["PPT_KEY"]
TCG = os.environ.get("DIAG_TCG", "42382")   # örnek: Base Set Charizard
url = "https://www.pokemonpricetracker.com/api/v2/cards?" + urllib.parse.urlencode(
    {"tcgPlayerId": TCG, "includeEbay": "true", "includeHistory": "false", "limit": 1})
req = urllib.request.Request(url, headers={"Authorization": f"Bearer {KEY}"})
body = json.loads(urllib.request.urlopen(req, timeout=60).read())


def shape(v, depth=0):
    if depth > 5:
        return "…"
    if isinstance(v, dict):
        ks = list(v.keys())
        # derece anahtarları çoksa yalnızca birkaçını aç
        if len(ks) > 8 and all(isinstance(v[k], dict) for k in ks):
            return {"_keys": ks[:30], "_example(" + ks[0] + ")": shape(v[ks[0]], depth + 1)}
        return {k: shape(v[k], depth + 1) for k in ks}
    if isinstance(v, list):
        return {"_list_len": len(v), "_item": shape(v[0], depth + 1) if v else None}
    return type(v).__name__ + ("" if not isinstance(v, str) else f"(len {len(v)})")


d = (body.get("data") or [{}])
d = d[0] if isinstance(d, list) and d else d
out = {"top_keys": sorted(d.keys()), "ebay": shape(d.get("ebay")), "metadata": shape(body.get("metadata"))}
# satış listesi varsa, bir öğenin alan adları ve tarih aralığı (değer değil)
json.dump(out, open(os.environ["DIAG_FILE"], "w"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False)[:3000])
