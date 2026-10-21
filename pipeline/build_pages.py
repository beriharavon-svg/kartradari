"""Holotique · arama motorları için statik kart ve set sayfaları + site haritası.

Her gece katalogdan en değerli kartları (ve portföy/istek listelerinde takip edilen kartları) seçer,
her biri için /kart/<ad>-<set>-<numara>-<id> sayfası, her set için /set/<oyun>-<set>-<id> sayfası,
/setler sayfası, sitemap.xml ve robots.txt üretir. Çıktı, GitHub Pages'e yüklenecek klasöre yazılır
(depoya commit edilmez).

Ortam: SUPABASE_URL, SUPABASE_SECRET_KEY, OUT_DIR (varsayılan _site)
"""
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

SUPA = os.environ.get("SUPABASE_URL", "").rstrip("/")
SKEY = os.environ.get("SUPABASE_SECRET_KEY", "")
OUT = os.environ.get("OUT_DIR", "_site")
SITE = "https://holotique.com"
UA = "Holotique-pages/1.0 (+https://holotique.com)"
TODAY = datetime.now(timezone.utc).date().isoformat()

# Oyun başına sayfası üretilecek en değerli kart sayısı
LIMITS = {"Pokemon": 4000, "Pokemon JP": 1500, "One Piece": 1500, "Magic": 2000, "Lorcana": 600, "Riftbound": 400}
GAME_LABEL = {"Pokemon": "Pokemon", "Pokemon JP": "Pokemon (Japonca)", "One Piece": "One Piece", "Magic": "Magic: The Gathering",
              "Lorcana": "Disney Lorcana", "Riftbound": "Riftbound"}
MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
GRADE_ORDER = ["psa10", "psa9", "bgs10", "bgs9_5", "cgc10", "cgc9_5", "sgc10", "tag10", "psa8"]

e = html.escape


def log(*a):
    print(*a, flush=True)


def sb(path, params):
    url = f"{SUPA}/rest/v1/{path}?" + urllib.parse.urlencode(params, safe=",.()*:")
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"apikey": SKEY, "User-Agent": UA})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode("utf-8") or "[]")
        except Exception as ex:  # noqa: BLE001
            if attempt == 3:
                raise
            log("tekrar:", path, str(ex)[:120])
            time.sleep(4 * (attempt + 1))


def sb_all(path, params, cap=200000):
    out, off = [], 0
    while off < cap:
        rows = sb(path, {**params, "limit": "1000", "offset": str(off)})
        out += rows
        if len(rows) < 1000:
            break
        off += 1000
    return out


def slug(s):
    s = str(s or "").lower()
    for a, b in (("ı", "i"), ("ş", "s"), ("ğ", "g"), ("ü", "u"), ("ö", "o"), ("ç", "c"), ("é", "e"), ("’", ""), ("'", "")):
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:70].strip("-")


def usd(v):
    if v is None:
        return "—"
    v = float(v)
    return "$" + (f"{v:,.0f}" if v >= 1000 else f"{v:,.2f}")


def trdate(iso):
    try:
        y, m, d = str(iso)[:10].split("-")
        return f"{int(d)} {MONTHS[int(m) - 1]} {y}"
    except Exception:  # noqa: BLE001
        return ""


def grade_label(k):
    m = re.match(r"^([a-z]+)(\d+)(?:_(5))?", k)
    return f"{m.group(1).upper()} {m.group(2)}{'.5' if m.group(3) else ''}" if m else k


def card_path(c):
    base = slug(f"{c['name']} {c.get('set_name') or ''} {c.get('number') or ''}") or "kart"
    return f"kart/{base}-{c['product_id']}"


def set_path(game, set_name, gid):
    return f"set/{slug(game)}-{slug(set_name) or 'set'}-{gid}"


def page(title, desc, canonical, body, extra_head=""):
    return f"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{SITE}/{canonical}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Holotique">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{SITE}/{canonical}">
<link rel="icon" href="/favicon-32.png" sizes="32x32" type="image/png">
<link rel="icon" href="/icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/manifest.webmanifest">
<meta name="theme-color" content="#EEF1F5">
<link rel="stylesheet" href="/seo.css">
<script src="/i18n.js"></script>
{extra_head}</head>
<body>
<header class="top"><div class="wrap">
  <a class="brand" href="/"><span class="mark" aria-hidden="true"></span><span class="bname">Holotique</span></a>
  <nav class="nav" aria-label="Sayfalar"><a href="/">Kart ara</a><a href="/setler">Setler</a><a href="/portfoy.html">Portföyüm</a></nav>
</div></header>
<main class="wrap">
{body}
</main>
<footer class="wrap foot">
  <span>Ham fiyatlar: TCGplayer piyasa fiyatı (TCGCSV aracılığıyla). PSA fiyatları: eBay satışları (PokemonPriceTracker). Fiyatlar bilgi amaçlıdır, yatırım tavsiyesi değildir.</span>
  <span><a href="/gizlilik.html">Gizlilik</a> · <a href="mailto:info@holotique.com">info@holotique.com</a></span>
</footer>
</body>
</html>
"""


def crumbs_ld(items):
    return '<script type="application/ld+json">' + json.dumps({
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": n, "item": f"{SITE}/{u}"} for i, (n, u) in enumerate(items)],
    }, ensure_ascii=False) + "</script>\n"


def crumbs_html(items):
    parts = [f'<a href="/{u}">{e(n)}</a>' for n, u in items[:-1]] + [f"<span>{e(items[-1][0])}</span>"]
    return '<nav class="crumbs" aria-label="Konum">' + " › ".join(parts) + "</nav>"


def build_card(c, tracked, siblings, set_url):
    game = c["game"]
    gl = GAME_LABEL.get(game, game)
    name, sname, num = c["name"], c.get("set_name") or "", c.get("number") or ""
    p = tracked.get(str(c["product_id"])) or {}
    img = p.get("image") or c.get("image")
    psa10, psa9 = p.get("psa10"), p.get("psa9")
    title = f"{name}{' ' + num if num and num not in name else ''} – {sname} fiyatı | Holotique"
    bits = [f"ham {usd(c.get('market'))}"] if c.get("market") is not None else []
    if psa10 is not None:
        bits.append(f"PSA 10 {usd(psa10)}")
    if psa9 is not None:
        bits.append(f"PSA 9 {usd(psa9)}")
    desc = (f"{name} ({sname}{', ' + num if num else ''}) güncel piyasa fiyatı: " + ", ".join(bits) +
            f". {gl} kart fiyatlarını takip et, koleksiyonunu portföy gibi yönet.") if bits else \
        f"{name} ({sname}{', ' + num if num else ''}) kart bilgileri ve fiyatı. {gl} koleksiyonunu Holotique ile takip et."
    path = card_path(c)
    items = [("Holotique", ""), (gl, f"?g={urllib.parse.quote(game)}"), (sname or "Set", set_url), (name, path)]
    lang = "japanese" if game == "Pokemon JP" else "english"
    pre = {"game": "Pokemon" if game == "Pokemon JP" else game, "set_input": sname,
           "name_input": re.sub(r"\s*\(\d+\)\s*$", "", re.sub(r"\s*-\s*[\w/-]+$", "", name)),
           "number_input": num.split("/")[0] if num else None, "language": lang}
    wish = {"product_id": c["product_id"], "name": name, "set_name": sname, "number": num, "image": c.get("image"), "game": game}
    cells = [("Ham · piyasa", usd(c.get("market")), "TCGplayer")]
    if game in ("Pokemon", "Pokemon JP"):
        cells.append(("PSA 9", usd(psa9), "eBay satışları" if psa9 is not None else "sitede getir"))
        cells.append(("PSA 10", usd(psa10), "eBay satışları" if psa10 is not None else "sitede getir"))
    grades = p.get("grades") or {}
    others = [(k, grades[k]["p"]) for k in sorted(grades, key=lambda k: (GRADE_ORDER.index(k) if k in GRADE_ORDER else 99, k))
              if k not in ("psa10", "psa9") and isinstance(grades.get(k), dict) and grades[k].get("p") is not None][:10]
    facts = [("Oyun", gl), ("Set", sname), ("Numara", num or "—"), ("Nadirlik", c.get("rarity") or "—"),
             ("Baskı", c.get("sub_type") or "—"), ("En düşük ilan", usd(c.get("low"))),
             ("Fiyat tarihi", trdate(p.get("date") or c.get("price_date")) or "—")]
    sib = "".join(f'<a class="sib" href="/{card_path(s)}"><span>{e(s["name"])}</span><b>{e(usd(s.get("market")))}</b></a>'
                  for s in siblings[:12])
    body = f"""{crumbs_html(items)}
<article class="card-page">
  <div class="art">{f'<img src="{e(img)}" alt="{e(name)} – {e(sname)}" loading="eager" referrerpolicy="no-referrer">' if img else '<span class="ph">Görsel yok</span>'}</div>
  <div class="info">
    <div class="label">{e(gl)}</div>
    <h1>{e(name)}</h1>
    <p class="muted">{e(sname)}{' · ' + e(num) if num else ''}</p>
    <div class="cells">{''.join(f'<div><div class="label">{e(a)}</div><div class="v">{e(b)}</div><div class="c">{e(d)}</div></div>' for a, b, d in cells)}</div>
    {('<div class="label" style="margin-top:4px">Diğer dereceler</div><div class="gchips">' + ''.join(f'<span class="gch"><b>{e(grade_label(k))}</b> {e(usd(v))}</span>' for k, v in others) + '</div>') if others else ''}
    <dl class="facts">{''.join(f'<dt>{e(a)}</dt><dd>{e(b)}</dd>' for a, b in facts)}</dl>
    <div class="actions">
      <a class="btn" href="/portfoy.html?ekle={e(urllib.parse.quote(json.dumps(pre, ensure_ascii=False)))}">Portföyüme ekle</a>
      <a class="btn ghost" href="/portfoy.html?istek={e(urllib.parse.quote(json.dumps(wish, ensure_ascii=False)))}">☆ İstek listeme ekle</a>
      <a class="btn ghost" href="/?q={e(urllib.parse.quote(name))}&amp;g={e(urllib.parse.quote(game))}">Güncel fiyatı ve geçmişi gör</a>
    </div>
    <p class="note">Holotique ile koleksiyonunu ücretsiz takip edebilir, fiyat alarmı kurabilir ve kartlarını bir vitrin bağlantısıyla paylaşabilirsin.</p>
  </div>
</article>
{f'<section class="more"><h2>{e(sname)} setinden diğer kartlar</h2><div class="sibs">{sib}</div><p><a href="/{set_url}">{e(sname)} setinin tüm kartları ve fiyatları →</a></p></section>' if sib else ''}
"""
    return path, page(title, desc[:300], path, body, crumbs_ld(items))


def build_set(game, sname, gid, cards, has_page, released):
    gl = GAME_LABEL.get(game, game)
    path = set_path(game, sname, gid)
    top = [c for c in cards if c.get("market") is not None][:3]
    desc = f"{sname} ({gl}) kart listesi ve güncel fiyatları: {len(cards)} kart." + \
        (" En değerliler: " + ", ".join(f"{c['name']} {usd(c['market'])}" for c in top) + "." if top else "")
    items = [("Holotique", ""), (gl, f"?g={urllib.parse.quote(game)}"), (sname, path)]
    rows = []
    for c in cards:
        link = f"/{card_path(c)}" if c["product_id"] in has_page else f"/?q={urllib.parse.quote(c['name'])}&g={urllib.parse.quote(game)}&set={gid}"
        rows.append(f'<tr><td class="n">{e(c.get("number") or "")}</td><td><a href="{e(link)}">{e(c["name"])}</a></td>'
                    f'<td class="r">{e(c.get("rarity") or "")}</td><td class="p">{e(usd(c.get("market")))}</td></tr>')
    body = f"""{crumbs_html(items)}
<section class="set-page">
  <div class="label">{e(gl)}{' · ' + e(trdate(released)) if released else ''}</div>
  <h1>{e(sname)} kart listesi ve fiyatları</h1>
  <p class="muted">{len(cards)} kart · fiyatlar TCGplayer piyasa fiyatıdır, her gün güncellenir. <a href="/?g={e(urllib.parse.quote(game))}&amp;set={gid}">Bu sette ara →</a></p>
  <div class="tblwrap"><table class="tbl"><thead><tr><th>No</th><th>Kart</th><th>Nadirlik</th><th>Piyasa</th></tr></thead><tbody>
  {''.join(rows)}
  </tbody></table></div>
</section>
"""
    return path, page(f"{sname} kart listesi ve fiyatları ({gl}) | Holotique", desc[:300], path, body, crumbs_ld(items))


def write(rel, content):
    full = os.path.join(OUT, rel + ("" if rel.endswith((".xml", ".txt")) else ".html"))
    os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    if not (SUPA and SKEY):
        sys.exit("Eksik ayar: SUPABASE_URL / SUPABASE_SECRET_KEY")
    fields = "product_id,game,group_id,set_name,name,number,rarity,image,sub_type,market,low,price_date,released"

    # 1) Takip edilen kartların (PSA dahil) son fiyatları
    tracked = {}
    cards = sb_all("cards", {"select": "id,ext_id,source,image,image_cached"})
    by_id = {c["id"]: c for c in cards}
    since = (datetime.now(timezone.utc).date() - timedelta(days=10)).isoformat()
    try:
        prices = sb_all("card_prices", {"select": "card_id,date,raw,psa10,psa9,grades", "date": f"gte.{since}", "order": "date.asc"})
    except Exception:  # noqa: BLE001  (grades sütunu yoksa)
        prices = sb_all("card_prices", {"select": "card_id,date,raw,psa10,psa9", "date": f"gte.{since}", "order": "date.asc"})
    for pr in prices:
        c = by_id.get(pr["card_id"])
        if not c:
            continue
        t = tracked.setdefault(c["ext_id"], {"image": c.get("image_cached")})
        t["date"] = pr["date"]
        for k in ("psa10", "psa9", "grades"):
            if pr.get(k) is not None:
                t[k] = pr[k]
    log(f"Fiyatı bilinen takipli kart: {len(tracked)}")

    # 2) Oyun başına en değerli kartlar + takip edilenler
    chosen = {}
    for game, lim in LIMITS.items():
        rows = sb_all("catalog", {"select": fields, "game": f"eq.{game}", "market": "not.is.null", "number": "not.is.null",
                                  "order": "market.desc"}, cap=lim)
        for r in rows[:lim]:
            chosen[r["product_id"]] = r
        log(f"{game}: {min(len(rows), lim)} kart")
    extra = [int(x) for x in tracked if str(x).isdigit() and int(x) not in chosen]
    for i in range(0, len(extra), 200):
        for r in sb("catalog", {"select": fields, "product_id": f"in.({','.join(map(str, extra[i:i + 200]))})"}):
            chosen[r["product_id"]] = r
    has_page = set(chosen)
    log(f"Kart sayfası: {len(has_page)}")

    # 3) Setler: seçilen kartların setlerindeki tüm kartlar
    groups = {}
    for r in chosen.values():
        if r.get("group_id") is not None:
            groups.setdefault((r["game"], r["group_id"]), r)
    set_cards = {}
    gids = sorted({g for _, g in groups})
    for i in range(0, len(gids), 40):
        rows = sb_all("catalog", {"select": fields, "group_id": f"in.({','.join(map(str, gids[i:i + 40]))})", "number": "not.is.null"})
        for r in rows:
            set_cards.setdefault((r["game"], r["group_id"]), []).append(r)
    log(f"Set sayfası: {len(groups)}")

    def num_key(c):
        n = str(c.get("number") or "")
        m = re.search(r"(\d+)", n)
        return (int(m.group(1)) if m else 10 ** 6, n)

    urls = []
    set_urls = {}
    for (game, gid), r0 in groups.items():
        lst = sorted(set_cards.get((game, gid), []), key=num_key)
        path, html_ = build_set(game, r0.get("set_name") or "Set", gid, lst, has_page, r0.get("released"))
        write(path, html_)
        set_urls[(game, gid)] = path
        urls.append(path)
    for r in chosen.values():
        key = (r["game"], r.get("group_id"))
        sibs = sorted([s for s in set_cards.get(key, []) if s["product_id"] in has_page and s["product_id"] != r["product_id"]],
                      key=lambda s: -(s.get("market") or 0))
        path, html_ = build_card(r, tracked, sibs, set_urls.get(key, ""))
        write(path, html_)
        urls.append(path)

    # 4) Set dizini
    by_game = {}
    for (game, gid), path in set_urls.items():
        r0 = groups[(game, gid)]
        by_game.setdefault(game, []).append((r0.get("released") or "", r0.get("set_name") or "Set", path, len(set_cards.get((game, gid), []))))
    secs = []
    for game in LIMITS:
        lst = sorted(by_game.get(game, []), key=lambda x: x[0], reverse=True)
        if lst:
            secs.append(f'<section class="more"><h2>{e(GAME_LABEL[game])}</h2><div class="sets">' +
                        "".join(f'<a href="/{p}"><span>{e(n)}</span><b>{c} kart</b></a>' for _, n, p, c in lst) + "</div></section>")
    write("setler", page("Kart setleri ve fiyat listeleri | Holotique",
                         "Pokemon, Japon Pokemon, One Piece, Magic, Riftbound ve Lorcana setlerinin kart listeleri ve güncel fiyatları.",
                         "setler", '<h1 style="margin-top:22px">Kart setleri</h1>' + "".join(secs)))
    urls.append("setler")

    # 5) Site haritası (dosya başına en fazla 45.000 adres) + robots.txt
    base = ["", "portfoy.html", "gizlilik.html"]
    allu = base + urls
    chunks = [allu[i:i + 45000] for i in range(0, len(allu), 45000)]
    names = []
    for i, ch in enumerate(chunks):
        nm = f"sitemap-{i + 1}.xml"
        names.append(nm)
        write(nm, '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
              "".join(f"<url><loc>{SITE}/{e(u)}</loc><lastmod>{TODAY}</lastmod></url>\n" for u in ch) + "</urlset>\n")
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
          "".join(f"<sitemap><loc>{SITE}/{n}</loc><lastmod>{TODAY}</lastmod></sitemap>\n" for n in names) + "</sitemapindex>\n")
    write("robots.txt", f"User-agent: *\nAllow: /\nDisallow: /admin.html\n\nSitemap: {SITE}/sitemap.xml\n")
    log(f"Bitti · {len(allu)} adres")


if __name__ == "__main__":
    main()
