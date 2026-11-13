/* PXD Browser offline + speed layer.
 * The browser shell opens instantly from cache; the registry, host table and search index are fetched fresh
 * every time (network first) and fall back to the last copy when offline, so new names appear as soon as
 * they are published and the browser still works with no connection. */
const SHELL = "pxd-shell-v1";
const FRESH = ["/names.json", "/hosts.json", "/search-index.json"];
self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(SHELL).then((c) => c.addAll(["/", "/favicon.svg", "/pxd.webmanifest"])).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== SHELL && k !== "pxd-data").map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.origin !== location.origin) return;
  if (FRESH.includes(u.pathname)) {                       // network first: always the newest names
    e.respondWith(fetch(e.request).then((r) => {
      const copy = r.clone(); caches.open("pxd-data").then((c) => c.put(u.pathname, copy)); return r;
    }).catch(() => caches.match(u.pathname)));
    return;
  }
  if (u.pathname === "/" || u.pathname === "/index.html") { // the browser itself: fresh when online, cached when not
    e.respondWith(fetch(e.request).then((r) => { const copy = r.clone(); caches.open(SHELL).then((c) => c.put("/", copy)); return r; })
      .catch(() => caches.match("/")));
  }
});
