// PXD2 LINK shell cache: the app opens with no signal (the outgoing queue lives in IndexedDB). GitHub API calls are never cached.
const SHELL = "pxd2-link-v9", FILES = ["./", "index.html", "app.js", "pitch.js", "fflate.min.js", "manifest.webmanifest", "icon-192.png", "icon-512.png", "pxd2-logo.png"];
self.addEventListener("install", e => { e.waitUntil(caches.open(SHELL).then(c => c.addAll(FILES))); self.skipWaiting(); });
self.addEventListener("activate", e => { e.waitUntil(caches.keys().then(k => Promise.all(k.filter(x => x !== SHELL).map(x => caches.delete(x))))); self.clients.claim(); });
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url);
  if (u.origin !== location.origin || e.request.method !== "GET") return;
  e.respondWith(fetch(e.request, { cache: "no-cache" }).then(r => { const c = r.clone(); caches.open(SHELL).then(x => x.put(e.request, c)); return r; }).catch(() => caches.match(e.request).then(r => r || caches.match("index.html"))));
});
