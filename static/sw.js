/* =====================================================================
   Casset service worker — hand-written, no Workbox.

   Workbox would add a build step and ~15 kB to implement three routing
   rules; this file is the whole of what the site needs and every caching
   decision is readable in one screen.

   Strategy per resource class, and why:
     static assets  cache-first          — hashed-by-content in practice
                                           (they change with a deploy, and
                                           the cache version bumps with it)
     HTML pages     network-first        — a stale page showing a stale
                                           track list is worse than a
                                           slightly slower one; falls back
                                           to cache, then to the offline
                                           page, when the network is gone
     API (GET)      stale-while-revalidate — instant paint, fresh next time
     audio/media    never cached         — a single track can be tens of
                                           megabytes and would evict
                                           everything else; the browser's
                                           own HTTP cache handles range
                                           requests far better than we can
     anything POST  never touched        — the cache must never stand
                                           between a like/comment and the
                                           server
   ===================================================================== */

const VERSION = "v3";
const STATIC_CACHE = `casset-static-${VERSION}`;
const PAGE_CACHE = `casset-pages-${VERSION}`;
const API_CACHE = `casset-api-${VERSION}`;

const APP_SHELL = [
  "/discover/",
  "/offline/",
  "/static/app.css",
  "/static/css/casset-ui.css",
  "/static/css/cassette.css",
  "/static/css/fonts.css",
  "/static/app.js",
  "/static/js/casset-ui.js",
  "/static/fonts/vazirmatn-arabic.woff2",
  "/static/manifest.webmanifest",
  "/static/icons/icon-192.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      // addAll() is all-or-nothing: one 404 would abandon the whole
      // install and leave the site with no service worker at all.
      .then((cache) => Promise.allSettled(APP_SHELL.map((url) => cache.add(url))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  const keep = [STATIC_CACHE, PAGE_CACHE, API_CACHE];
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => !keep.includes(k)).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

function isMedia(url, request) {
  return (
    request.destination === "audio" ||
    request.destination === "video" ||
    /\.(mp3|wav|m4a|ogg|opus|flac|mp4|webm)$/i.test(url.pathname)
  );
}

function isStatic(url) {
  return url.pathname.startsWith("/static/");
}

function isApi(url) {
  return url.pathname.startsWith("/api/");
}

async function cacheFirst(request, cacheName) {
  const cached = await caches.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response && response.ok) {
    const cache = await caches.open(cacheName);
    cache.put(request, response.clone());
  }
  return response;
}

async function networkFirst(request, cacheName) {
  try {
    const response = await fetch(request);
    if (response && response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    const cached = await caches.match(request);
    if (cached) return cached;
    const offline = await caches.match("/offline/");
    if (offline) return offline;
    throw err;
  }
}

async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  const network = fetch(request)
    .then((response) => {
      if (response && response.ok) cache.put(request, response.clone());
      return response;
    })
    .catch(() => cached);
  return cached || network;
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);

  // Never cache another origin's responses, and never cache media.
  if (url.origin !== self.location.origin) return;
  if (isMedia(url, request)) return;

  if (isStatic(url)) {
    event.respondWith(cacheFirst(request, STATIC_CACHE));
    return;
  }
  if (isApi(url)) {
    event.respondWith(staleWhileRevalidate(request, API_CACHE));
    return;
  }
  if (request.mode === "navigate" || (request.headers.get("accept") || "").includes("text/html")) {
    event.respondWith(networkFirst(request, PAGE_CACHE));
  }
});
