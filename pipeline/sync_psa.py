"""KartRadarı PSA fiyat görevi.

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
UA = "KartRadari/0.2 (+https://github.com/beriharavon-svg/kartradari)"
CURRENCIES = ["TRY", "EUR", "GBP", "JPY", "CNY"]
SEARCH_LIMIT = 3
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


def match_pending(budget):
    params = {"match_status": "eq.pending", "order": "created_at.asc", "limit": "200"}
    try:
        pending = sb("GET", "holdings", {**params, "select": "id,game,set_input,name_input,number_input,language,psa"}) or []
    except RuntimeError:
        pending = sb("GET", "holdings", {**params, "select": "id,game,set_input,name_input,number_input,language"}) or []
    if not pending:
        return 0
    log(f"Eşleşme bekleyen kart: {len(pending)}")
    cap_used = budget.used + int(budget.left * MATCH_SHARE)
    done = 0
    memo = {}
    for h in pending:
        game = (h.get("game") or "Pokemon").strip()
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

def grade_price(g):
    if not isinstance(g, dict):
        return None, None, None
    sm = g.get("smartMarketPrice") or {}
    price = sm.get("price") or g.get("marketPrice7Day") or g.get("medianPrice") or g.get("averagePrice")
    return (round(float(price), 2) if price else None), sm.get("confidence"), g.get("count")


def price_cards(budget, cap=None):
    matched = sb("GET", "holdings", {"select": "card_id", "match_status": "eq.matched", "card_id": "not.is.null"}) or []
    ids = sorted({r["card_id"] for r in matched})
    if not ids:
        return 0
    cards = sb("GET", "cards", {"select": "id,ext_id,language,last_priced", "id": f"in.({','.join(map(str, ids))})"}) or []
    if os.environ.get("FORCE_REPRICE") == "1":
        have = {r["card_id"] for r in (sb("GET", "card_prices", {"select": "card_id", "date": f"eq.{TODAY}"}) or [])}
        todo = [c for c in cards if c["id"] not in have]
    else:
        todo = [c for c in cards if c.get("last_priced") != TODAY]
    todo.sort(key=lambda c: c.get("last_priced") or "")
    log(f"Takip edilen kart: {len(cards)} · bugün fiyatlanacak: {len(todo)}")
    done = 0
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
            sb("POST", "card_prices", {"on_conflict": "card_id,date"}, [{
                "card_id": c["id"], "date": TODAY, "raw": raw, "psa10": p10, "psa10_conf": c10, "psa10_n": n10,
                "psa9": p9, "psa9_conf": c9, "psa9_n": n9}], prefer="resolution=merge-duplicates,return=minimal")
            sb("PATCH", "cards", {"id": f"eq.{c['id']}"}, {
                "last_priced": TODAY, "image": d.get("imageCdnUrl400") or d.get("imageUrl"), "url": d.get("tcgPlayerUrl")})
            done += 1
        except Exception as e:  # noqa: BLE001
            note_error(f"fiyat kaydı (kart {c['id']})", e)
    return done


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
        if days < 7:
            log(f"PSA erişimi onay bekliyor ({since}'den beri). PSA adımı atlandı; haftada bir yeniden denenir.")
            return 0
    try:
        rows = sb("GET", "holdings", {"select": "id,cert,grade,match_status", "cert": "not.is.null",
                                      "psa_checked": "is.null", "order": "created_at.asc", "limit": "60"}) or []
    except RuntimeError as e:
        log("PSA alanları veritabanında yok (supabase/migrations/002_psa.sql çalıştırılmalı). PSA adımı atlandı.", str(e)[:120])
        return 0
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
    except PsaStop as e:
        log("PSA adımı durdu:", e)
        if "approved customers" in str(e):
            sb("POST", "job_state", {"on_conflict": "key"},
               [{"key": "psa:blocked", "value": {"since": TODAY}, "updated_at": datetime.now(timezone.utc).isoformat()}],
               prefer="resolution=merge-duplicates,return=minimal")
    finally:
        sb("POST", "job_state", {"on_conflict": "key"},
           [{"key": f"psa:{TODAY}", "value": budget, "updated_at": datetime.now(timezone.utc).isoformat()}],
           prefer="resolution=merge-duplicates,return=minimal")
    return done


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
    STATUS.update({"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "credits_before": budget.used})
    m = p = 0
    try:
        # Önce eşleşmiş kartların fiyatı (bütçenin en fazla %60'ı), sonra yeni eşleştirmeler,
        # en son kalan krediyle bugün fiyatlanmamış kartlar.
        p = price_cards(budget, cap=budget.used + int(budget.left * PRICE_SHARE))
        m = match_pending(budget)
        p += price_cards(budget)
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
