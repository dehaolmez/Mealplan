/* Mealbird servis çalışanı: uygulama kabuğunu ve son görüntülenen verileri çevrimdışı kullanım için önbellekler. */
const VERSION = "v1";
const SHELL = `mealbird-shell-${VERSION}`;
const DATA = `mealbird-api-${VERSION}`;
const PRECACHE = ["/", "/manifest.webmanifest", "/icons/icon-192.png", "/icons/icon-512.png"];
// Kişisel/hassas veya değişken uç noktalar önbelleğe alınmaz
const NO_CACHE = ["/api/auth/", "/api/geocode", "/api/places/nearby", "/api/prices/"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(SHELL).then((c) => c.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => ![SHELL, DATA].includes(k)).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("message", (event) => {
  // Çıkışta kullanıcıya ait önbelleklenmiş verileri temizle
  if (event.data === "clear-user-data") event.waitUntil(caches.delete(DATA));
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== self.location.origin) return;

  if (url.pathname.startsWith("/api/")) {
    if (NO_CACHE.some((p) => url.pathname.startsWith(p))) return;
    event.respondWith(networkFirst(req, DATA));
    return;
  }
  if (req.mode === "navigate") {
    event.respondWith(fetch(req).catch(() => caches.match("/")));
    return;
  }
  event.respondWith(staleWhileRevalidate(req));
});

async function networkFirst(req, cacheName) {
  const cache = await caches.open(cacheName);
  try {
    const res = await fetch(req);
    if (res.ok) cache.put(req, res.clone());
    return res;
  } catch (err) {
    const cached = await cache.match(req);
    if (cached) return cached;
    throw err;
  }
}

async function staleWhileRevalidate(req) {
  const cache = await caches.open(SHELL);
  const cached = await cache.match(req);
  const network = fetch(req).then((res) => {
    if (res.ok) cache.put(req, res.clone());
    return res;
  }).catch(() => cached);
  return cached || network;
}
