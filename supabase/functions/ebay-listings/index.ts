// Holotique · ebay-listings
// Kart detayında "eBay'de şu an" bölümü: eBay'deki satıştaki ilanların fiyat aralığı ve en uygun birkaç ilan.
// Sonuçlar 6 saat önbellekte tutulur (eBay API günlük sınırı için).
// Gerekli gizli ayarlar (Edge Functions → Secrets): EBAY_CLIENT_ID, EBAY_CLIENT_SECRET
// İsteğe bağlı: EBAY_CAMPAIGN_ID (eBay Partner Network kampanya numarası; varsa bağlantılar affiliate olur)

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const CACHE_HOURS = 6;
// eBay kategorileri: CCG tekli kartlar (Pokemon, Magic, One Piece, Lorcana, Riftbound...)
const CATEGORY_TCG = "183454";
// Spor kartları: Sports Mem, Cards & Fan Shop > Sports Trading Cards > Trading Card Singles
const CATEGORY_SPORTS = "261328";
let TOKEN: { v: string; exp: number } | null = null;

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { ...CORS, "Content-Type": "application/json" } });
}

async function ebayToken(id: string, secret: string) {
  if (TOKEN && TOKEN.exp > Date.now() + 60_000) return TOKEN.v;
  const r = await fetch("https://api.ebay.com/identity/v1/oauth2/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded", Authorization: "Basic " + btoa(`${id}:${secret}`) },
    body: "grant_type=client_credentials&scope=" + encodeURIComponent("https://api.ebay.com/oauth/api_scope"),
  });
  if (!r.ok) throw new Error(`eBay oturum açılamadı (${r.status}) ${(await r.text()).slice(0, 160)}`);
  const j = await r.json();
  TOKEN = { v: j.access_token, exp: Date.now() + (Number(j.expires_in) || 7200) * 1000 };
  return TOKEN.v;
}

function median(a: number[]) {
  if (!a.length) return null;
  const s = [...a].sort((x, y) => x - y), m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "POST") return json({ error: "method" }, 405);
  const ID = Deno.env.get("EBAY_CLIENT_ID"), SECRET = Deno.env.get("EBAY_CLIENT_SECRET");
  if (!ID || !SECRET) return json({ error: "eBay anahtarları tanımlı değil" }, 500);
  const CAMPAIGN = Deno.env.get("EBAY_CAMPAIGN_ID") || "";
  const SUPA = Deno.env.get("SUPABASE_URL")!;
  let KEY = Deno.env.get("SB_SECRET_KEY") || "";
  if (!KEY) { try { const m = JSON.parse(Deno.env.get("SUPABASE_SECRET_KEYS") || "{}"); KEY = m.default || (Object.values(m)[0] as string) || ""; } catch (_) { /* yok */ } }
  if (!KEY) KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
  const H: Record<string, string> = { apikey: KEY, "Content-Type": "application/json" };
  if (KEY.startsWith("ey")) H.Authorization = `Bearer ${KEY}`;

  try {
    const body = await req.json().catch(() => ({}));
    const cacheGet = async (k: string, hours: number) => {
      if (!KEY) return null;
      const r = await fetch(`${SUPA}/rest/v1/ebay_cache?q=eq.${encodeURIComponent(k)}&select=data,fetched_at`, { headers: H });
      const row = r.ok ? (await r.json())?.[0] : null;
      return row && Date.now() - new Date(row.fetched_at).getTime() < hours * 3600_000 ? row.data : null;
    };
    const cachePut = async (k: string, data: unknown) => {
      if (!KEY) return;
      await fetch(`${SUPA}/rest/v1/ebay_cache?on_conflict=q`, {
        method: "POST", headers: { ...H, Prefer: "resolution=merge-duplicates,return=minimal" },
        body: JSON.stringify([{ q: k, data, fetched_at: new Date().toISOString() }]),
      }).catch(() => {});
    };
    const bh = (): Record<string, string> => ({ "X-EBAY-C-MARKETPLACE-ID": "EBAY_US" });

    // Kart bulucu (spor): kullanıcı bildiği kadarını yazar ("wembanyama prizm silver"), eBay ilanlarından kartını seçer.
    if (body.mode === "find") {
      const text = String(body.q || "").replace(/[^\p{L}\p{N} #\/.'-]/gu, " ").replace(/\s+/g, " ").trim().slice(0, 100);
      if (text.length < 3) return json({ error: "q" }, 400);
      const q = text + " -lot -bundle -reprint -custom -proxy -digital -break -pack -box";
      const k = `find1|${q}`.toLowerCase();
      const hit = await cacheGet(k, 24);
      if (hit) return json({ cached: true, ...hit });
      const token = await ebayToken(ID, SECRET);
      const params = new URLSearchParams({ q, category_ids: CATEGORY_SPORTS, limit: "40" });
      const r = await fetch(`https://api.ebay.com/buy/browse/v1/item_summary/search?${params}`, { headers: { ...bh(), Authorization: `Bearer ${token}` } });
      if (!r.ok) return json({ error: `eBay yanıt vermedi (${r.status})` }, 502);
      const j = await r.json();
      const seen = new Set<string>();
      const items = (j.itemSummaries || []).map((it: any) => ({
        id: it.itemId, title: it.title, price: Number(it.price?.value) || null,
        image: it.thumbnailImages?.[0]?.imageUrl || it.image?.imageUrl || null,
      })).filter((it: any) => {
        if (!it.image) return false;
        const t = String(it.title).toLowerCase().replace(/\s+/g, " ");
        if (seen.has(t)) return false; seen.add(t); return true;
      }).slice(0, 24);
      const data = { total: items.length, items };
      await cachePut(k, data);
      return json({ cached: false, ...data });
    }

    // Seçilen ilanın kart bilgileri (eBay'deki "Item specifics": oyuncu, sezon, üretici, set, numara, paralel, spor, derece)
    if (body.mode === "item") {
      const id = String(body.id || "").trim();
      if (!/^v1\|\d+\|\d+$/.test(id)) return json({ error: "id" }, 400);
      const k = `item1|${id}`;
      const hit = await cacheGet(k, 24 * 7);
      if (hit) return json({ cached: true, ...hit });
      const token = await ebayToken(ID, SECRET);
      const r = await fetch(`https://api.ebay.com/buy/browse/v1/item/${encodeURIComponent(id)}`, { headers: { ...bh(), Authorization: `Bearer ${token}` } });
      if (!r.ok) return json({ error: `eBay yanıt vermedi (${r.status})` }, 502);
      const it = await r.json();
      const A: Record<string, string> = {};
      for (const a of it.localizedAspects || []) A[String(a.name).toLowerCase()] = String(a.value || "").trim();
      const pick = (...names: string[]) => { for (const n of names) { const v = A[n.toLowerCase()]; if (v && !/^(n\/?a|none|unknown|-)$/i.test(v)) return v; } return ""; };
      const data = {
        title: it.title || "",
        player: pick("Player/Athlete", "Player", "Athlete", "Character"),
        season: pick("Season", "Year Manufactured", "Year"),
        manufacturer: pick("Manufacturer", "Brand"),
        set: pick("Set", "Product", "Series"),
        number: pick("Card Number"),
        parallel: pick("Parallel/Variety", "Parallel", "Variety"),
        sport: pick("Sport"), league: pick("League"),
        grader: pick("Professional Grader", "Grader"), grade: pick("Grade"),
        autographed: pick("Autographed"), features: pick("Features", "Attributes"),
        print_run: pick("Print Run"),
      };
      await cachePut(k, data);
      return json({ cached: false, ...data });
    }

    const name = String(body.name || "").replace(/\s*\(\d+\)\s*$/, "").replace(/\s+-\s+[\w\/-]+$/, "").trim().slice(0, 80);
    const numFull = String(body.number || "").trim().slice(0, 20);          // "4/102", "OP05-119", "TG03/TG30"
    const number = numFull.split("/")[0];
    const set = String(body.set || "").trim().slice(0, 60);
    const grade = String(body.grade || "raw").trim();
    const sports = body.cat === "sports";
    const variant = String(body.variant || "").trim().slice(0, 60);
    const CATEGORY = sports ? CATEGORY_SPORTS : CATEGORY_TCG;
    if (!name) return json({ error: "name" }, 400);
    const graded = /^(PSA|BGS|CGC|SGC|TAG|ACE)\s*\d/i.test(grade);
    const gradeText = graded ? grade.replace(/\s+(pristine|black\s*label)/i, "") : "";
    // Arama metni: ad + numara (+ derece). Ham için dereceli ilanları dışarıda bırak.
    // Arama: ad + tam numara (+ derece). Dijital/sahte/toplu ilanları ve (ham için) dereceli ilanları dışarıda bırak.
    const setWords = set.replace(/[^\p{L}\p{N} ]/gu, " ").split(/\s+/).filter((w) => w.length > 2).slice(0, 3).join(" ");
    // Spor kartı: oyuncu + yıl/set + numara + paralel (ör. "Victor Wembanyama 2023 Panini Prizm 136 Silver")
    let q = sports ? [name, set, numFull, variant, gradeText].filter(Boolean).join(" ")
                   : [name, numFull || setWords, gradeText].filter(Boolean).join(" ");
    q += " -pocket -digital -proxy -custom -orica -replica -lot -bundle";
    if (!graded) q += " -PSA -BGS -CGC -SGC -TAG -graded -slab";
    const key = `v4|${CATEGORY}|${q}|${set}|${CAMPAIGN ? "a" : ""}`.toLowerCase();

    // Önbellek
    if (KEY) {
      const r = await fetch(`${SUPA}/rest/v1/ebay_cache?q=eq.${encodeURIComponent(key)}&select=data,fetched_at`, { headers: H });
      if (r.ok) {
        const row = (await r.json())?.[0];
        if (row && Date.now() - new Date(row.fetched_at).getTime() < CACHE_HOURS * 3600_000) return json({ cached: true, ...row.data });
      }
    }

    const token = await ebayToken(ID, SECRET);
    const params = new URLSearchParams({
      q, category_ids: CATEGORY, limit: "100",
      filter: "buyingOptions:{FIXED_PRICE},priceCurrency:USD,price:[1..]",
    });
    const headers: Record<string, string> = { Authorization: `Bearer ${token}`, "X-EBAY-C-MARKETPLACE-ID": "EBAY_US" };
    if (CAMPAIGN) headers["X-EBAY-C-ENDUSERCTX"] = `affiliateCampaignId=${CAMPAIGN}`;
    const r = await fetch(`https://api.ebay.com/buy/browse/v1/item_summary/search?${params}`, { headers });
    if (!r.ok) return json({ error: `eBay yanıt vermedi (${r.status})`, detail: (await r.text()).slice(0, 200) }, 502);
    const j = await r.json();
    const words = name.toLowerCase().replace(/[^\p{L}\p{N} ]/gu, " ").split(/\s+/).filter((w) => w.length > 2);
    // Numara eşleşmesi: "4/102" = "04/102" = "004/102"; "OP05-119" olduğu gibi
    const norm = (t: string) => t.toLowerCase().replace(/(^|[^0-9a-z])0+(\d)/g, "$1$2");
    const numPat = numFull ? norm(numFull).replace(/[.*+?^${}()|[\]\\]/g, "\\$&") : "";
    const numRe = numPat ? new RegExp(`(^|[^0-9a-z])${numPat}($|[^0-9a-z])`) : null;
    const items = (j.itemSummaries || [])
      .filter((it: any) => {
        const t = String(it.title || "").toLowerCase();
        if (!words.every((w) => t.includes(w))) return false;
        if (numRe && !numRe.test(norm(t))) return false;
        if (/\b(pocket|digital|proxy|custom|orica|replica)\b/.test(t)) return false;
        // Aynı numarayı kullanan yeni baskılar (ör. Celebrations Classic Collection 4/102) ve baskı türleri
        if (!/celebration|classic collection/i.test(set) && /celebration|classic collection/.test(t)) return false;
        // Yeniden baskı / hatıra / büyük boy ürünler (kartın kendi seti bunlardan biri değilse; sporda "Gold" bir paralel adıdır)
        if (!sports) for (const w of ["reprint", "anniversary", "gold", "metal", "jumbo", "oversize", "graded card guard"]) {
          if (t.includes(w) && !(set + " " + name).toLowerCase().includes(w)) return false;
        }
        if (/1st edition/i.test(set + " " + name)) { if (!/\b1st\b|first edition/.test(t)) return false; }
        else if (/\b1st ed|\b1st edition|first edition/.test(t)) return false;
        if (/shadowless/i.test(set + " " + name)) { if (!/shadowless/.test(t)) return false; }
        else if (/shadowless/.test(t)) return false;
        if (graded && !t.includes(gradeText.toLowerCase().split(" ")[0])) return false;
        return true;
      })
      .map((it: any) => ({
        title: it.title, price: Number(it.price?.value) || null, currency: it.price?.currency,
        ship: Number(it.shippingOptions?.[0]?.shippingCost?.value) || 0,
        image: it.thumbnailImages?.[0]?.imageUrl || it.image?.imageUrl || null,
        url: it.itemAffiliateWebUrl || it.itemWebUrl, condition: it.condition || null,
        country: it.itemLocation?.country || null,
      }))
      .filter((it: any) => it.price);
    // Aykırı fiyatları ayıkla (ortancanın 1/4'ünden ucuz ya da 4 katından pahalı ilanlar genelde başka ürün)
    const med0 = median(items.map((i: any) => i.price as number));
    const clean = med0 ? items.filter((i: any) => i.price >= med0 / 4 && i.price <= med0 * 4) : items;
    clean.sort((a: any, b: any) => (a.price + a.ship) - (b.price + b.ship));
    items.length = 0; items.push(...clean);
    const prices = items.map((i: any) => i.price as number);
    const data = {
      q, total: items.length, min: prices.length ? Math.min(...prices) : null,
      median: median(prices), max: prices.length ? Math.max(...prices) : null,
      items: items.slice(0, 6),
      search_url: `https://www.ebay.com/sch/i.html?_nkw=${encodeURIComponent(q)}&_sacat=${CATEGORY}` +
        (CAMPAIGN ? `&mkcid=1&mkrid=711-53200-19255-0&siteid=0&campid=${CAMPAIGN}&toolid=10001&mkevt=1` : ""),
      fetched: new Date().toISOString(),
    };
    if (KEY) {
      await fetch(`${SUPA}/rest/v1/ebay_cache?on_conflict=q`, {
        method: "POST", headers: { ...H, Prefer: "resolution=merge-duplicates,return=minimal" },
        body: JSON.stringify([{ q: key, data, fetched_at: data.fetched }]),
      }).catch(() => {});
    }
    return json({ cached: false, ...data });
  } catch (e) {
    return json({ error: String((e as Error).message || e).slice(0, 300) }, 500);
  }
});
