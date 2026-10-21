// Holotique · ppt-price
// Arama sayfasında "PSA fiyatlarını getir" düğmesine basılınca çalışır.
// Kartın bugünkü fiyatı kayıtlıysa onu döndürür; değilse PokemonPriceTracker'dan çeker, kaydeder ve döndürür.
// Gerekli gizli ayar (Edge Functions → Secrets): PPT_API_KEY
// SUPABASE_URL ve SUPABASE_SERVICE_ROLE_KEY Supabase tarafından otomatik verilir.

const PPT = "https://www.pokemonpricetracker.com/api/v2";
const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const GRADE_KEY = /^(psa|bgs|cgc|sgc|tag|ace)_?(\d+(?:_5)?)(?:_?[a-z]+)?$/;

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { ...CORS, "Content-Type": "application/json" } });
}

function gradePrice(g: any): [number | null, string | null, number | null] {
  if (!g || typeof g !== "object") return [null, null, null];
  const sm = g.smartMarketPrice || {};
  const p = sm.price ?? g.marketPrice7Day ?? g.medianPrice ?? g.averagePrice;
  return [p ? Math.round(Number(p) * 100) / 100 : null, sm.confidence ?? null, g.count ?? null];
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "POST") return json({ error: "method" }, 405);

  const SUPA = Deno.env.get("SUPABASE_URL")!;
  const KEY = Deno.env.get("SB_SECRET_KEY") || Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const PKEY = Deno.env.get("PPT_API_KEY");
  if (!PKEY) return json({ error: "PPT_API_KEY tanımlı değil" }, 500);
  const H: Record<string, string> = { apikey: KEY, "Content-Type": "application/json" };
  if (KEY.startsWith("ey")) H.Authorization = `Bearer ${KEY}`;
  const db = async (method: string, path: string, body?: unknown, prefer?: string) => {
    const r = await fetch(`${SUPA}/rest/v1/${path}`, {
      method, headers: prefer ? { ...H, Prefer: prefer } : H, body: body ? JSON.stringify(body) : undefined,
    });
    if (!r.ok) throw new Error(`db ${method} ${path.split("?")[0]}: ${r.status} ${(await r.text()).slice(0, 200)}`);
    const t = await r.text();
    return t ? JSON.parse(t) : null;
  };

  try {
    const { pid } = await req.json().catch(() => ({}));
    const id = Number(pid);
    if (!Number.isInteger(id) || id <= 0) return json({ error: "pid" }, 400);
    const today = new Date().toISOString().slice(0, 10);

    const cat = (await db("GET", `catalog?product_id=eq.${id}&select=product_id,game,name,set_name,number,rarity,image,url`))?.[0];
    if (!cat) return json({ error: "Kart katalogda yok" }, 404);
    if (cat.game !== "Pokemon" && cat.game !== "Pokemon JP") return json({ error: "Bu oyun için PSA fiyat kaynağı yok", unsupported: true }, 200);
    const language = cat.game === "Pokemon JP" ? "japanese" : "english";

    // Kart daha önce takibe alındıysa ve bugün fiyatlandıysa kayıttan dön (kredi harcamaz)
    let card = (await db("GET", `cards?source=eq.ppt&ext_id=eq.${id}&select=id,last_priced`))?.[0];
    if (card) {
      const row = (await db("GET", `card_prices?card_id=eq.${card.id}&date=eq.${today}&select=*`))?.[0];
      if (row) return json({ cached: true, ...row });
      if (card.last_priced === today) return json({ cached: true, empty: true });
    }

    // PokemonPriceTracker'dan çek
    const q = new URLSearchParams({ tcgPlayerId: String(id), language, includeEbay: "true", limit: "1" });
    const pr = await fetch(`${PPT}/cards?${q}`, { headers: { Authorization: `Bearer ${PKEY}` } });
    if (!pr.ok) return json({ error: `Fiyat kaynağı yanıt vermedi (${pr.status})` }, 502);
    const body = await pr.json();
    let data = body?.data;
    if (data && !Array.isArray(data)) data = [data];
    const d = (data || []).find((x: any) => x && typeof x === "object");

    // Kredi sayacını fiyat göreviyle ortak tut
    try {
      const used = Number(body?.metadata?.apiCallsConsumed?.total ?? 2) || 2;
      const st = (await db("GET", `job_state?key=eq.ppt:${today}&select=value`))?.[0];
      const cur = Number(st?.value?.used || 0);
      await db("POST", "job_state?on_conflict=key", [{ key: `ppt:${today}`, value: { used: cur + used }, updated_at: new Date().toISOString() }],
        "resolution=merge-duplicates,return=minimal");
    } catch (_) { /* sayaç yazılamasa da fiyatı döndür */ }

    if (!card) {
      card = (await db("POST", "cards?on_conflict=source,ext_id", [{
        source: "ppt", ext_id: String(id), game: "Pokemon", language,
        name: d?.name || cat.name, set_name: d?.setName || cat.set_name, number: d?.cardNumber || cat.number,
        rarity: d?.rarity || cat.rarity, image: d?.imageCdnUrl400 || d?.imageUrl || cat.image, url: d?.tcgPlayerUrl || cat.url,
      }], "resolution=merge-duplicates,return=representation"))[0];
    }
    if (!d) {
      await db("PATCH", `cards?id=eq.${card.id}`, { last_priced: today });
      return json({ empty: true });
    }

    const sales = d?.ebay?.salesByGrade || {};
    const [p10, c10, n10] = gradePrice(sales.psa10);
    const [p9, c9, n9] = gradePrice(sales.psa9);
    const grades: Record<string, unknown> = {};
    for (const k of Object.keys(sales)) {
      if (!GRADE_KEY.test(k)) continue;
      const [p, c, n] = gradePrice(sales[k]);
      if (p != null) grades[k] = { p, c, n };
    }
    const row = {
      card_id: card.id, date: today, raw: d?.prices?.market ?? null,
      psa10: p10, psa10_conf: c10, psa10_n: n10, psa9: p9, psa9_conf: c9, psa9_n: n9,
      grades: Object.keys(grades).length ? grades : null,
    };
    await db("POST", "card_prices?on_conflict=card_id,date", [row], "resolution=merge-duplicates,return=minimal");
    await db("PATCH", `cards?id=eq.${card.id}`, { last_priced: today });
    return json({ cached: false, ...row });
  } catch (e) {
    return json({ error: String((e as Error).message || e).slice(0, 300) }, 500);
  }
});
