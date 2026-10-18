"""Holotique katalog görevi.

Her gece TCGCSV'den (TCGplayer verisi) seçili oyunların tüm kartlarını ve
güncel piyasa fiyatlarını Supabase'deki `catalog` tablosuna yükler.
Herkese açık arama sayfası bu tabloyu kullanır.

TCGCSV kuralları: tanımlayıcı User-Agent, istekler arası bekleme,
günde en fazla bir tam senkron, toplam 10.000 isteğin altında kalmak.
Yalnızca Python standart kütüphanesi kullanılır.
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SUPA = os.environ.get("SUPABASE_URL", "").rstrip("/")
SKEY = os.environ.get("SUPABASE_SECRET_KEY", "")
TCG = "https://tcgcsv.com/tcgplayer"
UA = "Holotique/0.3 (+https://holotique.com)"
FORCE = os.environ.get("CATALOG_FORCE") == "1"
BATCH = 500
# Katalog satır biçimi değişince artırılır; böylece kaynak aynı olsa bile bir kez yeniden yüklenir.
SYNC_VERSION = 2
EXTRA_COLS = {"ok": True}

# Oyun adı (sitede görünen) -> TCGCSV kategori adı adayları
GAMES = [
    ("Pokemon", ["pokemon"]),
    ("Pokemon JP", ["pokemonjapan"]),
    ("One Piece", ["onepiececardgame"]),
    ("Lorcana", ["lorcanatcg", "disneylorcana", "lorcana"]),
]
VARIANT_ORDER = ["Normal", "Holofoil", "Foil", "Unlimited Holofoil", "1st Edition Holofoil",
                 "Unlimited", "1st Edition", "Reverse Holofoil"]
STATUS = {"errors": [], "games": {}}


def log(*a):
    print(*a, flush=True)


def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def http(method, url, headers=None, body=None, timeout=90):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8")
        if not raw.strip():
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw


REQUESTS = {"n": 0}


def tcg(path):
    for attempt in range(4):
        try:
            time.sleep(0.12)
            REQUESTS["n"] += 1
            body = http("GET", f"{TCG}/{path}")
            return body.get("results") if isinstance(body, dict) else (body or [])
        except Exception as e:  # noqa: BLE001
            if attempt == 3:
                raise
            log("tekrar:", path, e)
            time.sleep(5 * (attempt + 1))


def sb(method, path, params=None, body=None, prefer=None):
    url = f"{SUPA}/rest/v1/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params, safe=",.()*:")
    headers = {"apikey": SKEY, "Content-Type": "application/json"}
    if prefer:
        headers["Prefer"] = prefer
    try:
        return http(method, url, headers, body)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:400]
        raise RuntimeError(f"Supabase {method} {path}: {e.code} {detail}") from None


def pick_price(rows):
    usable = [r for r in rows if r.get("marketPrice") or r.get("midPrice")]
    for v in VARIANT_ORDER:
        for r in usable:
            if r.get("subTypeName") == v:
                return r
    return usable[0] if usable else (rows[0] if rows else None)


def upsert(rows):
    for i in range(0, len(rows), BATCH):
        sb("POST", "catalog", {"on_conflict": "product_id"}, rows[i:i + BATCH],
           prefer="resolution=merge-duplicates,return=minimal")


def sync_game(label, aliases, cats, price_date):
    cat = None
    for a in aliases:
        cat = next((c for c in cats if norm(c.get("name")) == a or norm(c.get("displayName")) == a), None)
        if cat:
            break
    if not cat:
        STATUS["errors"].append(f"{label}: kategori bulunamadı")
        return 0
    cid = cat["categoryId"]
    groups = tcg(f"{cid}/groups") or []
    log(f"{label}: kategori {cid}, {len(groups)} set")
    total = 0
    buffer = []
    for g in groups:
        gid = g.get("groupId")
        try:
            products = tcg(f"{cid}/{gid}/products") or []
            prices = tcg(f"{cid}/{gid}/prices") or []
        except Exception as e:  # noqa: BLE001
            if len(STATUS["errors"]) < 20:
                STATUS["errors"].append(f"{label} set {gid}: {str(e)[:150]}")
            continue
        by_pid = {}
        for p in prices:
            by_pid.setdefault(int(p["productId"]), []).append(p)
        for p in products:
            ext = {e.get("name"): e.get("value") for e in (p.get("extendedData") or [])}
            pr = pick_price(by_pid.get(int(p["productId"]), []))
            img = p.get("imageUrl") or ""
            buffer.append({
                "product_id": p["productId"], "category_id": cid, "game": label, "group_id": gid,
                "set_name": g.get("name"), "name": p.get("name") or "", "clean_name": p.get("cleanName"),
                "number": ext.get("Number"), "rarity": ext.get("Rarity"),
                "image": img.replace("_200w", "_400w") if img else None, "url": p.get("url"),
                "sub_type": pr.get("subTypeName") if pr else None,
                "market": (pr.get("marketPrice") or pr.get("midPrice")) if pr else None,
                "low": pr.get("lowPrice") if pr else None,
                **({"set_code": g.get("abbreviation") or None,
                    "released": (g.get("publishedOn") or "")[:10] or None} if EXTRA_COLS["ok"] else {}),
                "price_date": price_date, "updated_at": datetime.now(timezone.utc).isoformat(),
            })
        if len(buffer) >= BATCH * 4:
            upsert(buffer)
            total += len(buffer)
            buffer = []
    if buffer:
        upsert(buffer)
        total += len(buffer)
    log(f"{label}: {total} kart yüklendi")
    return total


def main():
    if not (SUPA and SKEY):
        sys.exit("Eksik ayar: SUPABASE_URL / SUPABASE_SECRET_KEY")
    STATUS["run_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        last = str(http("GET", "https://tcgcsv.com/last-updated.txt") or "").strip()
    except Exception as e:  # noqa: BLE001
        last = ""
        log("last-updated.txt okunamadı:", e)
    STATUS["source_updated"] = last
    try:
        prev = sb("GET", "job_state", {"key": "eq.catalog:last", "select": "value"}) or []
    except RuntimeError as e:
        log("Veritabanı hazır değil:", e)
        STATUS["errors"].append(str(e)[:200])
        return
    try:
        sb("GET", "catalog", {"select": "product_id", "limit": "1"})
    except RuntimeError as e:
        log("Katalog tablosu henüz yok (supabase/migrations/003_catalog.sql çalıştırılmalı).", e)
        STATUS["errors"].append("catalog tablosu yok: " + str(e)[:150])
        return
    try:
        sb("GET", "catalog", {"select": "set_code,released", "limit": "1"})
    except RuntimeError:
        EXTRA_COLS["ok"] = False
        STATUS["note"] = "004_search_v2.sql henüz çalıştırılmamış; set kodu ve çıkış tarihi yüklenmedi."
        log(STATUS["note"])
    version = SYNC_VERSION if EXTRA_COLS["ok"] else 1
    pv = prev[0]["value"] if prev else {}
    if pv.get("source_updated") == last and last and pv.get("version", 1) >= version and not FORCE:
        log("TCGCSV verisi son senkrondan beri değişmemiş; atlandı.")
        STATUS["skipped"] = True
        return
    price_date = (last or STATUS["run_at"])[:10]
    cats = tcg("categories") or []
    for label, aliases in GAMES:
        try:
            STATUS["games"][label] = sync_game(label, aliases, cats, price_date)
        except Exception as e:  # noqa: BLE001
            STATUS["errors"].append(f"{label}: {str(e)[:200]}")
            log("HATA", label, e)
    STATUS["requests"] = REQUESTS["n"]
    if any(STATUS["games"].values()):
        sb("POST", "job_state", {"on_conflict": "key"},
           [{"key": "catalog:last", "value": {"source_updated": last, "games": STATUS["games"], "version": version},
             "updated_at": datetime.now(timezone.utc).isoformat()}],
           prefer="resolution=merge-duplicates,return=minimal")
    log(f"Bitti · istek: {REQUESTS['n']} · {STATUS['games']}")


if __name__ == "__main__":
    try:
        main()
    finally:
        with open(os.environ.get("STATUS_FILE", "catalog-status.json"), "w", encoding="utf-8") as f:
            json.dump(STATUS, f, ensure_ascii=False, indent=1)
