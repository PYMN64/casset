const CACHE_NAME = "casset-v2";
const ASSETS = [
  "/",
  "/discover/",
  "/search/",
  "/tracks/",
  "/library/",
  "/static/app.js",
  "/static/app.css",
  "/static/manifest.webmanifest",
  "/static/icons/icon.svg",
  "/static/icons/maskable.svg"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.map(k => (k !== CACHE_NAME ? caches.delete(k) : null)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;

  // فقط GET
  if (req.method !== "GET") return;

  event.respondWith(
    caches.match(req).then((cached) => {
      if (cached) return cached;

      return fetch(req).then((res) => {
        // اگر جواب بد بود cache نکن
        if (!res || res.status !== 200 || res.type !== "basic") return res;

        const copy = res.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
        return res;
      });
    })
  );
});
