/* Holotique vitrin görseli: en değerli kartların kolajı (Instagram gönderisi 4:5 ya da hikâye 9:16).
 * Tarayıcıda canvas ile çizilir; sunucuya hiçbir şey gönderilmez.
 * Kart görselleri başka sitelerden geldiği için önce doğrudan (CORS ile), olmazsa wsrv.nl görsel önbelleği üzerinden yüklenir;
 * ikisi de olmazsa kartın yerine düz bir kutu çizilir. */
(function () {
  'use strict';
  var T = function (s) { return window.HQ_T ? window.HQ_T(s) : s; };
  var LOC = window.HQ_LANG === 'en' ? 'en-US' : 'tr-TR';
  var FOIL = ['#7AD3F0', '#B79CF5', '#F3A6C8', '#F6D58A', '#9BE3C4'];
  var FD = '"Bricolage Grotesque", system-ui, sans-serif', FB = '"IBM Plex Sans", system-ui, sans-serif', FM = '"IBM Plex Mono", ui-monospace, monospace';

  function usd(v) {
    if (v == null || !isFinite(v)) return '—';
    var d = v >= 10 ? 0 : 2; return '$' + Number(v).toLocaleString(LOC, { minimumFractionDigits: d, maximumFractionDigits: d });
  }
  function once(src, cors) {
    return new Promise(function (res) {
      var i = new Image(), done = false;
      if (cors) i.crossOrigin = 'anonymous';
      i.onload = function () { if (!done) { done = true; res(i); } };
      i.onerror = function () { if (!done) { done = true; res(null); } };
      setTimeout(function () { if (!done) { done = true; res(null); } }, 7000);
      i.src = src;
    });
  }
  function loadImg(src) {
    if (!src) return Promise.resolve(null);
    if (/^data:/.test(src)) return once(src, false);
    return once(src, true).then(function (i) {
      return i || once('https://wsrv.nl/?url=' + encodeURIComponent(src.replace(/^https?:\/\//, '')) + '&w=420&output=jpg&q=85', true);
    });
  }
  function rr(c, x, y, w, h, r) { c.beginPath(); c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r); c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath(); }
  function foil(c, x, y, w, h) { var g = c.createLinearGradient(x, y, x + w, y + h); FOIL.forEach(function (col, i) { g.addColorStop(i / (FOIL.length - 1), col); }); return g; }
  function fit(c, text, max) {
    text = String(text || '');
    if (c.measureText(text).width <= max) return text;
    while (text.length > 1 && c.measureText(text + '…').width > max) text = text.slice(0, -1);
    return text + '…';
  }
  function wrap(c, text, max, lines) {
    var words = String(text || '').split(/\s+/), out = [], cur = '';
    words.forEach(function (w) { var t = cur ? cur + ' ' + w : w; if (c.measureText(t).width <= max || !cur) cur = t; else { out.push(cur); cur = w; } });
    if (cur) out.push(cur);
    if (out.length > lines) { out = out.slice(0, lines); out[lines - 1] = fit(c, out[lines - 1] + '…', max); }
    return out.map(function (l) { return fit(c, l, max); });
  }
  function isSlab(g) { return /^(PSA|BGS|CGC|SGC|TAG|ACE)\b/.test(g || ''); }

  function logo(c, x, y, r) {
    c.save();
    c.strokeStyle = '#33405A'; c.lineWidth = r * 0.07;
    [0.37, 0.68].forEach(function (k) { c.beginPath(); c.arc(x, y, r * k, 0, Math.PI * 2); c.stroke(); });
    c.beginPath(); c.moveTo(x, y); c.arc(x, y, r, -Math.PI / 2, -Math.PI / 2 + Math.PI / 3); c.closePath();
    c.fillStyle = 'rgba(79,107,255,.55)'; c.fill();
    c.lineWidth = r * 0.09; c.strokeStyle = foil(c, x - r, y - r, 2 * r, 2 * r); c.beginPath(); c.arc(x, y, r, 0, Math.PI * 2); c.stroke();
    c.fillStyle = '#4F6BFF'; c.beginPath(); c.arc(x, y, r * 0.15, 0, Math.PI * 2); c.fill();
    c.restore();
  }

  /* opts: {title, slug, host, count, total (null = değerleri gizle), cards:[{name,set,number,image,grade,value,qty}], format:'post'|'story'} */
  window.HQShareImage = function (opts) {
    var story = opts.format === 'story', W = 1080, H = story ? 1920 : 1350, P = 64;
    var cols = 3, rows = story ? 3 : 2, n = cols * rows;
    var cards = (opts.cards || []).slice(0, n);
    var showVal = opts.total != null;
    var fontsReady = document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve();
    return Promise.all([fontsReady, Promise.all(cards.map(function (k) { return loadImg(k.image); }))]).then(function (r) {
      var imgs = r[1], cv = document.createElement('canvas');
      cv.width = W; cv.height = H;
      var c = cv.getContext('2d');
      // zemin
      var bg = c.createLinearGradient(0, 0, 0, H); bg.addColorStop(0, '#141C2B'); bg.addColorStop(1, '#0B1018');
      c.fillStyle = bg; c.fillRect(0, 0, W, H);
      var glow = c.createRadialGradient(W * 0.85, H * 0.08, 0, W * 0.85, H * 0.08, W * 0.7);
      glow.addColorStop(0, 'rgba(79,107,255,.22)'); glow.addColorStop(1, 'rgba(79,107,255,0)');
      c.fillStyle = glow; c.fillRect(0, 0, W, H);
      c.fillStyle = foil(c, 0, 0, W, 12); c.fillRect(0, 0, W, 12);
      c.textBaseline = 'alphabetic';

      // başlık alanı
      var y = story ? 150 : 110;
      logo(c, P + 26, y - 14, 26);
      c.fillStyle = '#E8EDF4'; c.font = '800 40px ' + FD; c.fillText('Holotique', P + 68, y);
      c.font = '600 22px ' + FB; c.fillStyle = '#A0AABA'; c.textAlign = 'right';
      c.fillText(T('VİTRİN'), W - P, y - 4); c.textAlign = 'left';
      y += story ? 110 : 86;
      c.font = '800 ' + (story ? 76 : 64) + 'px ' + FD; c.fillStyle = '#FFFFFF';
      var tl = wrap(c, opts.title || opts.slug, W - 2 * P, 2);
      tl.forEach(function (l, i) { c.fillText(l, P, y + i * (story ? 84 : 72)); });
      y += (tl.length - 1) * (story ? 84 : 72) + (story ? 70 : 58);
      c.font = '500 32px ' + FM; c.fillStyle = '#A0AABA';
      var stat = opts.count + ' ' + T('kart') + (showVal ? '  ·  ' + usd(opts.total) : '');
      c.fillText(stat, P, y);
      y += story ? 70 : 50;

      // kart ızgarası
      var footH = story ? 170 : 120, gap = 26;
      var gridH = H - y - footH, cellW = (W - 2 * P - gap * (cols - 1)) / cols, cellH = (gridH - gap * (rows - 1)) / rows;
      var textH = 104, artH = Math.min(cellH - textH, cellW * 88 / 63), artW = artH * 63 / 88;
      if (!cards.length) {
        c.font = '500 34px ' + FB; c.fillStyle = '#A0AABA'; c.textAlign = 'center';
        c.fillText(T('Bu vitrinde henüz kart yok.'), W / 2, y + gridH / 2); c.textAlign = 'left';
      }
      cards.forEach(function (k, i) {
        var cx = P + (i % cols) * (cellW + gap), cy = y + Math.floor(i / cols) * (cellH + gap);
        var ax = cx + (cellW - artW) / 2, ay = cy;
        var slab = isSlab(k.grade), b = slab ? 7 : 0;
        if (slab) { rr(c, ax - b, ay - b, artW + 2 * b, artH + 2 * b, 18); c.fillStyle = foil(c, ax, ay, artW, artH); c.fill(); }
        c.save(); rr(c, ax, ay, artW, artH, 13); c.clip();
        c.fillStyle = '#1B2433'; c.fillRect(ax, ay, artW, artH);
        var im = imgs[i];
        if (im) {
          var s = Math.max(artW / im.width, artH / im.height), iw = im.width * s, ih = im.height * s;
          c.drawImage(im, ax + (artW - iw) / 2, ay + (artH - ih) / 2, iw, ih);
        } else {
          c.fillStyle = '#6E7889'; c.font = '600 26px ' + FB; c.textAlign = 'center';
          wrap(c, k.name, artW - 30, 3).forEach(function (l, j) { c.fillText(l, ax + artW / 2, ay + artH / 2 - 20 + j * 34); });
          c.textAlign = 'left';
        }
        c.restore();
        // derece rozeti + değer
        var ty = ay + artH + 7 + 40, lx = cx + 4, vtxt = showVal && k.value != null ? usd(k.value) : '', vw = 0;
        if (vtxt) { c.font = '600 26px ' + FM; vw = c.measureText(vtxt).width + 14; }
        c.font = '700 22px ' + FB;
        var g0 = k.grade === 'Ham' ? T('Ham') : String(k.grade).replace(/\s*Black Label$/i, ' BL');
        var gtxt = fit(c, g0 + (k.qty > 1 ? ' ×' + k.qty : ''), cellW - vw - 32), gw = c.measureText(gtxt).width + 24;
        rr(c, lx, ty - 27, gw, 36, 18); c.fillStyle = k.grade === 'Ham' ? '#253041' : '#E8EDF4'; c.fill();
        c.fillStyle = k.grade === 'Ham' ? '#C9D1DE' : '#0B1018'; c.fillText(gtxt, lx + 12, ty - 2);
        if (vtxt) {
          c.font = '600 26px ' + FM; c.fillStyle = '#FFFFFF'; c.textAlign = 'right';
          c.fillText(vtxt, cx + cellW - 4, ty - 2); c.textAlign = 'left';
        }
        c.font = '500 23px ' + FB; c.fillStyle = '#A0AABA';
        c.fillText(fit(c, k.name, cellW - 8), lx, ty + 38);
      });

      // alt bilgi
      var fy = H - (story ? 90 : 60);
      c.strokeStyle = '#253041'; c.lineWidth = 2; c.beginPath(); c.moveTo(P, fy - 56); c.lineTo(W - P, fy - 56); c.stroke();
      c.font = '600 ' + (story ? 30 : 28) + 'px ' + FM; c.fillStyle = '#E8EDF4';
      c.fillText(fit(c, (opts.host || 'holotique.com') + '/v/' + opts.slug, W - 2 * P - 250), P, fy);
      if (showVal) { c.font = '400 20px ' + FB; c.fillStyle = '#6E7889'; c.textAlign = 'right'; c.fillText(T('Tahmini piyasa değeri'), W - P, fy - 4); c.textAlign = 'left'; }
      return cv;
    });
  };

  // İndir ya da (telefonda) doğrudan paylaş
  window.HQShareImageExport = function (cv, name, share, url) {
    return new Promise(function (res) {
      try { cv.toBlob(function (blob) {
        var file = new File([blob], name, { type: 'image/png' });
        if (share && navigator.canShare && navigator.canShare({ files: [file] })) {
          navigator.share(url ? { files: [file], text: url } : { files: [file] }).then(function () { res('shared'); }, function () { res('cancel'); });
          return;
        }
        var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name;
        document.body.appendChild(a); a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
        res('downloaded');
      }, 'image/png'); } catch (e) { res('error'); }
    });
  };
})();
