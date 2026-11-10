// PXD2 LINK shell cache: the app opens with no signal (the outgoing queue lives in IndexedDB). GitHub API calls are never cached.
const SHELL = "pxd2-link-v10", FILES = ["./", "index.html", "app.js", "pitch.js", "fflate.min.js", "manifest.webmanifest", "icon-192.png", "icon-512.png", "pxd2-logo.png"];
self.addEventListener("install", e => { e.waitUntil(caches.open(SHELL).then(c => c.addAll(FILES))); self.skipWaiting(); });
self.addEventListener("activate", e => { e.waitUntil(caches.keys().then(k => Promise.all(k.filter(x => x !== SHELL).map(x => caches.delete(x))))); self.clients.claim(); });
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url);
  if (u.origin !== location.origin || e.request.method !== "GET") return;
  e.respondWith(fetch(e.request, { cache: "no-cache" }).then(r => { const c = r.clone(); caches.open(SHELL).then(x => x.put(e.request, c)); return r; }).catch(() => caches.match(e.request).then(r => r || caches.match("index.html"))));
});

// pop-up alerts: BASE1 pushes (end-to-end encrypted Web Push) - shows even when the app is closed
self.addEventListener("push", e => {
  let d = {}; try { d = e.data.json(); } catch (x) { d = { title: "PXD2", body: e.data ? e.data.text() : "" }; }
  e.waitUntil(self.registration.showNotification(d.title || "PXD2", { body: d.body || "", tag: d.tag || "pxd2", renotify: true,
    requireInteraction: true, icon: "icon-192.png", badge: "icon-192.png", vibrate: [150, 80, 150], data: { tag: d.tag } }));
});
self.addEventListener("notificationclick", e => {
  e.notification.close();
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(cs => {
    const c = cs.find(x => x.url.includes("/biz/hub/")); if (c) return c.focus();
    return self.clients.openWindow("./");
  }));
});
