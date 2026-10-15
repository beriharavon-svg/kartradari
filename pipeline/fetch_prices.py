"""KartRadarı günlük fiyat kaydı.

Her gün GitHub Actions tarafından çalıştırılır:
  1. pipeline/portfolio.json içindeki kartları TCGCSV (TCGplayer verisi) kataloğunda bulur.
  2. Bu kartların güncel piyasa fiyatlarını çeker.
  3. USD karşısında TRY, EUR, GBP, JPY, CNY kurlarını çeker (Frankfurter / ECB).
  4. docs/data/latest.json dosyasını yazar ve docs/data/history.json dosyasına o günün kaydını ekler.

Yalnızca Python standart kütüphanesi kullanılır.
"""

import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTFOLIO = os.path.join(ROOT, "pipeline", "portfolio.json")
CACHE = os.path.join(ROOT, "pipeline", "cache", "resolved.json")
DATA_DIR = os.path.join(ROOT, "docs", "data")
LATEST = os.path.join(DATA_DIR, "latest.json")
HISTORY = os.path.join(DATA_DIR, "history.json")

UA = "KartRadari/0.1 (+https://github.com/beriharavon-svg/kartradari)"
TCG = "https://tcgcsv.com/tcgplayer"
CURRENCIES = ["TRY", "EUR", "GBP", "JPY", "CNY"]
VARIANT_ORDER = [
    "Normal", "Holofoil", "Foil", "Unlimited Holofoil", "1st Edition Holofoil",
    "Unlimited", "1st Edition", "Reverse Holofoil",
]
GAME_ALIASES = {
    "pokemon": ["pokemon"],
    "magic": ["magic"],
    "yugioh": ["yugioh"],
    "onepiece": ["onepiececardgame", "onepiece"],
    "digimon": ["digimoncardgame", "digimon"],
    "dragonball": ["dragonballsuperfusionworld", "dragonballsuperccg", "dragonball"],
    "lorcana": ["lorcanatcg", "lorcana"],
}


def log(*a):
    print(*a, flush=True)


def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def norm_number(s):
    parts = re.split(r"/", str(s or "").strip().lower())
    out = []
    for p in parts:
        p = re.sub(r"\s", "", p)
        out.append(p.lstrip("0") or "0" if p.isdigit() else p)
    return "/".join(out)


def http_get(url, as_json=True, retries=3):
    last = None
    for attempt in range(retries):
        try:
            time.sleep(0.15)
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read().decode("utf-8")
            return json.loads(body) if as_json else body
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"İstek başarısız: {url}: {last}")


def results(payload):
    if isinstance(payload, dict):
        return payload.get("results") or []
    return payload or []


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, data, compact=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        if compact:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


# ---------- Kurlar ----------

def fetch_fx(date=None):
    path = date or "latest"
    urls = [
        f"https://api.frankfurter.dev/v1/{path}?base=USD&symbols={','.join(CURRENCIES)}",
        f"https://api.frankfurter.app/{path}?from=USD&to={','.join(CURRENCIES)}",
    ]
    for u in urls:
        try:
            d = http_get(u)
            rates = d.get("rates") or {}
            if all(c in rates for c in CURRENCIES):
                return {"date": d.get("date"), "rates": {c: rates[c] for c in CURRENCIES}}
        except Exception as e:  # noqa: BLE001
            log("Kur kaynağı yanıt vermedi:", u, e)
    return None


# ---------- Katalog eşleştirme ----------

class Catalog:
    def __init__(self):
        self._categories = None
        self._groups = {}
        self._products = {}

    def categories(self):
        if self._categories is None:
            self._categories = results(http_get(f"{TCG}/categories"))
        return self._categories

    def groups(self, cat_id):
        if cat_id not in self._groups:
            self._groups[cat_id] = results(http_get(f"{TCG}/{cat_id}/groups"))
        return self._groups[cat_id]

    def products(self, cat_id, group_id):
        key = (cat_id, group_id)
        if key not in self._products:
            self._products[key] = results(http_get(f"{TCG}/{cat_id}/{group_id}/products"))
        return self._products[key]

    def find_category(self, game):
        g = norm(game)
        wanted = GAME_ALIASES.get(g, [g])
        cats = self.categories()
        for w in wanted:
            for c in cats:
                if norm(c.get("name")) == w or norm(c.get("displayName")) == w:
                    return c
        hits = [c for c in cats if any(w in norm(c.get("name")) or w in norm(c.get("displayName")) for w in wanted)]
        hits.sort(key=lambda c: len(c.get("name") or ""))
        return hits[0] if hits else None

    def find_group(self, cat_id, set_name):
        s = norm(set_name)
        groups = self.groups(cat_id)
        exact = [g for g in groups if norm(g.get("name")) == s or norm(g.get("abbreviation")) == s]
        if exact:
            return exact[0]
        # "SV: Scarlet & Violet 151" gibi önekli adları da yakala
        # Yalnızca büyük harfli set kodu önekini at: "SV: Scarlet & Violet 151", "SWSH07: Evolving Skies"
        def stripped(name):
            return norm(re.sub(r"^[A-Z0-9]{1,8}:\s*", "", name or ""))
        exact2 = [g for g in groups if stripped(g.get("name")) == s]
        if exact2:
            return exact2[0]
        side = re.compile(r"commander|art series|tokens?|promos?|jumpstart|minigames|alchemy|front cards|oversized", re.I)
        hits = [g for g in groups if s and s in norm(g.get("name"))]
        hits.sort(key=lambda g: (bool(side.search(g.get("name") or "")), len(g.get("name") or "")))
        return hits[0] if hits else None

    def group_candidates(self, cat_id, set_name):
        s = norm(set_name)
        return [g.get("name") for g in self.groups(cat_id) if s and s in norm(g.get("name"))][:15]

    def find_product(self, cat_id, group_id, name, number):
        n = norm(name)
        num = norm_number(number) if number else None
        cands = []
        for p in self.products(cat_id, group_id):
            pname = norm(p.get("cleanName") or p.get("name"))
            if n and n not in pname:
                continue
            ext = {e.get("name"): e.get("value") for e in (p.get("extendedData") or [])}
            pnum = ext.get("Number")
            if num and norm_number(pnum) != num:
                continue
            cands.append(p)
        cands.sort(key=lambda p: (norm(p.get("cleanName") or p.get("name")) != n, len(p.get("name") or "")))
        return cands[0] if cands else None


def resolve(holding, catalog, cache):
    hid = holding["id"]
    sig = json.dumps({k: holding.get(k) for k in ("game", "set", "name", "number", "product_id")}, sort_keys=True)
    hit = cache.get(hid)
    if hit and hit.get("sig") == sig and hit.get("product_id"):
        return hit
    cat = catalog.find_category(holding["game"])
    if not cat:
        return {"sig": sig, "error": f"Oyun bulunamadı: {holding['game']}"}
    grp = catalog.find_group(cat["categoryId"], holding["set"])
    if not grp:
        return {"sig": sig, "error": f"Set bulunamadı: {holding['set']}"}
    prod = None
    if holding.get("product_id"):
        for p in catalog.products(cat["categoryId"], grp["groupId"]):
            if int(p.get("productId")) == int(holding["product_id"]):
                prod = p
                break
    else:
        prod = catalog.find_product(cat["categoryId"], grp["groupId"], holding["name"], holding.get("number"))
    if not prod:
        return {"sig": sig, "error": f"Kart bulunamadı: {holding['name']} {holding.get('number') or ''}".strip()}
    ext = {e.get("name"): e.get("value") for e in (prod.get("extendedData") or [])}
    image = prod.get("imageUrl") or ""
    return {
        "sig": sig,
        "category_id": cat["categoryId"],
        "category_name": cat.get("displayName") or cat.get("name"),
        "group_id": grp["groupId"],
        "group_name": grp.get("name"),
        "product_id": prod["productId"],
        "product_name": prod.get("name"),
        "number": ext.get("Number") or holding.get("number"),
        "rarity": ext.get("Rarity"),
        "image": image.replace("_200w", "_400w") if image else "",
        "url": prod.get("url"),
    }


def pick_price(rows, variant):
    usable = [r for r in rows if (r.get("marketPrice") or r.get("midPrice"))]
    if variant:
        for r in usable:
            if norm(r.get("subTypeName")) == norm(variant):
                return r
    for v in VARIANT_ORDER:
        for r in usable:
            if r.get("subTypeName") == v:
                return r
    return usable[0] if usable else None


# ---------- Ana akış ----------

def main():
    now = datetime.now(timezone.utc)
    portfolio = load_json(PORTFOLIO, {"holdings": []})
    cache = load_json(CACHE, {})
    history = load_json(HISTORY, {"prices": {}, "fx": []})
    catalog = Catalog()

    try:
        source_updated = http_get("https://tcgcsv.com/last-updated.txt", as_json=False).strip()
    except Exception as e:  # noqa: BLE001
        log("last-updated.txt okunamadı:", e)
        source_updated = None
    price_date = (source_updated or now.isoformat())[:10]

    fx_today = fetch_fx()
    if fx_today:
        history["fx"] = [row for row in history.get("fx", []) if row[0] != price_date]
        history["fx"].append([price_date, fx_today["rates"]])
        history["fx"].sort(key=lambda r: r[0])

    resolved = {}
    for h in portfolio.get("holdings", []):
        try:
            r = resolve(h, catalog, cache)
        except Exception as e:  # noqa: BLE001
            r = {"error": f"Katalog okunamadı: {e}"}
        if r.get("product_id") and "buy_fx" not in r and h.get("bought"):
            fx_buy = fetch_fx(h["bought"])
            if fx_buy:
                r["buy_fx"] = fx_buy["rates"]
        cache[h["id"]] = r
        resolved[h["id"]] = r
        log(("OK  " if r.get("product_id") else "HATA"), h["id"], r.get("product_name") or r.get("error"))

    # Eşleşme kontrolü için aday listesi: aynı set içinde adı tutan tüm ürünler
    debug = {}
    for h in portfolio.get("holdings", []):
        try:
            cat = catalog.find_category(h["game"])
            grp = catalog.find_group(cat["categoryId"], h["set"]) if cat else None
            if not grp:
                continue
            n = norm(h["name"])
            cands = []
            for p in catalog.products(cat["categoryId"], grp["groupId"]):
                if n in norm(p.get("cleanName") or p.get("name")):
                    ext = {e.get("name"): e.get("value") for e in (p.get("extendedData") or [])}
                    cands.append({"product_id": p["productId"], "name": p.get("name"),
                                  "number": ext.get("Number"), "rarity": ext.get("Rarity")})
            debug[h["id"]] = {"group": grp.get("name"), "group_options": catalog.group_candidates(cat["categoryId"], h["set"]),
                              "candidates": cands[:15]}
        except Exception as e:  # noqa: BLE001
            debug[h["id"]] = {"error": str(e)}

    prices_by_group = {}
    for r in resolved.values():
        if r.get("product_id"):
            key = (r["category_id"], r["group_id"])
            if key not in prices_by_group:
                try:
                    rows = results(http_get(f"{TCG}/{key[0]}/{key[1]}/prices"))
                except Exception as e:  # noqa: BLE001
                    log("Fiyat okunamadı:", key, e)
                    rows = []
                idx = {}
                for row in rows:
                    idx.setdefault(int(row["productId"]), []).append(row)
                prices_by_group[key] = idx

    out_holdings = []
    for h in portfolio.get("holdings", []):
        r = resolved.get(h["id"], {})
        item = {
            "id": h["id"], "game": h.get("game"), "set_input": h.get("set"), "name_input": h.get("name"),
            "qty": h.get("qty", 1), "cost_usd": h.get("cost_usd", 0), "bought": h.get("bought"),
            "buy_fx": r.get("buy_fx"),
        }
        if not r.get("product_id"):
            item.update({"status": "unresolved", "note": r.get("error")})
            out_holdings.append(item)
            continue
        rows = prices_by_group.get((r["category_id"], r["group_id"]), {}).get(int(r["product_id"]), [])
        row = pick_price(rows, h.get("variant"))
        item.update({
            "status": "ok" if row else "no_price",
            "product_id": r["product_id"], "name": r["product_name"], "set": r["group_name"],
            "category": r["category_name"], "number": r.get("number"), "rarity": r.get("rarity"),
            "image": r.get("image"), "url": r.get("url"),
            "variant": row.get("subTypeName") if row else h.get("variant"),
        })
        if row:
            market = row.get("marketPrice") or row.get("midPrice")
            item["price"] = {
                "market": market, "low": row.get("lowPrice"), "mid": row.get("midPrice"),
                "direct_low": row.get("directLowPrice"),
            }
            series = [p for p in history["prices"].get(h["id"], []) if p[0] != price_date]
            series.append([price_date, round(float(market), 2)])
            series.sort(key=lambda p: p[0])
            history["prices"][h["id"]] = series
        out_holdings.append(item)

    latest = {
        "generated_at": now.isoformat(timespec="seconds"),
        "source": "TCGplayer piyasa fiyatı (TCGCSV aracılığıyla)",
        "source_updated": source_updated,
        "price_date": price_date,
        "fx": fx_today,
        "holdings": out_holdings,
    }
    save_json(LATEST, latest)
    save_json(HISTORY, history, compact=True)
    save_json(CACHE, cache)
    for hid, d in debug.items():
        for c in d.get("candidates", []):
            for (cid, gid), idx in prices_by_group.items():
                rows = idx.get(int(c["product_id"]))
                if rows:
                    c["prices"] = {r.get("subTypeName"): r.get("marketPrice") for r in rows}
    save_json(os.path.join(ROOT, "pipeline", "cache", "candidates.json"), debug)

    ok = sum(1 for h in out_holdings if h.get("status") == "ok")
    log(f"{ok}/{len(out_holdings)} kart fiyatlandı · tarih {price_date} · kur {'var' if fx_today else 'yok'}")
    if ok == 0 and out_holdings:
        sys.exit(1)


if __name__ == "__main__":
    main()
