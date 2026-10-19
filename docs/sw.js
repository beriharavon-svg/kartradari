/* Holotique: uygulama olarak açılabilmesi için basit servis çalışanı.
 * Her istekte önce internet denenir (fiyatlar hep güncel kalsın); bağlantı yoksa son açılan sayfa gösterilir.
 * Veritabanı ve diğer sitelere giden istekler hiç önbelleğe alınmaz. */
var CACHE = 'holotique-v1';
self.addEventListener('install', function (e) { self.skipWaiting(); });
self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (ks) { return Promise.all(ks.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); })); }).then(function () { return self.clients.claim(); }));
});
self.addEventListener('fetch', function (e) {
  var r = e.request, u = new URL(r.url);
  if (r.method !== 'GET' || u.origin !== location.origin) return;
  e.respondWith(fetch(r).then(function (res) {
    if (res.ok) { var c = res.clone(); caches.open(CACHE).then(function (ca) { ca.put(r, c); }); }
    return res;
  }).catch(function () {
    return caches.match(r, { ignoreSearch: r.mode === 'navigate' }).then(function (m) { return m || caches.match('./'); });
  }));
});
