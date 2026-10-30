"""Holotique PSA fiyat görevi.

GitHub Actions tarafından iki saatte bir çalışır:
  1. Kullanıcıların yeni eklediği kartları PokemonPriceTracker kataloğunda bulur (eşleştirme).
  2. Takip edilen kartların ham, PSA 10 ve PSA 9 fiyatlarını günde bir kez günceller.
  3. Günlük kurları ve alış günündeki kurları kaydeder.

Günlük kredi bütçesini (ücretsiz plan: 100) aşmaz; kalan iş sonraki çalışmalara kalır.
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
PKEY = os.environ.get("PPT_KEY", "")
PSA_TOKEN = os.environ.get("PSA_TOKEN", "")
PSA_DAILY_BUDGET = int(os.environ.get("PSA_DAILY_BUDGET", "90"))
PSA_API = "https://api.psacard.com/publicapi"
DAILY_BUDGET = int(os.environ.get("PPT_DAILY_BUDGET", "95"))
PPT = "https://www.pokemonpricetracker.com/api/v2"
UA = "Holotique/0.2 (+https://holotique.com)"
CURRENCIES = ["TRY", "EUR", "GBP", "JPY", "CNY"]
SEARCH_LIMIT = int(os.environ.get("PPT_SEARCH_LIMIT", "3"))
HISTORY_DAYS = int(os.environ.get("PPT_HISTORY_DAYS", "0"))  # 0: geçmiş çekilmez (ücretsiz plan)
MATCH_SHARE = 0.7  # fiyatlamadan kalan bütçenin bu kadarı eşleştirmeye, gerisi yeni eşleşenlerin fiyatına
PRICE_SHARE = 0.6  # bütçenin önce bu kadarı eşleşmiş kartların fiyatına

TODAY = datetime.now(timezone.utc).date().isoformat()
STATUS = {"errors": [], "price_samples": []}


def note_error(where, e):
    msg = f"{where}: {str(e)[:300]}"
    log("HATA", msg)
    if len(STATUS["errors"]) < 20:
        STATUS["errors"].append(msg)


def log(*a):
    print(*a, flush=True)


# ---------- HTTP ----------

def http(method, url, headers=None, body=None, timeout=60):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8")
        return json.loads(raw) if raw.strip() else None


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
        detail = e.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"Supabase {method} {path}: {e.code} {detail}") from None


class Budget:
    def __init__(self):
        rows = sb("GET", "job_state", {"key": f"eq.ppt:{TODAY}", "select": "value"}) or []
        self.used = int(rows[0]["value"].get("used", 0)) if rows else 0

    @property
    def left(self):
        return max(0, DAILY_BUDGET - self.used)

    def save(self):
        sb("POST", "job_state", {"on_conflict": "key"},
           [{"key": f"ppt:{TODAY}", "value": {"used": self.used}, "updated_at": datetime.now(timezone.utc).isoformat()}],
           prefer="resolution=merge-duplicates,return=minimal")


def ppt(params, budget, expected_cost):
    if budget.left < expected_cost:
        raise BudgetExhausted()
    url = f"{PPT}/cards?{urllib.parse.urlencode(params)}"
    time.sleep(1.1)  # dakikada 60 istek sınırı
    try:
        body = http("GET", url, {"Authorization": f"Bearer {PKEY}"})
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        if e.code in (402, 429):
            budget.used = DAILY_BUDGET
            raise BudgetExhausted() from None
        raise RuntimeError(f"PPT {e.code}: {detail}") from None
    used = ((body or {}).get("metadata") or {}).get("apiCallsConsumed") or {}
    budget.used += int(used.get("total", expected_cost)) if isinstance(used, dict) else expected_cost
    return body or {}


class BudgetExhausted(Exception):
    pass


# ---------- Eşleştirme ----------

def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def num_key(s):
    """'217/187' -> '217', 'TG23/TG30' -> '23', 'SM211' -> '211', '007' -> '7'."""
    first = str(s or "").split("/")[0]
    digits = re.sub(r"\D", "", first)
    return digits.lstrip("0") or ("0" if digits else "")


def lang_of(v):
    return "japanese" if str(v or "").strip().lower() in ("jp", "ja", "jpn", "japanese", "japonca") else "english"


def clean_set(s):
    s = re.sub(r"\bjapanese\b", "", str(s or ""), flags=re.I)
    return re.sub(r"\s+", " ", s).strip()


def pick(cands, number, set_name):
    want = num_key(number)
    hits = [c for c in cands if want and num_key(c.get("cardNumber")) == want] if want else list(cands)
    if not hits and want:
        # Numarası olmayan kartlar (ör. Japon Vending serisi): set adı tutuyorsa numarasız adaylar kabul edilir.
        hits = [c for c in cands if not num_key(c.get("cardNumber")) and set_overlap(set_name, c.get("setName")) > 0]
    if not hits:
        return None, len(cands)
    hits.sort(key=lambda c: -set_overlap(set_name, c.get("setName")))
    return hits[0], len(hits)


GENERIC_SET_WORDS = {"promo", "promos", "pokemon", "japanese", "set", "special", "collection", "the", "and"}


def set_overlap(set_name, cand_set):
    words = [norm(w) for w in clean_set(set_name).split() if len(w) > 2]
    words = [w for w in words if w and w not in GENERIC_SET_WORDS]
    target = norm(cand_set)
    return sum(1 for w in words if w in target)


def upsert_card(c, game, language):
    row = {
        "source": "ppt", "ext_id": str(c.get("tcgPlayerId")), "game": game, "language": language,
        "name": c.get("name") or "", "set_name": c.get("setName"), "number": c.get("cardNumber"),
        "rarity": c.get("rarity"), "image": c.get("imageCdnUrl400") or c.get("imageUrl"),
        "url": c.get("tcgPlayerUrl"),
    }
    res = sb("POST", "cards", {"on_conflict": "source,ext_id"}, [row], prefer="resolution=merge-duplicates,return=representation")
    return res[0]["id"]


# ---------- Pokemon dışı oyunlar: TCGCSV kataloğundan ham fiyat ----------

CATALOG_GAMES = {"onepiece": "One Piece", "lorcana": "Lorcana", "disneylorcana": "Lorcana",
                 "magic": "Magic", "magicthegathering": "Magic", "mtg": "Magic", "riftbound": "Riftbound"}


def catalog_game(game):
    return CATALOG_GAMES.get(norm(game))


def _cat_get(params):
    return sb("GET", "catalog", {"select": "product_id,game,set_name,name,clean_name,number,rarity,image,url,market,price_date",
                                 "limit": "60", **params}) or []


def _pg_like(v):
    return re.sub(r"[*,()]", " ", str(v or "")).strip()


def match_exact(h, budget):
    """Kullanıcı kart eklerken öneriden seçtiyse (product_id) tahmin yok: doğrudan o kart."""
    pid = h.get("product_id")
    rows = _cat_get({"product_id": f"eq.{pid}"})
    c = rows[0] if rows else None
    game = (h.get("game") or "Pokemon").strip()
    cgame = catalog_game(game)
    if cgame or (c and c.get("game") not in ("Pokemon", "Pokemon JP")):
        if not c:
            return None, "Seçilen kart katalogda bulunamadı."
        row = {"source": "tcgcsv", "ext_id": str(pid), "game": c.get("game") or cgame, "language": "english",
               "name": c.get("name") or "", "set_name": c.get("set_name"), "number": c.get("number"),
               "rarity": c.get("rarity"), "image": c.get("image"), "url": c.get("url")}
        res = sb("POST", "cards", {"on_conflict": "source,ext_id"}, [row], prefer="resolution=merge-duplicates,return=representation")
        return res[0]["id"], f"{c.get('set_name')} · {c.get('number')} · yalnızca ham fiyat (TCGplayer)"
    # Pokemon: PSA fiyatları için PokemonPriceTracker kaydı (TCGplayer numarasıyla birebir)
    lang = "japanese" if (c and c.get("game") == "Pokemon JP") else lang_of(h.get("language"))
    prev = sb("GET", "cards", {"select": "id,set_name,number", "source": "eq.ppt", "ext_id": f"eq.{pid}", "limit": "1"}) or []
    if prev:
        return prev[0]["id"], f"{prev[0].get('set_name')} · {prev[0].get('number')} · listeden seçildi"
    body = ppt({"tcgPlayerId": str(pid), "language": lang, "limit": 1}, budget, 1)
    d = body.get("data")
    d = d[0] if isinstance(d, list) and d else (d if isinstance(d, dict) else None)
    if not d:
        return None, None   # bulunamadı: normal eşleştirmeye düş
    return upsert_card(d, "Pokemon", lang), f"{d.get('setName')} · {d.get('cardNumber')} · listeden seçildi"


def match_from_catalog(h, cgame):
    """Kartı gece yüklenen katalogda (TCGCSV) bulur. Kredi harcamaz."""
    name, number, set_in = h.get("name_input") or "", (h.get("number_input") or "").strip(), h.get("set_input") or ""
    cands = []
    if number:
        cands = _cat_get({"game": f"eq.{cgame}", "number": f"ilike.*{_pg_like(number)}*"})
    if not cands and name:
        words = [w for w in re.split(r"\W+", name) if len(w) > 1][:4]
        if words:
            cands = _cat_get({"game": f"eq.{cgame}", "name": "ilike.*" + "*".join(_pg_like(w) for w in words) + "*"})
    if not cands:
        return None, "Katalogda bulunamadı. Kart adını ve numarasını (ör. OP05-119) kontrol et."
    want_num = norm(number)
    name_words = {norm(w) for w in re.split(r"\W+", name) if len(w) > 1}

    def score(c):
        cn = norm(c.get("number"))
        num_ok = 3 if want_num and cn == want_num else (2 if want_num and cn.endswith(want_num) else 0)
        nm = norm(c.get("clean_name") or c.get("name"))
        name_hits = sum(1 for w in name_words if w and w in nm)
        variant_pen = 0 if any(t in norm(name) for t in ("alternate", "parallel", "manga", "enchanted", "foil")) else \
            (1 if re.search(r"alternate|parallel|manga|enchanted|special", str(c.get("name")), re.I) else 0)
        return (num_ok, name_hits, set_overlap(set_in, c.get("set_name")), -variant_pen, c.get("market") or 0)

    cands.sort(key=score, reverse=True)
    best = cands[0]
    if number and score(best)[0] == 0 and (score(best)[1] == 0 or best.get("number")):
        return None, "Katalogda bu numarayla kart bulunamadı. Numarayı kontrol et."
    row = {"source": "tcgcsv", "ext_id": str(best["product_id"]), "game": cgame, "language": "english",
           "name": best.get("name") or "", "set_name": best.get("set_name"), "number": best.get("number"),
           "rarity": best.get("rarity"), "image": best.get("image"), "url": best.get("url")}
    res = sb("POST", "cards", {"on_conflict": "source,ext_id"}, [row], prefer="resolution=merge-duplicates,return=representation")
    others = sum(1 for c in cands[1:] if score(c)[:2] == score(best)[:2])
    note = f"{best.get('set_name')} · {best.get('number')} · yalnızca ham fiyat (TCGplayer)"
    if others:
        note += " · birden fazla aday vardı, kontrol et"
    return res[0]["id"], note


def price_catalog_cards(cards):
    """Katalogdan eşleşen kartların bugünkü ham fiyatını yazar."""
    if not cards:
        return 0
    have = {r["card_id"] for r in (sb("GET", "card_prices", {"select": "card_id", "date": f"eq.{TODAY}",
                                                             "card_id": f"in.({','.join(str(c['id']) for c in cards)})"}) or [])}
    todo = [c for c in cards if c["id"] not in have]
    if not todo:
        return 0
    rows = _cat_get({"product_id": f"in.({','.join(c['ext_id'] for c in todo)})", "limit": "1000"})
    by = {str(r["product_id"]): r for r in rows}
    out = []
    for c in todo:
        r = by.get(c["ext_id"])
        if r and r.get("market") is not None:
            out.append({"card_id": c["id"], "date": TODAY, "raw": r["market"]})
            sb("PATCH", "cards", {"id": f"eq.{c['id']}"}, {"last_priced": TODAY, "image": r.get("image"), "url": r.get("url")})
    if out:
        sb("POST", "card_prices", {"on_conflict": "card_id,date"}, out, prefer="resolution=merge-duplicates,return=minimal")
    log(f"Katalogdan ham fiyat yazılan kart: {len(out)}")
    return len(out)


def match_pending(budget):
    # Katalogla desteklenen oyunlarda daha önce "desteklenmiyor" denmiş kartları yeniden dene.
    for g in set(CATALOG_GAMES.values()):
        sb("PATCH", "holdings", {"match_status": "eq.unsupported", "game": f"ilike.*{g.split()[0]}*"},
           {"match_status": "pending", "match_note": None})
    params = {"match_status": "eq.pending", "order": "created_at.asc", "limit": "200"}
    try:
        pending = sb("GET", "holdings", {**params, "select": "id,game,set_input,name_input,number_input,language,psa,product_id"}) or []
    except RuntimeError:
        pending = None
    if pending is None:
        try:
            pending = sb("GET", "holdings", {**params, "select": "id,game,set_input,name_input,number_input,language,psa"}) or []
        except RuntimeError:
            pending = None
    if pending is None:
        pending = sb("GET", "holdings", {**params, "select": "id,game,set_input,name_input,number_input,language"}) or []
    if not pending:
        return 0
    log(f"Eşleşme bekleyen kart: {len(pending)}")
    cap_used = budget.used + int(budget.left * MATCH_SHARE)
    done = 0
    memo = {}
    for h in pending:
        game = (h.get("game") or "Pokemon").strip()
        if h.get("product_id"):
            try:
                card_id, note = match_exact(h, budget)
            except BudgetExhausted:
                break
            except Exception as e:  # noqa: BLE001
                note_error("seçilen kartı eşleştirme", e)
                card_id, note = None, None
            if card_id:
                sb("PATCH", "holdings", {"id": f"eq.{h['id']}"}, {"card_id": card_id, "match_status": "matched", "match_note": note})
                done += 1
                log("EŞLEŞTİ (seçilen) " + str(h.get("name_input")), "→", note)
                continue
        cgame = catalog_game(game)
        if cgame:
            try:
                card_id, note = match_from_catalog(h, cgame)
            except Exception as e:  # noqa: BLE001
                note_error("katalog eşleştirme", e)
                continue
            sb("PATCH", "holdings", {"id": f"eq.{h['id']}"},
               {"card_id": card_id, "match_status": "matched" if card_id else "failed", "match_note": note})
            done += 1
            log(("EŞLEŞTİ (katalog) " if card_id else "BULUNAMADI (katalog) ") + str(h.get("name_input")), "→", note)
            continue
        if norm(game) != "pokemon":
            sb("PATCH", "holdings", {"id": f"eq.{h['id']}"},
               {"match_status": "unsupported", "match_note": f"{game} için PSA fiyat kaynağı henüz bağlı değil."})
            continue
        lang = lang_of(h.get("language"))
        pinfo = psa_hint(h.get("psa"))
        if pinfo.get("japanese"):
            lang = "japanese"
        number = pinfo.get("number") or h.get("number_input")
        key = (norm(h.get("name_input")), norm(clean_set(h.get("set_input"))), num_key(number), lang)
        if key in memo:
            card_id, note = memo[key]
        else:
            # Aynı kart daha önce başka bir satır için eşleşmiş mi?
            prev = sb("GET", "holdings", {
                "select": "card_id,match_note", "match_status": "eq.matched", "card_id": "not.is.null",
                "name_input": f"eq.{h.get('name_input')}", "number_input": f"eq.{h.get('number_input')}",
                "language": f"eq.{h.get('language')}", "limit": "1"}) if h.get("number_input") and not pinfo else []
            if prev:
                card_id, note = prev[0]["card_id"], prev[0]["match_note"]
            else:
                if budget.used >= cap_used:
                    break
                card_id, note = None, None
                queries = []
                if pinfo.get("subject"):
                    if pinfo.get("number"):
                        queries.append(f"{pinfo['subject']} {pinfo['number']}")
                    if pinfo.get("set"):
                        queries.append(f"{pinfo['subject']} {pinfo['set']}")
                queries.append(f"{h.get('name_input', '')} {clean_set(h.get('set_input'))}".strip())
                if h.get("number_input") and not pinfo.get("number"):
                    queries.append(f"{h.get('name_input', '')} {h.get('number_input')}".strip())
                queries = list(dict.fromkeys(q for q in queries if q))[:3]
                seen = []
                try:
                    for q in queries:
                        body = ppt({"search": q, "language": lang, "limit": SEARCH_LIMIT}, budget, SEARCH_LIMIT)
                        cands = [c for c in (body.get("data") or []) if isinstance(c, dict)]
                        seen += cands
                        best, n_hits = pick(cands, number, pinfo.get("set") or h.get("set_input"))
                        if best:
                            card_id = upsert_card(best, game, lang)
                            note = f"{best.get('setName')} · {best.get('cardNumber')}"
                            set_ref = pinfo.get("set") or h.get("set_input")
                            has_words = any(w for w in clean_set(set_ref).split() if len(w) > 2 and norm(w) not in GENERIC_SET_WORDS)
                            if has_words and set_overlap(set_ref, best.get("setName")) == 0:
                                note += " · set adı tutmadı, kontrol et"
                            elif n_hits > 1:
                                note += " · birden fazla aday vardı"
                            if pinfo:
                                note += " · PSA kaydıyla eşleşti"
                            break
                except BudgetExhausted:
                    break
                if not card_id:
                    names = ", ".join(sorted({f"{c.get('name')} ({c.get('setName')})" for c in seen})[:3])
                    note = "Kart bulunamadı. Set adını ve numarayı kontrol et." + (f" Benzer: {names}" if names else "")
            memo[key] = (card_id, note)
        sb("PATCH", "holdings", {"id": f"eq.{h['id']}"},
           {"card_id": card_id, "match_status": "matched" if card_id else "failed", "match_note": note})
        done += 1
        log(("EŞLEŞTİ " if card_id else "BULUNAMADI ") + str(h.get("name_input")), "→", note)
    return done


# ---------- Fiyatlar ----------

# psa10, bgs9_5, cgc10_pristine, bgs10_black, ... (şirket + derece + isteğe bağlı ek)
GRADE_KEY = re.compile(r"^(psa|bgs|cgc|sgc|tag|ace)_?(\d+(?:_5)?)(?:_?[a-z]+)?$")
HAS_GRADES = {"ok": True}


def all_grades(sales):
    """eBay derece verisini {"bgs9_5": {"p": fiyat, "c": güven, "n": satış adedi}} biçimine çevirir."""
    out = {}
    STATUS.setdefault("grade_keys", [])
    for k in (sales or {}):
        if k not in STATUS["grade_keys"]:
            STATUS["grade_keys"].append(k)
    for k, v in (sales or {}).items():
        if not GRADE_KEY.match(str(k)):
            continue
        p, c, n = grade_price(v)
        if p is not None:
            out[k] = {"p": p, "c": c, "n": n}
    return out or None


def write_prices(rows, prefer="resolution=merge-duplicates,return=minimal"):
    """card_prices'a yazar; 'grades' sütunu henüz yoksa (008 çalışmadıysa) onsuz yazar."""
    if not HAS_GRADES["ok"]:
        rows = [{k: v for k, v in r.items() if k != "grades"} for r in rows]
    try:
        sb("POST", "card_prices", {"on_conflict": "card_id,date"}, rows, prefer=prefer)
    except RuntimeError as e:
        if "grades" in str(e) and HAS_GRADES["ok"]:
            HAS_GRADES["ok"] = False
            STATUS["note_grades"] = "008_all_grades.sql henüz çalıştırılmamış; yalnızca PSA 10/9 kaydedildi."
            write_prices(rows, prefer)
        else:
            raise


def grade_price(g):
    if not isinstance(g, dict):
        return None, None, None
    sm = g.get("smartMarketPrice") or {}
    price = sm.get("price") or g.get("marketPrice7Day") or g.get("medianPrice") or g.get("averagePrice")
    return (round(float(price), 2) if price else None), sm.get("confidence"), g.get("count")


def sales_summary(e):
    """eBay verisinden derece bazında satış özeti (son 90 günde satışı olan dereceler) ve son 90 günün günlük satışları."""
    if not isinstance(e, dict):
        return None
    from datetime import timedelta
    cut90 = (datetime.now(timezone.utc).date() - timedelta(days=91)).isoformat()
    hist = e.get("priceHistory") or {}
    out = {}
    for k, v in (e.get("salesByGrade") or {}).items():
        if not GRADE_KEY.match(str(k)) or not isinstance(v, dict):
            continue
        last = str(v.get("lastSaleDate") or "")[:10]
        if not last or last < cut90:
            continue
        days = []
        for dt, x in (hist.get(k) or {}).items():
            if str(dt) >= cut90 and isinstance(x, dict) and x.get("count"):
                days.append([str(dt)[:10], int(x.get("count") or 0), round(float(x.get("average") or 0), 2)])
        days.sort()

        def num(x):
            try:
                return round(float(x), 2) if x is not None else None
            except (TypeError, ValueError):
                return None
        out[k] = {"n": v.get("count"), "med": num(v.get("medianPrice")), "avg": num(v.get("averagePrice")),
                  "min": num(v.get("minPrice")), "max": num(v.get("maxPrice")), "last": last,
                  "trend": v.get("marketTrend"), "vol": num(v.get("dailyVolume7Day")),
                  "src": v.get("salesBySource"), "d": days}
    if not out:
        return None
    return {"at": TODAY, "from": str(e.get("dateRangeStart") or "")[:10], "to": str(e.get("dateRangeEnd") or "")[:10],
            "monthly": (e.get("salesVelocity") or {}).get("monthlyTotal"), "g": out}


def merge_sales(old, new):
    """Fiyat kaynağı yalnızca ~30 günlük günlük satış veriyor; önceki günleri koruyarak 90 güne kadar biriktir."""
    if not new:
        return old if isinstance(old, dict) else None
    if not isinstance(old, dict):
        return new
    from datetime import timedelta
    cut = (datetime.now(timezone.utc).date() - timedelta(days=91)).isoformat()
    for k, g in (new.get("g") or {}).items():
        og = (old.get("g") or {}).get(k) or {}
        days = {d[0]: d for d in (og.get("d") or []) if d[0] >= cut}
        days.update({d[0]: d for d in (g.get("d") or [])})
        g["d"] = sorted(days.values())
    starts = [x for x in (old.get("from"), new.get("from")) if x]
    if starts:
        new["from"] = max(min(starts), cut)
    return new


SALES_COL = [True]


def tracked_card_ids():
    """Portföylerdeki eşleşmiş kartlar + istek listelerindeki kartlar."""
    matched = sb("GET", "holdings", {"select": "card_id", "match_status": "eq.matched", "card_id": "not.is.null"}) or []
    ids = {r["card_id"] for r in matched}
    try:
        ids |= {r["card_id"] for r in (sb("GET", "wishlist", {"select": "card_id", "card_id": "not.is.null"}) or [])}
    except RuntimeError:
        pass  # 011_wishlist_showcase.sql henüz çalıştırılmamış
    return ids


def price_cards(budget, cap=None):
    ids = sorted(tracked_card_ids())
    if not ids:
        return 0
    cards = sb("GET", "cards", {"select": "id,ext_id,language,last_priced,source", "id": f"in.({','.join(map(str, ids))})"}) or []
    try:
        cat_done = price_catalog_cards([c for c in cards if c.get("source") == "tcgcsv"])
    except Exception as e:  # noqa: BLE001
        note_error("katalog fiyatı", e)
        cat_done = 0
    cards = [c for c in cards if c.get("source", "ppt") == "ppt"]
    # Bugün fiyat satırı olmayan her kart fiyatlanır. Ücretsiz planda kredi kısıtlı olduğundan
    # fiyatı gelmeyen kartlar (last_priced bugün) gün içinde yeniden denenmez.
    have = {r["card_id"] for r in (sb("GET", "card_prices", {"select": "card_id", "date": f"eq.{TODAY}"}) or [])}
    todo = [c for c in cards if c["id"] not in have and (DAILY_BUDGET > 1000 or c.get("last_priced") != TODAY)]
    todo.sort(key=lambda c: c.get("last_priced") or "")
    log(f"Takip edilen kart: {len(cards)} · bugün fiyatlanacak: {len(todo)}")
    done = cat_done
    for c in todo:
        if cap is not None and budget.used + 2 > cap:
            break
        try:
            body = ppt({"tcgPlayerId": c["ext_id"], "language": c.get("language") or "english",
                        "includeEbay": "true", "limit": 1}, budget, 2)
        except BudgetExhausted:
            break
        except Exception as e:  # noqa: BLE001
            note_error(f"fiyat isteği (kart {c['id']})", e)
            continue
        try:
            raw_data = body.get("data")
            # Tek kart sorgusunda API listeyi değil tek bir kaydı döndürebiliyor.
            if isinstance(raw_data, dict):
                raw_data = [raw_data]
            data = [x for x in (raw_data or []) if isinstance(x, dict)]
            meta = body.get("metadata") or {}
            if len(STATUS["price_samples"]) < 3:
                d0 = data[0] if data else {}
                STATUS["price_samples"].append({
                    "card": c["id"], "lang": c.get("language"), "n_data": len(data),
                    "keys": sorted(d0.keys())[:40], "has_ebay": bool(d0.get("ebay")),
                    "grades": sorted(((d0.get("ebay") or {}).get("salesByGrade") or {}).keys())[:12],
                    "has_market": bool((d0.get("prices") or {}).get("market")),
                    "meta_total": meta.get("total"), "data_type": type(body.get("data")).__name__,
                    "body_keys": sorted(body.keys())[:10], "error": body.get("error") or body.get("message")})
            if not data:
                log("Fiyat yok:", c["ext_id"])
                sb("PATCH", "cards", {"id": f"eq.{c['id']}"}, {"last_priced": TODAY})
                continue
            d = data[0]
            grades = ((d.get("ebay") or {}).get("salesByGrade")) or {}
            p10, c10, n10 = grade_price(grades.get("psa10"))
            p9, c9, n9 = grade_price(grades.get("psa9"))
            raw = (d.get("prices") or {}).get("market")
            write_prices([{
                "card_id": c["id"], "date": TODAY, "raw": raw, "psa10": p10, "psa10_conf": c10, "psa10_n": n10,
                "psa9": p9, "psa9_conf": c9, "psa9_n": n9, "grades": all_grades(grades)}])
            sb("PATCH", "cards", {"id": f"eq.{c['id']}"}, {
                "last_priced": TODAY, "image": d.get("imageCdnUrl400") or d.get("imageUrl"), "url": d.get("tcgPlayerUrl")})
            if SALES_COL[0]:
                try:
                    prev = (sb("GET", "cards", {"select": "sales", "id": f"eq.{c['id']}"}) or [{}])[0].get("sales")
                    sb("PATCH", "cards", {"id": f"eq.{c['id']}"}, {"sales": merge_sales(prev, sales_summary(d.get("ebay")))})
                except RuntimeError as e:  # 020_card_sales.sql henüz çalıştırılmamış
                    if "sales" in str(e) or "PGRST204" in str(e):
                        SALES_COL[0] = False
                    else:
                        note_error("satış özeti", e)
            done += 1
        except Exception as e:  # noqa: BLE001
            note_error(f"fiyat kaydı (kart {c['id']})", e)
    return done


# ---------- Kart görsellerini kendi depomuza kopyala (vitrin görseli için) ----------

IMG_BUCKET = "card-images"


def cache_images(limit=150):
    """Takip edilen kartların görsellerini Supabase Storage'a kopyalar; tarayıcı bunları güvenle çizebilir."""
    ids = sorted(tracked_card_ids())
    if not ids:
        return 0
    try:
        cards = sb("GET", "cards", {"select": "id,image", "image_cached": "is.null", "image": "not.is.null",
                                    "id": f"in.({','.join(map(str, ids))})", "limit": str(limit)}) or []
    except RuntimeError as e:
        if "image_cached" in str(e):
            STATUS["note_images"] = "012_card_images.sql henüz çalıştırılmamış."
            return 0
        raise
    done, fails = 0, []
    for c in cards:
        src = c["image"]
        try:
            req = urllib.request.Request(src, headers={"User-Agent": UA, "Accept": "image/*"})
            with urllib.request.urlopen(req, timeout=30) as r:
                ctype = (r.headers.get("Content-Type") or "image/jpeg").split(";")[0].strip()
                data = r.read(2_000_000)
            if not ctype.startswith("image/") or len(data) < 500:
                raise RuntimeError(f"görsel değil ({ctype}, {len(data)} bayt)")
            ext = {"image/png": "png", "image/webp": "webp"}.get(ctype, "jpg")
            path = f"{c['id']}.{ext}"
            up = urllib.request.Request(f"{SUPA}/storage/v1/object/{IMG_BUCKET}/{path}", data=data, method="POST",
                                        headers={"apikey": SKEY, "Content-Type": ctype, "x-upsert": "true",
                                                 "Cache-Control": "max-age=31536000", "User-Agent": UA})
            urllib.request.urlopen(up, timeout=30).read()
            sb("PATCH", "cards", {"id": f"eq.{c['id']}"},
               {"image_cached": f"{SUPA}/storage/v1/object/public/{IMG_BUCKET}/{path}"})
            done += 1
        except urllib.error.HTTPError as e:
            fails.append(f"kart {c['id']}: {e.code} {e.read().decode('utf-8', 'replace')[:120]}")
        except Exception as e:  # noqa: BLE001
            fails.append(f"kart {c['id']}: {str(e)[:120]}")
        if len(fails) >= 5 and not done:
            break  # depo ya da kaynak hiç çalışmıyorsa boşuna deneme
    STATUS["images"] = {"cached": done, "failed": len(fails), "examples": fails[:3]}
    if done:
        log(f"Depoya kopyalanan kart görseli: {done}")
    return done


# ---------- Fiyat alarmı (istek listesi hedef fiyata inince mail) ----------

SMTP_HOST = os.environ.get("SMTP_HOST", "smtpout.secureserver.net")
SMTP_USER = os.environ.get("SMTP_USER", "info@holotique.com")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")


def _alert_html(rows):
    import html as _h
    def money(v):
        return "—" if v is None else "$" + f"{float(v):,.2f}"
    items = ""
    for r in rows:
        img = f'<img src="{_h.escape(r["image"])}" width="56" style="border-radius:6px;display:block" alt="">' if r.get("image") else ""
        sub = " · ".join(x for x in [r.get("set_name"), r.get("number"), r.get("grade")] if x)
        items += f"""<tr><td style="padding:10px 0;border-top:1px solid #DDE2EA;width:64px;vertical-align:top">{img}</td>
<td style="padding:10px 0 10px 10px;border-top:1px solid #DDE2EA;vertical-align:top">
<div style="font-weight:600;font-size:15px">{_h.escape(r.get("name") or "")}</div>
<div style="font-size:13px;color:#5A6577">{_h.escape(sub)}</div>
<div style="font-size:14px;margin-top:4px"><b style="color:#127A47">{money(r.get("price"))}</b>
<span style="color:#5A6577"> · hedef / target {money(r.get("target"))}</span></div></td></tr>"""
    return f"""<!doctype html><html><body style="margin:0;background:#EEF1F5;font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#121A26">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:24px 12px"><tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;background:#fff;border:1px solid #DDE2EA;border-radius:14px;overflow:hidden">
<tr><td style="height:6px;background-color:#B79CF5;background:linear-gradient(90deg,#7AD3F0,#B79CF5,#F3A6C8,#F6D58A,#9BE3C4)"></td></tr>
<tr><td style="padding:24px 28px 0"><div style="font-size:20px;font-weight:800">Holotique</div>
<h1 style="font-size:19px;margin:14px 0 4px">Takip ettiğin kart hedef fiyatına indi</h1>
<div style="font-size:14px;color:#5A6577" lang="en">A card on your wishlist reached your target price</div></td></tr>
<tr><td style="padding:14px 28px 4px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0">{items}</table></td></tr>
<tr><td style="padding:12px 28px 4px"><a href="https://holotique.com/portfoy.html" style="display:inline-block;background:#2B47D6;color:#fff;text-decoration:none;font-weight:600;font-size:15px;padding:12px 20px;border-radius:8px">İstek listemi aç · Open my wishlist</a></td></tr>
<tr><td style="padding:16px 28px 24px;font-size:12px;color:#8A94A6;line-height:1.5">
Fiyatlar tahmini piyasa değeridir, yatırım tavsiyesi değildir. Bu maili almak istemiyorsan istek listende kartın ayarlarından “Hedef fiyata inince bana mail at” seçeneğini kapat.<br>
<span lang="en">Prices are estimated market values, not investment advice. To stop these emails, turn off “Email me when it hits my target price” for the card on your wishlist.</span><br><br>
Holotique · <a href="https://holotique.com" style="color:#8A94A6">holotique.com</a></td></tr>
</table></td></tr></table></body></html>"""


def send_alerts():
    if not SMTP_PASSWORD:
        STATUS["alerts"] = {"skipped": "SMTP_PASSWORD tanımlı değil"}
        return 0
    try:
        rows = sb("POST", "rpc/alerts_due", body={}) or []
    except RuntimeError as e:
        if "alerts_due" in str(e) or "PGRST202" in str(e):
            STATUS["alerts"] = {"skipped": "015_price_alerts.sql henüz çalıştırılmamış"}
            return 0
        raise
    if not rows:
        STATUS["alerts"] = {"sent": 0}
        return 0
    import smtplib
    import ssl
    from email.message import EmailMessage
    from email.utils import formataddr, make_msgid
    by = {}
    for r in rows:
        by.setdefault(r["email"], []).append(r)
    sent, fails = 0, []
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_HOST, 465, context=ctx, timeout=30) as srv:
        srv.login(SMTP_USER, SMTP_PASSWORD)
        for email, items in list(by.items())[:200]:
            first = items[0].get("name") or "Kart"
            subj = (f"{first} hedef fiyatına indi" if len(items) == 1 else f"{len(items)} kart hedef fiyatına indi") \
                + " · Holotique"
            m = EmailMessage()
            m["Subject"] = subj
            m["From"] = formataddr(("Holotique", SMTP_USER))
            m["To"] = email
            m["Message-ID"] = make_msgid(domain="holotique.com")
            lines = [f"- {r.get('name')} ({r.get('grade')}): ${float(r['price']):,.2f} (hedef/target ${float(r['target']):,.2f})" for r in items]
            m.set_content("Takip ettiğin kart hedef fiyatına indi / A card on your wishlist reached your target price\n\n"
                          + "\n".join(lines) + "\n\nhttps://holotique.com/portfoy.html")
            m.add_alternative(_alert_html(items), subtype="html")
            try:
                srv.send_message(m)
                sb("POST", "rpc/alerts_mark_sent", body={"ids": [r["wish_id"] for r in items]})
                sent += 1
            except Exception as e:  # noqa: BLE001
                fails.append(str(e)[:120])
    STATUS["alerts"] = {"sent": sent, "cards": len(rows), "failed": len(fails), "examples": fails[:2]}
    log(f"Fiyat alarmı maili: {sent}")
    return sent


# ---------- Ortak mail kalıbı ----------

def _money(v):
    return "—" if v is None else "$" + f"{float(v):,.2f}"


def _mail_shell(title_tr, title_en, inner, cta_tr, cta_en, url, foot_tr, foot_en):
    return f"""<!doctype html><html><body style="margin:0;background:#EEF1F5;font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#121A26">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:24px 12px"><tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#fff;border:1px solid #DDE2EA;border-radius:14px;overflow:hidden">
<tr><td style="height:6px;background-color:#B79CF5;background:linear-gradient(90deg,#7AD3F0,#B79CF5,#F3A6C8,#F6D58A,#9BE3C4)"></td></tr>
<tr><td style="padding:24px 28px 0"><div style="font-size:20px;font-weight:800">Holotique</div>
<h1 style="font-size:19px;margin:14px 0 4px">{title_tr}</h1>
<div style="font-size:14px;color:#5A6577" lang="en">{title_en}</div></td></tr>
<tr><td style="padding:14px 28px 4px">{inner}</td></tr>
<tr><td style="padding:12px 28px 4px"><a href="{url}" style="display:inline-block;background:#2B47D6;color:#fff;text-decoration:none;font-weight:600;font-size:15px;padding:12px 20px;border-radius:8px">{cta_tr} · {cta_en}</a></td></tr>
<tr><td style="padding:16px 28px 24px;font-size:12px;color:#8A94A6;line-height:1.5">
Fiyatlar tahmini piyasa değeridir, yatırım tavsiyesi değildir. {foot_tr}<br>
<span lang="en">Prices are estimated market values, not investment advice. {foot_en}</span><br><br>
Holotique · <a href="https://holotique.com" style="color:#8A94A6">holotique.com</a></td></tr>
</table></td></tr></table></body></html>"""


def _card_rows(items, right):
    """items: kart listesi; right(r) -> (ana satır html, alt satır html)"""
    import html as _h
    out = ""
    for r in items:
        img = f'<img src="{_h.escape(r["image"])}" width="48" style="border-radius:6px;display:block" alt="">' if r.get("image") else ""
        sub = " · ".join(x for x in [r.get("set_name") or r.get("set"), r.get("grade")] if x)
        a, b = right(r)
        out += f"""<tr><td style="padding:9px 0;border-top:1px solid #DDE2EA;width:56px;vertical-align:top">{img}</td>
<td style="padding:9px 0 9px 10px;border-top:1px solid #DDE2EA;vertical-align:top">
<div style="font-weight:600;font-size:14px">{_h.escape(r.get("name") or "")}</div>
<div style="font-size:12px;color:#5A6577">{_h.escape(sub)}</div>
<div style="font-size:14px;margin-top:3px">{a}<span style="color:#5A6577">{b}</span></div></td></tr>"""
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{out}</table>'


def _send_batch(batch, key):
    """batch: [(email, subject, text, html, on_ok)]"""
    import smtplib
    import ssl
    from email.message import EmailMessage
    from email.utils import formataddr, make_msgid
    sent, fails = 0, []
    if not batch:
        return 0, []
    with smtplib.SMTP_SSL(SMTP_HOST, 465, context=ssl.create_default_context(), timeout=30) as srv:
        srv.login(SMTP_USER, SMTP_PASSWORD)
        for email, subj, text, html, on_ok in batch[:300]:
            m = EmailMessage()
            m["Subject"] = subj
            m["From"] = formataddr(("Holotique", SMTP_USER))
            m["To"] = email
            m["Message-ID"] = make_msgid(domain="holotique.com")
            m.set_content(text)
            m.add_alternative(html, subtype="html")
            try:
                srv.send_message(m)
                on_ok()
                sent += 1
            except Exception as e:  # noqa: BLE001
                fails.append(f"{key}: {str(e)[:120]}")
    return sent, fails


def _rpc_missing(e, name):
    return name in str(e) or "PGRST202" in str(e)


# ---------- Portföy fiyat alarmı (kart hedefi ya da % hareket) ----------

def send_holding_alerts():
    if not SMTP_PASSWORD:
        return 0
    try:
        rows = sb("POST", "rpc/holding_alerts_due", body={}) or []
    except RuntimeError as e:
        if _rpc_missing(e, "holding_alerts_due"):
            STATUS["holding_alerts"] = {"skipped": "019 henüz çalıştırılmamış"}
            return 0
        raise
    by = {}
    for r in rows:
        by.setdefault(r["email"], []).append(r)
    LBL = {"above": ("hedefinin üstüne çıktı", "rose above your target"),
           "below": ("hedefinin altına indi", "fell below your target"),
           "up": ("yükseldi", "is up"), "down": ("düştü", "is down")}

    def right(r):
        k = r["kind"]
        col = "#127A47" if k in ("above", "up") else "#B7322A"
        if k in ("up", "down"):
            sign = "+" if (r.get("pct") or 0) > 0 else ""
            return (f'<b style="color:{col}">{_money(r["price"])} ({sign}{r.get("pct")}%)</b>',
                    f' · önceki / was {_money(r.get("ref"))}')
        return (f'<b style="color:{col}">{_money(r["price"])}</b>',
                f' · {"hedef / target"} {_money(r.get("ref"))}')

    batch = []
    for email, items in list(by.items()):
        first = items[0]
        if len(items) == 1:
            subj = f'{first.get("name") or "Kartın"} {LBL[first["kind"]][0]} · Holotique'
        else:
            subj = f"Portföyünde {len(items)} kartta fiyat hareketi · Holotique"
        text = "Portföyündeki kartlarda fiyat alarmı / Price alerts for your portfolio\n\n" + "\n".join(
            f'- {r.get("name")} ({r.get("grade")}): {_money(r["price"])} — {LBL[r["kind"]][0]} / {LBL[r["kind"]][1]}' for r in items) \
            + "\n\nhttps://holotique.com/portfoy.html"
        html = _mail_shell("Portföyünde fiyat alarmı", "Price alert for your portfolio", _card_rows(items, right),
                           "Portföyümü aç", "Open my portfolio", "https://holotique.com/portfoy.html",
                           "Hedefler tek seferliktir; tetiklenince silinir. Alarmları portföyünde kartın detayından ya da “Bildirimler”den değiştirebilirsin.",
                           "Targets fire once and are then cleared. Change alerts from the card details or “Notifications” in your portfolio.")
        ids = [r["holding_id"] for r in items]
        batch.append((email, subj, text, html, lambda ids=ids: sb("POST", "rpc/holding_alerts_mark", body={"ids": ids})))
    sent, fails = _send_batch(batch, "alarm")
    STATUS["holding_alerts"] = {"sent": sent, "cards": len(rows), "failed": len(fails), "examples": fails[:2]}
    log(f"Portföy alarmı maili: {sent}")
    return sent


# ---------- Haftalık özet (pazartesi, İstanbul saatiyle 09:00 sonrası) ----------

def send_weekly():
    if not SMTP_PASSWORD:
        return 0
    now = datetime.now(timezone.utc)
    if os.environ.get("WEEKLY_FORCE") != "1" and not (now.weekday() == 0 and now.hour >= 6):
        return 0
    try:
        rows = sb("POST", "rpc/weekly_digest", body={}) or []
    except RuntimeError as e:
        if _rpc_missing(e, "weekly_digest"):
            STATUS["weekly"] = {"skipped": "019 henüz çalıştırılmamış"}
            return 0
        raise
    batch = []
    for r in rows:
        d = r.get("data") or {}
        tot, prev, cost = d.get("total"), d.get("prev_total"), d.get("cost")
        chg = (float(tot) - float(prev)) if tot is not None and prev is not None else None
        pct = (chg / float(prev) * 100) if chg is not None and prev else None
        col = "#127A47" if (chg or 0) >= 0 else "#B7322A"
        sign = "+" if (chg or 0) >= 0 else "−"
        head = ""
        if tot is not None:
            head = f"""<div style="font-size:12px;color:#5A6577;text-transform:uppercase;letter-spacing:.06em">Portföy değeri · Portfolio value</div>
<div style="font-size:30px;font-weight:800;margin:2px 0">{_money(tot)}</div>"""
            if chg is not None:
                head += f'<div style="font-size:14px"><b style="color:{col}">{sign}{_money(abs(chg))[0:]}{f" ({sign}{abs(pct):.1f}%)" if pct is not None else ""}</b> <span style="color:#5A6577">bu hafta · this week</span></div>'
            if cost:
                pl = float(tot) - float(cost)
                head += f'<div style="font-size:13px;color:#5A6577;margin-top:2px">Toplam kâr/zarar · Total P/L: <b style="color:{"#127A47" if pl >= 0 else "#B7322A"}">{"+" if pl >= 0 else "−"}{_money(abs(pl))}</b> · {d.get("cards")} kart / cards</div>'

        def sec(title, items, fn):
            if not items:
                return ""
            return f'<div style="font-size:13px;font-weight:700;margin:18px 0 2px">{title}</div>' + _card_rows(items, fn)

        def mv(r):
            c = float(r.get("chg") or 0)
            return (f'<b style="color:{"#127A47" if c >= 0 else "#B7322A"}">{_money(r.get("price"))} ({"+" if c >= 0 else ""}{c:.1f}%)</b>', "")

        def wi(r):
            return (f'<b>{_money(r.get("price"))}</b>', f' · hedef / target {_money(r.get("target"))}')

        inner = head + sec("En çok yükselenler · Top gainers", d.get("up"), mv) \
            + sec("En çok düşenler · Top losers", d.get("down"), mv) \
            + sec("İstek listende hedefe yakın · Near your target", d.get("wish"), wi)
        subj = "Haftalık portföy özetin" + (f" · {sign}{abs(pct):.1f}%" if pct is not None and abs(pct) >= 0.1 else "") + " · Holotique"
        text = f"Haftalık portföy özetin / Your weekly portfolio summary\n\nPortföy değeri: {_money(tot)}" \
            + (f" ({sign}{_money(abs(chg))} bu hafta)" if chg is not None else "") + "\n\nhttps://holotique.com/portfoy.html"
        html = _mail_shell("Haftalık portföy özetin", "Your weekly portfolio summary", inner,
                           "Portföyümü aç", "Open my portfolio", "https://holotique.com/portfoy.html",
                           "Bu maili her pazartesi gönderiyoruz. Almak istemiyorsan portföyünde “Bildirimler”den kapatabilirsin.",
                           "We send this every Monday. Turn it off from “Notifications” in your portfolio.")
        uid = r["user_id"]
        batch.append((r["email"], subj, text, html, lambda uid=uid: sb("POST", "rpc/weekly_mark_sent", body={"ids": [uid]})))
    sent, fails = _send_batch(batch, "haftalık")
    STATUS["weekly"] = {"sent": sent, "users": len(rows), "failed": len(fails), "examples": fails[:2]}
    log(f"Haftalık özet maili: {sent}")
    return sent


# ---------- PSA sertifika verisi ----------

class PsaStop(Exception):
    pass


def psa_hint(psa):
    """PSA kaydından eşleştirme ipuçları: ad, numara, set, dil."""
    if not isinstance(psa, dict) or not psa.get("Subject"):
        return {}
    brand = str(psa.get("Brand") or "")
    subject = re.sub(r"\s+", " ", str(psa.get("Subject") or "")).strip().title()
    variety = str(psa.get("Variety") or "").strip()
    set_hint = re.sub(r"\b(POKEMON|JAPANESE|ENGLISH)\b", " ", brand, flags=re.I)
    set_hint = re.sub(r"\s+", " ", set_hint).strip().title()
    return {"subject": subject, "number": str(psa.get("CardNumber") or "").strip() or None,
            "set": set_hint or None, "variety": variety or None, "japanese": "JAPANESE" in brand.upper()}


def grade_from_psa(psa):
    g = str((psa or {}).get("CardGrade") or "")
    m = re.search(r"(\d+(?:\.\d)?)\s*$", g)
    return f"PSA {m.group(1).rstrip('0').rstrip('.') if '.' in m.group(1) else m.group(1)}" if m else None


def psa_get(path, budget):
    if budget["used"] >= PSA_DAILY_BUDGET:
        raise PsaStop("günlük PSA bütçesi doldu")
    time.sleep(0.6)
    budget["used"] += 1
    try:
        return http("GET", f"{PSA_API}/{path}", {"Authorization": f"bearer {PSA_TOKEN}"})
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:200]
        if e.code in (401, 403):
            raise PsaStop(f"PSA anahtarı reddedildi ({e.code}). GitHub'daki PSA_API_TOKEN'ı kontrol et. {detail}") from None
        if e.code == 429 or "limit" in detail.lower():
            budget["used"] = PSA_DAILY_BUDGET
            raise PsaStop(f"PSA günlük sınırı doldu ({e.code}).") from None
        if e.code == 404:
            return None
        raise RuntimeError(f"PSA {e.code}: {detail}") from None


def find_images(obj):
    """Görsel yanıtının şekli belgelenmemiş; içindeki görsel adreslerini ön/arka olarak ayıkla."""
    front = back = None
    items = obj if isinstance(obj, list) else (obj.get("Images") or obj.get("images") or [obj]) if isinstance(obj, dict) else []
    for it in items if isinstance(items, list) else []:
        if not isinstance(it, dict):
            continue
        url = next((v for v in it.values() if isinstance(v, str) and v.startswith("http")), None)
        if not url:
            continue
        is_front = it.get("IsFrontImage")
        if is_front is True and not front:
            front = url
        elif is_front is False and not back:
            back = url
        elif not front:
            front = url
        elif not back:
            back = url
    return front, back


def sync_psa_certs():
    if not PSA_TOKEN:
        log("PSA_API_TOKEN tanımlı değil, PSA adımı atlandı.")
        return 0
    blocked = sb("GET", "job_state", {"key": "eq.psa:blocked", "select": "value"}) or []
    if blocked:
        since = blocked[0]["value"].get("since", "")
        days = (datetime.fromisoformat(TODAY) - datetime.fromisoformat(since)).days if since else 99
        if days < 1:
            log(f"PSA erişimi onay bekliyor ({since}'den beri). PSA adımı atlandı; günde bir yeniden denenir.")
            STATUS["psa"] = {"skipped": f"onay bekliyor ({since})"}
            return 0
    try:
        rows = sb("GET", "holdings", {"select": "id,cert,grade,match_status", "cert": "not.is.null",
                                      "grade": "ilike.PSA*", "psa_checked": "is.null", "order": "created_at.asc", "limit": "60"}) or []
    except RuntimeError as e:
        log("PSA alanları veritabanında yok (supabase/migrations/002_psa.sql çalıştırılmalı). PSA adımı atlandı.", str(e)[:120])
        return 0
    STATUS["psa"] = {"waiting": len(rows), "ok": 0, "not_found": 0}
    if not rows:
        return 0
    st = sb("GET", "job_state", {"key": f"eq.psa:{TODAY}", "select": "value"}) or []
    budget = {"used": int(st[0]["value"].get("used", 0)) if st else 0}
    log(f"PSA kontrolü bekleyen kart: {len(rows)} · bugünkü PSA isteği: {budget['used']}/{PSA_DAILY_BUDGET}")
    done = 0
    try:
        for h in rows:
            cert = re.sub(r"\D", "", str(h["cert"]))
            if not cert:
                sb("PATCH", "holdings", {"id": f"eq.{h['id']}"}, {"psa_checked": TODAY, "psa_status": "invalid"})
                continue
            body = psa_get(f"cert/GetByCertNumber/{cert}", budget)
            cert_data = (body or {}).get("PSACert") if isinstance(body, dict) else None
            if not cert_data:
                sb("PATCH", "holdings", {"id": f"eq.{h['id']}"}, {"psa_checked": TODAY, "psa_status": "not_found"})
                log("PSA kaydı yok:", cert)
                STATUS["psa"]["not_found"] += 1
                continue
            front = back = None
            try:
                imgs = psa_get(f"cert/GetImagesByCertNumber/{cert}", budget)
                front, back = find_images(imgs)
            except PsaStop:
                raise
            except Exception as e:  # noqa: BLE001
                log("PSA görseli alınamadı:", cert, e)
            patch = {"psa": cert_data, "psa_front": front, "psa_back": back, "psa_checked": TODAY, "psa_status": "ok"}
            if h.get("match_status") == "failed":
                patch.update({"match_status": "pending", "match_note": None})
            sb("PATCH", "holdings", {"id": f"eq.{h['id']}"}, patch)
            g = grade_from_psa(cert_data)
            log("PSA OK", cert, "·", cert_data.get("Subject"), cert_data.get("CardNumber"), "·", cert_data.get("CardGrade"),
                "· görsel", "var" if front else "yok", "· derece farkı!" if g and h.get("grade") and g != h["grade"] else "")
            done += 1
            STATUS["psa"]["ok"] += 1
            if blocked and done == 1:
                sb("DELETE", "job_state", {"key": "eq.psa:blocked"})
    except PsaStop as e:
        log("PSA adımı durdu:", e)
        STATUS["psa"]["stopped"] = str(e)[:300]
        if "approved customers" in str(e):
            sb("POST", "job_state", {"on_conflict": "key"},
               [{"key": "psa:blocked", "value": {"since": TODAY}, "updated_at": datetime.now(timezone.utc).isoformat()}],
               prefer="resolution=merge-duplicates,return=minimal")
    finally:
        sb("POST", "job_state", {"on_conflict": "key"},
           [{"key": f"psa:{TODAY}", "value": budget, "updated_at": datetime.now(timezone.utc).isoformat()}],
           prefer="resolution=merge-duplicates,return=minimal")
    return done


# ---------- Geçmiş fiyatlar (bir kart için bir kez) ----------

DATE_KEYS = ("date", "day", "timestamp", "time", "recordedAt", "createdAt", "t")
PRICE_KEYS = ("market", "marketPrice", "price", "avg", "average", "averagePrice", "median", "medianPrice", "value", "p")


def _date_of(v):
    if isinstance(v, (int, float)) and v > 1e9:
        return datetime.fromtimestamp(v / 1000 if v > 1e11 else v, timezone.utc).date().isoformat()
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", str(v or ""))
    return m.group(1) if m else None


def _num(v):
    try:
        f = float(v)
        return round(f, 2) if f > 0 else None
    except (TypeError, ValueError):
        return None


def _as_series(node):
    """Liste [{date, price}] ya da sözlük {tarih: fiyat} biçimindeki bir geçmişi {tarih: fiyat} yapar."""
    out = {}
    if isinstance(node, list):
        for x in node:
            if isinstance(x, dict):
                d = next((_date_of(x[k]) for k in DATE_KEYS if k in x and _date_of(x[k])), None)
                v = next((_num(x[k]) for k in PRICE_KEYS if k in x and _num(x[k]) is not None), None)
                if d and v is not None:
                    out[d] = v
            elif isinstance(x, (list, tuple)) and len(x) >= 2 and _date_of(x[0]):
                v = _num(x[1])
                if v is not None:
                    out[_date_of(x[0])] = v
    elif isinstance(node, dict) and node and all(_date_of(k) for k in list(node)[:5]):
        for k, v in node.items():
            if isinstance(v, dict):
                v = next((_num(v[k2]) for k2 in PRICE_KEYS if k2 in v and _num(v[k2]) is not None), None)
            else:
                v = _num(v)
            if _date_of(k) and v is not None:
                out[_date_of(k)] = v
    return out


def _walk(node, path=()):
    """Yanıttaki tüm tarihli fiyat serilerini (yol, seri) olarak bulur."""
    ser = _as_series(node)
    if len(ser) >= 2:
        yield path, ser
        return
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _walk(v, path + (str(k),))
    elif isinstance(node, list) and node and isinstance(node[0], dict) and not ser:
        for i, v in enumerate(node[:20]):
            yield from _walk(v, path + (str(i),))


def _best(found, want, avoid=()):
    cands = [(p, s) for p, s in found if any(w in "/".join(p).lower().replace(" ", "") for w in want)
             and not any(a in "/".join(p).lower().replace(" ", "") for a in avoid)]
    if not cands:
        return {}, None
    # Önce "near mint", sonra en çok gün içeren seri
    cands.sort(key=lambda ps: (("nearmint" in "/".join(ps[0]).lower().replace(" ", "")), len(ps[1])), reverse=True)
    return cands[0][1], "/".join(cands[0][0])


# v2: tüm derecelerin geçmişi de yazılır (v1 yalnızca ham/PSA 10/PSA 9 yazıyordu).
BACKFILL_KEY = "backfill:v2"


def backfill_history(budget):
    if HAS_GRADES["ok"]:
        try:
            sb("GET", "card_prices", {"select": "grades", "limit": "1"})
        except RuntimeError:
            HAS_GRADES["ok"] = False
            STATUS["note_grades"] = "008_all_grades.sql henüz çalıştırılmamış; tüm derecelerin geçmişi bekliyor."
    if not HAS_GRADES["ok"]:
        return 0
    if HISTORY_DAYS <= 0:
        return 0
    st = sb("GET", "job_state", {"key": f"eq.{BACKFILL_KEY}", "select": "value"}) or []
    done_ids = set(st[0]["value"].get("done", [])) if st else set()
    # Geçmişi okunamayan kartlar günde en fazla bir kez yeniden denenir.
    tried = {int(k): v for k, v in (st[0]["value"].get("tried", {}) if st else {}).items()}
    ids = sorted(i for i in tracked_card_ids() - done_ids if tried.get(i) != TODAY)
    if not ids:
        return 0
    cards = sb("GET", "cards", {"select": "id,ext_id,language", "source": "eq.ppt", "id": f"in.({','.join(map(str, ids))})"}) or []
    log(f"Geçmiş fiyatı çekilecek kart: {len(cards)}")
    n = 0
    try:
        for c in cards:
            try:
                body = ppt({"tcgPlayerId": c["ext_id"], "language": c.get("language") or "english", "limit": 1,
                            "includeHistory": "true", "includeEbay": "true", "days": HISTORY_DAYS}, budget, 3)
            except BudgetExhausted:
                raise
            except Exception as e:  # noqa: BLE001
                note_error(f"geçmiş isteği (kart {c['id']})", e)
                continue
            data = body.get("data")
            d = data if isinstance(data, dict) else ((data or [{}])[0] if isinstance(data, list) else {})
            found = list(_walk(d))
            raw, raw_path = _best(found, ("pricehistory", "history"), ("ebay", "psa", "grade"))
            p10, p10_path = _best(found, ("psa10",))
            p9, p9_path = _best(found, ("psa9",), ("psa10",))
            if len(STATUS.setdefault("history_samples", [])) < 3:
                STATUS["history_samples"].append({
                    "card": c["id"], "paths": ["/".join(p) + f" ({len(s)})" for p, s in found][:12],
                    "raw": raw_path, "psa10": p10_path, "psa9": p9_path,
                    "top_keys": sorted(d.keys())[:40] if isinstance(d, dict) else str(type(d)),
                    "ph_keys": sorted((d.get("priceHistory") or {}).keys())[:12] if isinstance(d.get("priceHistory"), dict) else None})
            # Her derecenin geçmişi: ebay/.../<psa10|bgs9_5|cgc10...>
            per_grade = {}
            for pth, ser in found:
                if not pth or "ebay" not in [x.lower() for x in pth]:
                    continue
                key = next((x.lower() for x in reversed(pth) if GRADE_KEY.match(x.lower())), None)
                if key and len(ser) > len(per_grade.get(key, {})):
                    per_grade[key] = ser
            dates = sorted((set(raw) | set(p10) | set(p9) | {d for ser in per_grade.values() for d in ser}) - {TODAY})
            rows = []
            for dt in dates:
                g = {k: {"p": ser[dt]} for k, ser in per_grade.items() if ser.get(dt) is not None} or None
                if raw.get(dt) is None and p10.get(dt) is None and p9.get(dt) is None and not g:
                    continue
                rows.append({"card_id": c["id"], "date": dt, "raw": raw.get(dt), "psa10": p10.get(dt),
                             "psa9": p9.get(dt), "grades": g})
            # Yeni günler tam satır olarak eklenir; var olan günlere (günlük fiyat satırları dahil)
            # yalnızca derece verisi eklenir, mevcut ham/PSA değerlerine dokunulmaz.
            have = {r["date"] for r in (sb("GET", "card_prices", {"select": "date", "card_id": f"eq.{c['id']}", "limit": "5000"}) or [])}
            new_rows = [r for r in rows if r["date"] not in have]
            upd_rows = [{"card_id": r["card_id"], "date": r["date"], "grades": r["grades"]} for r in rows if r["date"] in have and r["grades"]]
            for chunk in (new_rows, upd_rows):
                for i in range(0, len(chunk), 500):
                    write_prices(chunk[i:i + 500])
            if rows:
                done_ids.add(c["id"])
                tried.pop(c["id"], None)
                n += 1
            else:
                tried[c["id"]] = TODAY
            log(f"Geçmiş: kart {c['id']} · {len(rows)} gün")
    except BudgetExhausted:
        pass
    finally:
        sb("POST", "job_state", {"on_conflict": "key"},
           [{"key": BACKFILL_KEY, "value": {"done": sorted(done_ids), "tried": {str(k): v for k, v in tried.items()}}, "updated_at": datetime.now(timezone.utc).isoformat()}],
           prefer="resolution=merge-duplicates,return=minimal")
    return n


def probe_grade_keys(budget):
    """Bir kez: en değerli birkaç kartın eBay derece anahtarlarını kaydeder (Pristine, Black Label adları için)."""
    if DAILY_BUDGET <= 1000 or sb("GET", "job_state", {"key": "eq.gradekeys:v1", "select": "key"}):
        return
    cards = sb("GET", "cards", {"select": "id,ext_id,language", "source": "eq.ppt", "order": "id.asc", "limit": "12"}) or []
    keys, hist = set(), set()
    for c in cards:
        try:
            body = ppt({"tcgPlayerId": c["ext_id"], "language": c.get("language") or "english", "limit": 1,
                        "includeHistory": "true", "includeEbay": "true", "days": 30}, budget, 3)
        except BudgetExhausted:
            break
        except Exception:  # noqa: BLE001
            continue
        d = body.get("data")
        d = d if isinstance(d, dict) else ((d or [{}])[0] if isinstance(d, list) else {})
        e = d.get("ebay") or {}
        keys |= set((e.get("salesByGrade") or {}).keys())
        hist |= set((e.get("priceHistory") or {}).keys()) if isinstance(e.get("priceHistory"), dict) else set()
        STATUS.setdefault("ebay_keys", sorted(e.keys()))
    STATUS["probe_sales_keys"] = sorted(keys)
    STATUS["probe_history_keys"] = sorted(hist)
    sb("POST", "job_state", {"on_conflict": "key"},
       [{"key": "gradekeys:v1", "value": {"sales": sorted(keys), "history": sorted(hist)}, "updated_at": datetime.now(timezone.utc).isoformat()}],
       prefer="resolution=merge-duplicates,return=minimal")


def retry_failed_once():
    """Daha geniş aramayla (ücretli plan) bulunamayan kartları bir kez yeniden dener."""
    if SEARCH_LIMIT <= 3:
        return
    key = f"retry_failed:limit{SEARCH_LIMIT}"
    if sb("GET", "job_state", {"key": f"eq.{key}", "select": "key"}):
        return
    sb("PATCH", "holdings", {"match_status": "eq.failed"}, {"match_status": "pending", "match_note": None})
    sb("POST", "job_state", {"on_conflict": "key"},
       [{"key": key, "value": {"at": TODAY}, "updated_at": datetime.now(timezone.utc).isoformat()}],
       prefer="resolution=merge-duplicates,return=minimal")
    log("Bulunamayan kartlar daha geniş aramayla yeniden denenecek.")


# ---------- Kurlar ----------

def fetch_fx(date=None):
    path = date or "latest"
    for u in (f"https://api.frankfurter.dev/v1/{path}?base=USD&symbols={','.join(CURRENCIES)}",
              f"https://api.frankfurter.app/{path}?from=USD&to={','.join(CURRENCIES)}"):
        try:
            d = http("GET", u)
            r = d.get("rates") or {}
            if all(k in r for k in CURRENCIES):
                return d.get("date"), {k: r[k] for k in CURRENCIES}
        except Exception as e:  # noqa: BLE001
            log("Kur kaynağı yanıt vermedi:", u, e)
    return None, None


def sync_fx():
    date, rates = fetch_fx()
    if rates:
        sb("POST", "fx_rates", {"on_conflict": "date"}, [{"date": date, "rates": rates}],
           prefer="resolution=merge-duplicates,return=minimal")
    rows = sb("GET", "holdings", {"select": "id,bought", "buy_fx": "is.null", "bought": "not.is.null", "limit": "60"}) or []
    cache = {}
    for r in rows:
        if r["bought"] not in cache:
            cache[r["bought"]] = fetch_fx(r["bought"])[1]
        if cache[r["bought"]]:
            sb("PATCH", "holdings", {"id": f"eq.{r['id']}"}, {"buy_fx": cache[r["bought"]]})


def main():
    missing = [n for n, v in (("SUPABASE_URL", SUPA), ("SUPABASE_SECRET_KEY", SKEY), ("PPT_KEY", PKEY)) if not v]
    if missing:
        sys.exit("Eksik ayar: " + ", ".join(missing))
    try:
        budget = Budget()
    except RuntimeError as e:
        if "PGRST205" in str(e) or "does not exist" in str(e) or " 404 " in str(e):
            log("Veritabanı tabloları henüz kurulmamış (supabase/schema.sql). Görev atlandı.")
            return
        raise
    log(f"Bugün ({TODAY}) kullanılan kredi: {budget.used}/{DAILY_BUDGET}")
    try:
        sync_fx()
    except Exception as e:  # noqa: BLE001
        log("Kur güncellemesi atlandı:", e)
    try:
        n = sync_psa_certs()
        if n:
            log(f"PSA verisi alınan kart: {n}")
    except Exception as e:  # noqa: BLE001
        log("PSA adımı hata verdi:", e)
        note_error("PSA", e)
    STATUS.update({"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "credits_before": budget.used})
    m = p = 0
    try:
        # Önce eşleşmiş kartların fiyatı (bütçenin en fazla %60'ı), sonra yeni eşleştirmeler,
        # en son kalan krediyle bugün fiyatlanmamış kartlar.
        retry_failed_once()
        p = price_cards(budget, cap=budget.used + int(budget.left * PRICE_SHARE))
        m = match_pending(budget)
        p += price_cards(budget)
        try:
            cache_images()
        except Exception as e:  # noqa: BLE001
            note_error("görsel kopyalama", e)
        try:
            send_alerts()
        except Exception as e:  # noqa: BLE001
            note_error("fiyat alarmı", e)
        try:
            send_holding_alerts()
        except Exception as e:  # noqa: BLE001
            note_error("portföy alarmı", e)
        try:
            send_weekly()
        except Exception as e:  # noqa: BLE001
            note_error("haftalık özet", e)
        STATUS["history_backfilled"] = backfill_history(budget)
        probe_grade_keys(budget)
    except Exception as e:  # noqa: BLE001
        note_error("görev", e)
        raise
    finally:
        budget.save()
        try:
            counts = {}
            for st in ("pending", "matched", "failed", "unsupported"):
                counts[st] = len(sb("GET", "holdings", {"select": "id", "match_status": f"eq.{st}"}) or [])
            STATUS["holdings"] = counts
            STATUS["cards_priced_ever"] = len({r["card_id"] for r in (sb("GET", "card_prices", {"select": "card_id"}) or [])})
            STATUS["price_rows_today"] = len(sb("GET", "card_prices", {"select": "card_id", "date": f"eq.{TODAY}"}) or [])
        except Exception as e:  # noqa: BLE001
            STATUS["errors"].append(f"durum sayımı: {str(e)[:200]}")
        STATUS.update({"matched_this_run": m, "priced_this_run": p, "credits_after": budget.used})
        with open(os.environ.get("STATUS_FILE", "status.json"), "w", encoding="utf-8") as f:
            json.dump(STATUS, f, ensure_ascii=False, indent=1)
    log(f"Eşleştirilen: {m} · fiyatlanan: {p} · kalan kredi: {budget.left}")


if __name__ == "__main__":
    main()
