"""Piyasa takibi: en değerli Pokemon kartlarının (İngilizce + Japonca) fiyatını ve eBay satış özetini her gün günceller.

Kullanıcıların portföy/istek listesi kartları bu görevin dışındadır (onları 15 dakikalık görev fiyatlar).
Ortam: SUPABASE_URL, SUPABASE_SECRET_KEY, PPT_KEY, MARKET_TOP_EN (2000), MARKET_TOP_JP (500), MARKET_BUDGET (5200)
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))
import sync_psa as s  # noqa: E402

TOP_EN = int(os.environ.get("MARKET_TOP_EN", "2000"))
TOP_JP = int(os.environ.get("MARKET_TOP_JP", "500"))
CAP = int(os.environ.get("MARKET_BUDGET", "5200"))
KEEP_DAYS = 150          # yalnızca piyasa takibindeki kartların günlük fiyat kayıtları bu kadar gün tutulur
KEEP_GRADES = {"psa10", "psa9", "psa8", "bgs10", "bgs9_5", "cgc10", "cgc9_5", "tag10", "sgc10"}
STATUS = {"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "errors": []}


class MarketBudget(s.Budget):
    """Kullanıcı görevinin sayacından ayrı tutulur (iki görev aynı anda çalışabilir)."""
    def __init__(self):
        rows = s.sb("GET", "job_state", {"key": f"eq.ppt-market:{s.TODAY}", "select": "value"}) or []
        self.used = int(rows[0]["value"].get("used", 0)) if rows else 0

    @property
    def left(self):
        return max(0, CAP - self.used)

    def save(self):
        s.sb("POST", "job_state", {"on_conflict": "key"},
             [{"key": f"ppt-market:{s.TODAY}", "value": {"used": self.used},
               "updated_at": datetime.now(timezone.utc).isoformat()}],
             prefer="resolution=merge-duplicates,return=minimal")


def top_products(game, n):
    out, off = [], 0
    while len(out) < n:
        rows = s.sb("GET", "catalog", {"select": "product_id,name,market", "game": f"eq.{game}", "number": "not.is.null",
                                       "market": "not.is.null", "order": "market.desc,product_id", "limit": "1000",
                                       "offset": str(off)}) or []
        out += rows
        if len(rows) < 1000:
            break
        off += 1000
    return out[:n]


def tracked_ids():
    try:
        return s.tracked_card_ids()
    except Exception:  # noqa: BLE001
        return set()


def main():
    budget = MarketBudget()
    want = [(p["product_id"], "english") for p in top_products("Pokemon", TOP_EN)] + \
           [(p["product_id"], "japanese") for p in top_products("Pokemon JP", TOP_JP)]
    STATUS["selected"] = len(want)
    # Var olan kart kayıtları (ext_id -> kayıt)
    existing = {}
    ids = [str(p) for p, _ in want]
    for i in range(0, len(ids), 200):
        for c in s.sb("GET", "cards", {"select": "id,ext_id,language,last_priced", "source": "eq.ppt",
                                       "ext_id": f"in.({','.join(ids[i:i + 200])})"}) or []:
            existing[(c["ext_id"], c.get("language") or "english")] = c
    tracked = tracked_ids()
    done = skipped = missing = 0
    watch_ids = set()
    t0 = time.time()
    for pid, lang in want:
        c = existing.get((str(pid), lang))
        if c:
            watch_ids.add(c["id"])
            if c["id"] in tracked or c.get("last_priced") == s.TODAY:
                skipped += 1          # kullanıcı kartı (15 dakikalık görev fiyatlar) ya da bugün zaten fiyatlandı
                continue
        if budget.left < 2:
            STATUS["stopped"] = "kredi sınırı"
            break
        if time.time() - t0 > 100 * 60:
            STATUS["stopped"] = "süre sınırı"
            break
        try:
            body = s.ppt({"tcgPlayerId": str(pid), "language": lang, "includeEbay": "true", "limit": 1}, budget, 2)
        except s.BudgetExhausted:
            STATUS["stopped"] = "kredi sınırı (API)"
            break
        except Exception as e:  # noqa: BLE001
            STATUS["errors"].append(f"{pid}: {str(e)[:120]}")
            continue
        try:
            data = body.get("data")
            d = data[0] if isinstance(data, list) and data else (data if isinstance(data, dict) else None)
            if not d:
                missing += 1
                if c:
                    s.sb("PATCH", "cards", {"id": f"eq.{c['id']}"}, {"last_priced": s.TODAY})
                continue
            cid = c["id"] if c else s.upsert_card(d, "Pokemon", lang)
            watch_ids.add(cid)
            grades = ((d.get("ebay") or {}).get("salesByGrade")) or {}
            p10, c10, n10 = s.grade_price(grades.get("psa10"))
            p9, c9, n9 = s.grade_price(grades.get("psa9"))
            allg = s.all_grades(grades) or {}
            allg = {k: v for k, v in allg.items() if k in KEEP_GRADES} or None
            s.write_prices([{"card_id": cid, "date": s.TODAY, "raw": (d.get("prices") or {}).get("market"),
                             "psa10": p10, "psa10_conf": c10, "psa10_n": n10, "psa9": p9, "psa9_conf": c9, "psa9_n": n9,
                             "grades": allg}])
            prev = (s.sb("GET", "cards", {"select": "sales", "id": f"eq.{cid}"}) or [{}])[0].get("sales") if c else None
            s.sb("PATCH", "cards", {"id": f"eq.{cid}"}, {
                "last_priced": s.TODAY, "image": d.get("imageCdnUrl400") or d.get("imageUrl"), "url": d.get("tcgPlayerUrl"),
                "sales": s.merge_sales(prev, s.sales_summary(d.get("ebay")))})
            done += 1
            if done % 100 == 0:
                budget.save()
                s.log(f"{done} kart · {budget.used} kredi")
        except Exception as e:  # noqa: BLE001
            STATUS["errors"].append(f"kayıt {pid}: {str(e)[:120]}")
    budget.save()
    # Saklama: yalnızca piyasa takibindeki (kullanıcıların takip etmediği) kartların eski günlük kayıtlarını sil
    cut = (datetime.now(timezone.utc).date() - timedelta(days=KEEP_DAYS)).isoformat()
    only = sorted(watch_ids - tracked)
    for i in range(0, len(only), 200):
        try:
            s.sb("DELETE", "card_prices", {"card_id": f"in.({','.join(map(str, only[i:i + 200]))})", "date": f"lt.{cut}"},
                 prefer="return=minimal")
        except Exception as e:  # noqa: BLE001
            STATUS["errors"].append(f"saklama: {str(e)[:120]}")
            break
    STATUS.update({"priced": done, "skipped": skipped, "no_data": missing, "credits": budget.used,
                   "minutes": round((time.time() - t0) / 60, 1), "errors": STATUS["errors"][:10]})
    with open(os.environ.get("STATUS_FILE", "market-status.json"), "w", encoding="utf-8") as f:
        json.dump(STATUS, f, ensure_ascii=False, indent=1)
    s.log(json.dumps(STATUS, ensure_ascii=False))


if __name__ == "__main__":
    main()
