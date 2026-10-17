// Tarayıcı testi (GitHub Actions'ta çalışır): gerçek kart görselleri ve örnek bir PSA etiketiyle
// fotoğraftan kart bulmayı uçtan uca dener. Sonuç status-scan dalına yazılır.
import { chromium } from 'playwright';
import fs from 'node:fs';
import { spawn } from 'node:child_process';

const SB_URL = 'https://bsifvfcnktofugaspsls.supabase.co', SB_KEY = 'sb_publishable_IFtbpaxlRhYiB7kjJydiIA_ilx0aRI1';
// Yüksek çözünürlüklü görseller (gerçek telefon fotoğrafına daha yakın)
const HIRES = [['https://images.pokemontcg.io/sv3pt5/199_hires.png', 'charizard ex 199/165', 'Pokemon'],
  ['https://images.pokemontcg.io/swsh7/215_hires.png', 'umbreon vmax 215/203', 'Pokemon'],
  ['https://images.pokemontcg.io/base1/4_hires.png', 'charizard 4/102', 'Pokemon'],
  ['https://images.pokemontcg.io/sv4pt5/234_hires.png', 'charizard ex 234/091', 'Pokemon'],
  ['https://images.pokemontcg.io/swsh12pt5/GG70_hires.png', 'charizard vstar gg70', 'Pokemon']];
const CASES = [['charizard ex 199/165', 'Pokemon'], ['umbreon vmax 215/203', 'Pokemon'], ['charizard 4/102', 'Pokemon'],
  ['pikachu ex', 'Pokemon'], ['op05-119', 'One Piece'], ['op01-120', 'One Piece'], ['elsa 207/204', 'Lorcana'],
  ['umbreon 217/187', 'Pokemon JP'], ['magmar vending', 'Pokemon JP']];

async function rpc(name, args) {
  const r = await fetch(`${SB_URL}/rest/v1/rpc/${name}`, { method: 'POST', headers: { apikey: SB_KEY, 'Content-Type': 'application/json' }, body: JSON.stringify(args) });
  return r.json();
}
fs.mkdirSync('docs/_t', { recursive: true });
const server = spawn('python3', ['-m', 'http.server', '8799', '-d', 'docs'], { stdio: 'ignore' });
await new Promise(r => setTimeout(r, 1500));
const out = { raw: [], slab: null, errors: [] };
const browser = await chromium.launch();
const page = await browser.newPage();
page.on('pageerror', e => out.errors.push(String(e.message).slice(0, 200)));
await page.goto('http://localhost:8799/ara.html');
await page.waitForTimeout(1500);

for (const [q, g] of CASES) {
  const rows = await rpc('search_cards', { q, g, lim: 1, off: 0 });
  const c = Array.isArray(rows) && rows[0];
  if (!c) { out.raw.push({ q, g, error: 'katalogda yok' }); continue; }
  const big = String(c.image || '').replace(/_\d+w\.jpg$/, '_in_1000x1000.jpg');
  let file = `docs/_t/${c.product_id}.jpg`, ok = false;
  for (const u of [big, c.image]) { try { const r = await fetch(u); if (r.ok) { fs.writeFileSync(file, Buffer.from(await r.arrayBuffer())); ok = true; break; } } catch {} }
  if (!ok) { out.raw.push({ q, g, error: 'görsel indirilemedi' }); continue; }
  const res = await page.evaluate(async ({ url, g }) => {
    const img = await KRScan.urlToImage(url);
    const r = await KRScan.scanRaw(img);
    const qs = KRScan.rawQueries(r);
    const sb = window.supabase.createClient('https://bsifvfcnktofugaspsls.supabase.co', 'sb_publishable_IFtbpaxlRhYiB7kjJydiIA_ilx0aRI1');
    let hit = null, ids = [];
    for (const q of qs) { const x = await sb.rpc('search_cards', { q, g, lim: 6, off: 0 }); if (x.data && x.data.length) { hit = q; ids = x.data.map(d => d.product_id); break; } }
    return { w: img.naturalWidth, name: r.name, num: r.num, qs, hit, ids, text: r.text.slice(0, 300) };
  }, { url: `/_t/${c.product_id}.jpg`, g });
  out.raw.push({ q, g, expect: c.product_id, expect_name: c.name, ...res, found: res.ids.includes(c.product_id), rank: res.ids.indexOf(c.product_id) });
}

for (const [url, q, g] of HIRES) {
  const rows = await rpc('search_cards', { q, g, lim: 3, off: 0 });
  const ids = Array.isArray(rows) ? rows.map(r => r.product_id) : [];
  let ok = false; const file = `docs/_t/h${out.raw.length}.png`;
  try { const r = await fetch(url); if (r.ok) { fs.writeFileSync(file, Buffer.from(await r.arrayBuffer())); ok = true; } } catch {}
  if (!ok) { out.raw.push({ q, hires: true, error: 'görsel indirilemedi' }); continue; }
  const res = await page.evaluate(async ({ url, g }) => {
    const img = await KRScan.urlToImage(url); const r = await KRScan.scanRaw(img); const qs = KRScan.rawQueries(r);
    const sb = window.supabase.createClient('https://bsifvfcnktofugaspsls.supabase.co', 'sb_publishable_IFtbpaxlRhYiB7kjJydiIA_ilx0aRI1');
    let hit = null, got = [];
    for (const q of qs) { const x = await sb.rpc('search_cards', { q, g, lim: 6, off: 0 }); if (x.data && x.data.length) { hit = q; got = x.data.map(d => d.product_id); break; } }
    let fuzzy = null;
    if (!hit && KRScan.plausible(r.name)) { const fz = await sb.rpc('search_fuzzy', { q: r.name, g, lim: 8 }); const w = KRScan.fuzzyPick(r.name, fz.data); fuzzy = fz.error ? fz.error.message : w;
      if (w) {
        const n = r.num && (r.num.full || r.num.code); for (const q of (n ? [w + ' ' + n] : []).concat([w])) { const x = await sb.rpc('search_cards', { q, g, lim: 6, off: 0 }); if (x.data && x.data.length) { hit = 'fuzzy:' + q; got = x.data.map(d => d.product_id); break; } } } }
    return { w: img.naturalWidth, name: r.name, num: r.num, qs, hit, fuzzy, ids: got, text: r.text.slice(0, 300) };
  }, { url: '/' + file.replace('docs/', ''), g });
  out.raw.push({ q, hires: true, expect: ids[0], ...res, found: ids.some(i => res.ids.includes(i)), rank: res.ids.indexOf(ids[0]) });
}

// Örnek PSA etiketi: barkod + yazılar
await page.setContent(`<html><body style="margin:0;background:#ddd">
<div id="slab" style="width:900px;padding:30px;background:#c9ccd1">
 <div style="background:#fff;border:6px solid #d0021b;padding:18px 24px;font:700 30px Arial;display:flex;justify-content:space-between">
  <div>2021 POKEMON SWORD &amp; SHIELD EVOLVING SKIES<br>UMBREON VMAX<br>ALT. ART SECRET</div>
  <div style="text-align:right">#215<br>GEM MT<br>10</div></div>
 <div style="background:#fff;border:6px solid #d0021b;border-top:0;padding:8px 24px;display:flex;justify-content:space-between;align-items:center">
  <svg id="bc"></svg><span style="font:700 30px Arial">76543210</span></div>
 <div style="height:900px;background:#334"></div></div>
<script src="https://cdn.jsdelivr.net/npm/jsbarcode@3.11.6/dist/JsBarcode.all.min.js"></script>
<script>JsBarcode('#bc','76543210',{format:'CODE128',height:70,displayValue:false})</script></body></html>`);
await page.waitForTimeout(1500);
await (await page.$('#slab')).screenshot({ path: 'docs/_t/slab.png' });
await page.goto('http://localhost:8799/ara.html'); await page.waitForTimeout(1200);
out.zxdiag = await page.evaluate(async () => {
  const img = await KRScan.urlToImage('/_t/slab.png'); const r = {};
  try { await KRScan.readBarcode(img).then(v => { r.readBarcode = v; r.err = KRScan.lastBarcodeError; }); } catch (e) { r.e0 = String(e); }
  const Z = window.ZXing; r.has = ['BrowserMultiFormatReader', 'BrowserBarcodeReader', 'HTMLCanvasElementLuminanceSource', 'Code128Reader', 'GlobalHistogramBinarizer'].filter(k => Z && Z[k]);
  try { if (Z.BrowserMultiFormatReader) { const res = await new Z.BrowserMultiFormatReader().decodeFromImageElement(img); r.browser = res.getText(); } } catch (e) { r.browserErr = String(e && (e.message || e)).slice(0, 120); }
  try { const c = document.createElement('canvas'); c.width = img.naturalWidth; c.height = img.naturalHeight; c.getContext('2d').drawImage(img, 0, 0);
    const src = new Z.HTMLCanvasElementLuminanceSource(c); const rd = new Z.Code128Reader();
    const res = rd.decode(new Z.BinaryBitmap(new Z.HybridBinarizer(src))); r.code128 = res.getText(); } catch (e) { r.code128Err = String(e && (e.message || e)).slice(0, 120); }
  return r;
});
out.slab = await page.evaluate(async () => {
  const img = await KRScan.urlToImage('/_t/slab.png');
  const s = await KRScan.scanSlab(img); s.label = s.raw; delete s.raw; s.zxingType = typeof window.ZXing; s.barcodeError = KRScan.lastBarcodeError || null;
  const qs = KRScan.slabQueries(s);
  const sb = window.supabase.createClient('https://bsifvfcnktofugaspsls.supabase.co', 'sb_publishable_IFtbpaxlRhYiB7kjJydiIA_ilx0aRI1');
  let hit = null, names = [];
  for (const q of qs) { const x = await sb.rpc('search_cards', { q, g: 'Pokemon', lim: 3, off: 0 }); if (x.data && x.data.length) { hit = q; names = x.data.map(d => d.name + ' · ' + d.set_name); break; } }
  return { ...s, qs, hit, names };
});
await browser.close(); server.kill();
out.summary = `${out.raw.filter(r => r.found).length}/${out.raw.length} ham kart bulundu; PSA barkod: ${out.slab && out.slab.certFrom}`;
fs.writeFileSync(process.env.OUT || 'scan-result.json', JSON.stringify(out, null, 1));
console.log(out.summary);
