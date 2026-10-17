/* KartRadarı kart tarayıcı
 * Ham kart: fotoğraftaki kart adı ve numarası telefonda okunur (Tesseract.js), katalogda aranır.
 * PSA'lı kart: etiket barkodundan sertifika numarası (ZXing / BarcodeDetector),
 *              etiket yazısından ad, numara, set ve derece okunur.
 * Hiçbir fotoğraf sunucuya gönderilmez; her şey telefonun tarayıcısında çalışır.
 */
(function () {
  'use strict';
  var TESS = 'https://cdn.jsdelivr.net/npm/tesseract.js@5.1.1/dist/tesseract.min.js';
  var ZX = 'https://cdn.jsdelivr.net/npm/@zxing/library@0.21.3/umd/index.min.js';
  var loaded = {}, worker = null;

  function loadScript(src) {
    if (!loaded[src]) loaded[src] = new Promise(function (ok, bad) {
      var s = document.createElement('script'); s.src = src; s.async = true; s.crossOrigin = 'anonymous';
      s.onload = ok; s.onerror = function () { delete loaded[src]; bad(new Error('Kütüphane yüklenemedi: ' + src)); };
      document.head.appendChild(s);
    });
    return loaded[src];
  }
  function getWorker(progress) {
    if (worker) return Promise.resolve(worker);
    return loadScript(TESS).then(function () {
      return window.Tesseract.createWorker('eng', 1, { logger: function (m) { if (progress && m.status) progress(m.status, m.progress); } });
    }).then(function (w) { worker = w; return w; });
  }

  // ---------- görüntü ----------
  function fileToImage(file) {
    return new Promise(function (ok, bad) {
      var url = URL.createObjectURL(file), img = new Image();
      img.onload = function () { ok(img); };
      img.onerror = function () { URL.revokeObjectURL(url); bad(new Error('Fotoğraf açılamadı.')); };
      img.src = url;
    });
  }
  function urlToImage(url) {
    return new Promise(function (ok, bad) {
      var img = new Image(); img.crossOrigin = 'anonymous';
      img.onload = function () { ok(img); }; img.onerror = function () { bad(new Error('Görsel açılamadı')); };
      img.src = url;
    });
  }
  // Kesit al (oranlarla), ölçekle, gri tona çevir, kontrastı aç.
  function crop(img, x, y, w, h, targetW, invert) {
    var iw = img.naturalWidth || img.width, ih = img.naturalHeight || img.height;
    var sx = Math.round(iw * x), sy = Math.round(ih * y), sw = Math.round(iw * w), sh = Math.round(ih * h);
    var scale = Math.min(4, (targetW || 1600) / sw);
    var c = document.createElement('canvas'); c.width = Math.max(1, Math.round(sw * scale)); c.height = Math.max(1, Math.round(sh * scale));
    var g = c.getContext('2d', { willReadFrequently: true }); g.imageSmoothingQuality = 'high';
    g.drawImage(img, sx, sy, sw, sh, 0, 0, c.width, c.height);
    var d = g.getImageData(0, 0, c.width, c.height), p = d.data, lo = 255, hi = 0, i, v;
    for (i = 0; i < p.length; i += 4) { v = 0.299 * p[i] + 0.587 * p[i + 1] + 0.114 * p[i + 2]; p[i] = v; if (v < lo) lo = v; if (v > hi) hi = v; }
    var span = Math.max(1, hi - lo);
    for (i = 0; i < p.length; i += 4) { v = (p[i] - lo) * 255 / span; if (invert) v = 255 - v; p[i] = p[i + 1] = p[i + 2] = v; }
    g.putImageData(d, 0, 0);
    return c;
  }
  function ocr(w, canvas) { return w.recognize(canvas).then(function (r) { return (r && r.data && r.data.text) || ''; }); }

  // ---------- metinden kart bilgisi ----------
  var STOP = /^(basic|stage|hp|evolves|from|trainer|supporter|item|stadium|tool|pok[eé]mon|energy|ability|put|this|card|your|the|of|and|ex|gx|v|vmax|vstar|tera|weakness|resistance|retreat|illus|illustrator|leader|character|event|don|counter|power|cost|life|attack|block|rush|blocker|trigger|banish|double|strike)$/i;
  function cleanNum(s) { return s.replace(/[oO]/g, '0').replace(/[lI|]/g, '1').replace(/\s+/g, ''); }

  function findNumber(text) {
    var t = text.replace(/[‐–—]/g, '-');
    var m = t.match(/\b(OP|ST|EB|PRB|P)\s?-?\s?(\d{2})\s?-\s?(\d{3})\b/i);          // One Piece: OP05-119
    if (m) return { code: (m[1] + m[2] + '-' + m[3]).toUpperCase(), kind: 'op' };
    m = t.match(/\b([A-Z]{0,4}[0-9OIl|]{1,3})\s?\/\s?([A-Z]{0,4}[0-9OIl|]{1,3})\b/);   // 199/165, TG12/TG30
    if (m) {
      var a = cleanNum(m[1]).replace(/^0+(?=\d)/, ''), b = cleanNum(m[2]);
      if (/\d/.test(a) && /\d/.test(b)) return { full: a + '/' + b, base: a.replace(/^[A-Z]+/, '') || a, kind: 'slash' };
    }
    m = t.match(/\b(SWSH|SVP|SM|XY|BW|DP|HGSS)\s?(\d{2,3})\b/i);                         // promo: SWSH050
    if (m) return { code: (m[1] + m[2]).toUpperCase(), kind: 'promo' };
    return null;
  }

  function findName(text) {
    // Kart adı genelde ilk satırlarda, büyük harfle başlayan ilk kelime grubudur.
    var lines = text.split(/\n+/);
    for (var li = 0; li < lines.length; li++) {
      var line = lines[li].replace(/evolves\s+from.*$/i, '').replace(/put .*$/i, '');
      var words = line.replace(/[^A-Za-zÀ-ÿ.'\- ]/g, ' ').split(/\s+/).filter(function (w) {
        var bare = w.replace(/[.'-]/g, '');
        return bare.length > 1 && !STOP.test(bare) && !(/^[A-Z]{2,4}$/.test(bare));   // OP, SEC, EN, MEW gibi kodlar ad değil
      });
      var run = [];
      for (var i = 0; i < words.length; i++) {
        if (/^[A-ZÀ-Þ]/.test(words[i])) run.push(words[i]); else if (run.length) break;
      }
      var s = run.slice(0, 3).join(' ').replace(/\.$/, '');
      if (s.replace(/[^A-Za-z]/g, '').length >= 4) return s;
    }
    return '';
  }

  // PSA derece kelimeleri; sayı etiketin başka bir satırında olabilir.
  var GRADES = [[/GEM\s*-?\s*M(?:IN)?T|PRISTINE/i, 10], [/NM\s*-?\s*MT/i, 8], [/VG\s*-?\s*EX/i, 4], [/EX\s*-?\s*MT/i, 6], [/\bMINT\b/i, 9],
    [/\bNM\b|NEAR\s*MINT/i, 7], [/\bEX\b/i, 5], [/\bVG\b/i, 3], [/\bGOOD\b/i, 2], [/\bPOOR\b|\bPR\b/i, 1]];
  var GRADE_WORDS = /GEM\s*-?\s*M(?:IN)?T|PRISTINE|NM\s*-?\s*MT\+?|VG\s*-?\s*EX|EX\s*-?\s*MT|\bMINT\b|\bNM\b|\bVG\b|\bGOOD\b|\bPOOR\b|\bAUTHENTIC\b/gi;
  function parseSlab(text) {
    var out = { raw: text }, T = text.replace(/[‐–—]/g, '-');
    // Belirgin derece kelimeleri her yerde aranır; "EX", "NM" gibi kısa olanlar yıl/set satırında aranmaz (set adlarında da geçer).
    var rest = T.split(/\n/).filter(function (l) { return !/\b(19|20)\d{2}\b/.test(l); }).join('\n');
    for (var i = 0; i < GRADES.length; i++) {
      var strong = i < 5, hay = strong ? T : rest;
      if (GRADES[i][0].test(hay)) { out.grade = 'PSA ' + GRADES[i][1]; break; }
    }
    var lone = T.match(/(?:^|\s)(10|[1-9](?:\.5)?)(?:\s|$)/g);
    if (lone && out.grade) { var nums = lone.map(function (x) { return x.trim(); }); if (nums.indexOf(out.grade.slice(4)) < 0 && nums.indexOf('10') >= 0 && /GEM|PRISTINE/i.test(T)) out.grade = 'PSA 10'; }
    var n = T.match(/#\s?([A-Z]{0,4}\d{1,3}[A-Z]?)\b/i) || T.match(/\bNO\.?\s?(\d{1,3})\b/i);
    if (n) out.number = n[1].toUpperCase().replace(/^0+(?=\d)/, '');
    var op = findNumber(T); if (op && op.kind === 'op') out.number = op.code;
    var y = T.match(/\b(19[89]\d|20[0-3]\d)\b/); if (y) out.year = y[1];
    out.japanese = /JAPANESE|JPN\b/i.test(T);
    T.split(/\n+/).forEach(function (l) { var runs = l.replace(/[ ]/g, '').match(/\d+/g) || []; var big = runs.filter(function (r) { return r.length >= 8 && r.length <= 10; });
      if (big.length === 1 && runs.length <= 2 && !out.certText) out.certText = big[0]; });
    // Etiket satırları: 1. satır yıl + marka/set, 2. satır kart adı
    var lines = T.split(/\n+/).map(function (s) { return s.trim(); }).filter(Boolean);
    var brand = lines.find(function (l) { return /POKEMON|ONE PIECE|LORCANA|BANDAI|DISNEY/i.test(l); }) || '';
    out.set = brand.replace(GRADE_WORDS, ' ').replace(/\b(19|20)\d{2}\b/, '').replace(/POKEMON|JAPANESE|ENGLISH|ONE PIECE|BANDAI|DISNEY|LORCANA|#\S+|\b[A-Z]{2,3}\d{2}-\d{3}\b/gi, ' ').replace(/[^A-Za-z0-9 &'-]/g, ' ').replace(/\s+/g, ' ').trim();
    var nameLine = lines.find(function (l) { var bare = l.replace(GRADE_WORDS, ' ').replace(/#\S+|\b\d+(\.\d)?\b/g, '').trim(); return l !== brand && bare.length > 2 && /^[A-Z][A-Z .'\-]{2,}$/.test(bare) && !/PSA|CERT/i.test(l); });
    if (nameLine) out.name = nameLine.replace(GRADE_WORDS, ' ').replace(/#\S+|\b\d+\b|-HOLO|HOLO|REV\.?FOIL|1ST EDITION|FULL ART|SPECIAL ART RARE|ILLUSTRATION RARE/gi, ' ').replace(/\s+/g, ' ').trim();
    return out;
  }

  // ---------- barkod ----------
  function readBarcode(img) {
    var tries = [[0, 0, 1, 0.45], [0, 0, 1, 0.3], [0, 0, 1, 1]];
    function viaNative() {
      if (!('BarcodeDetector' in window)) return Promise.resolve(null);
      var det; try { det = new window.BarcodeDetector(); } catch (e) { return Promise.resolve(null); }
      return det.detect(img).then(function (r) { var c = (r || []).map(function (x) { return x.rawValue; }).find(function (v) { return /\d{7,}/.test(v); }); return c || null; }).catch(function () { return null; });
    }
    function viaZxing() {
      return loadScript(ZX).then(function () {
        var Z = window.ZXing, hints = new Map();
        hints.set(Z.DecodeHintType.TRY_HARDER, true);
        var reader = new Z.MultiFormatReader(); reader.setHints(hints);
        for (var i = 0; i < tries.length; i++) {
          var t = tries[i];
          try {
            var cv = crop(img, t[0], t[1], t[2], t[3], 1400), src = new Z.HTMLCanvasElementLuminanceSource(cv);
            var res = reader.decode(new Z.BinaryBitmap(new Z.HybridBinarizer(src)));
            if (res && /\d{7,}/.test(res.getText())) return res.getText();
          } catch (e) { KRScan.lastBarcodeError = String(e && (e.name || e.message) || e); }
        }
        return null;
      });
    }
    return viaNative().then(function (v) { return v || viaZxing(); }).then(function (v) {
      if (!v) return null;
      var m = String(v).match(/(\d{7,10})/); return m ? m[1] : null;
    }).catch(function () { return null; });
  }

  // ---------- akışlar ----------
  function scanRaw(img, progress) {
    // Numara: Pokemon'da sol alt (eski kartlarda sağ alt), One Piece'te sağ alt, Lorcana'da sol alt.
    var spots = [[0, 0.84, 0.55, 0.16], [0.45, 0.84, 0.55, 0.16], [0, 0.72, 1, 0.28]];
    return getWorker(progress).then(function (w) {
      progress && progress('Kartın üst kısmı okunuyor', 0.25);
      return ocr(w, crop(img, 0, 0, 1, 0.2, 2000)).then(function (top) {
        var texts = [top], i = 0;
        function nextSpot(invert) {
          if (i >= spots.length) {
            if (!invert) { i = 0; return nextSpot(true); }   // koyu (full art) kartlar için ters renk
            return Promise.resolve(null);
          }
          var sp = spots[i++];
          progress && progress('Kart numarası aranıyor', 0.35 + 0.08 * i + (invert ? 0.25 : 0));
          return ocr(w, crop(img, sp[0], sp[1], sp[2], sp[3], 2200, invert)).then(function (t) {
            texts.push(t); var n = findNumber(t); return n || nextSpot(invert);
          });
        }
        return nextSpot(false).then(function (num) {
          var name = findName(top);
          if (num && name) return { name: name, num: num, text: texts.join('\n') };
          progress && progress('Tüm kart okunuyor', 0.9);
          return ocr(w, crop(img, 0, 0, 1, 1, 2000)).then(function (all) {
            texts.push(all);
            return { name: name || findName(all), num: num || findNumber(all), text: texts.join('\n') };
          });
        });
      });
    });
  }
  function scanSlab(img, progress) {
    progress && progress('Barkod aranıyor', 0.1);
    return readBarcode(img).then(function (cert) {
      return getWorker(progress).then(function (w) {
        progress && progress('PSA etiketi okunuyor', 0.5);
        return ocr(w, crop(img, 0, 0, 1, 0.3, 1800)).then(function (label) {
          var s = parseSlab(label);
          s.cert = cert || s.certText || null; s.certFrom = cert ? 'barcode' : (s.certText ? 'text' : null);
          return s;
        });
      });
    });
  }

  // Aday sorguları: en ayırt edici olandan genele.
  // Katalog arama alanında noktalama yok ("Monkey.D.Luffy" → "MonkeyDLuffy").
  function tidy(n) { return String(n || '').replace(/\./g, '').replace(/\s+/g, ' ').trim(); }
  function rawQueries(r) {
    var q = [], n = tidy(r.name), num = r.num;
    if (num && num.kind === 'slash') { if (n) q.push(n + ' ' + num.full); q.push(num.full); if (n) q.push(n + ' ' + num.base); }
    if (num && (num.kind === 'op' || num.kind === 'promo')) { q.push(num.code); if (n) q.push(n + ' ' + num.code); }
    if (n) { q.push(n); var first = n.split(' ')[0]; if (first !== n && first.length > 2) q.push(first); }
    return q.filter(function (x, i) { return x && q.indexOf(x) === i; });
  }
  function slabQueries(s) {
    var q = [], n = tidy(s.name), num = s.number || '', setw = (s.set || '').split(' ').filter(function (w) { return w.length > 2; }).slice(0, 2).join(' ');
    if (n && num && setw) q.push(n + ' ' + num + ' ' + setw);
    if (n && num) q.push(n + ' ' + num);
    if (n && setw) q.push(n + ' ' + setw);
    if (num && /-/.test(num)) q.push(num);
    if (n) { q.push(n); var first = n.split(' ')[0]; if (first !== n && first.length > 2) q.push(first); }
    return q.filter(function (x, i) { return x && q.indexOf(x) === i; });
  }

  window.KRScan = { scanRaw: scanRaw, scanSlab: scanSlab, fileToImage: fileToImage, urlToImage: urlToImage,
    rawQueries: rawQueries, slabQueries: slabQueries, findNumber: findNumber, findName: findName, parseSlab: parseSlab, readBarcode: readBarcode };
})();
