const CACHE = "dhammabell-v6";
const SHELL = ["./", "index.html", "manifest.webmanifest", "icon-192.png", "icon-512.png", "icon-maskable-512.png", "apple-touch-icon.png", "favicon.svg", "favicon.ico"];

self.addEventListener("install", e => {
  e.waitUntil(
    caches.open(CACHE).then(async c => {
      await c.addAll(SHELL);
      // bell.mp3 is optional — cache it if the repo has one
      try { await c.add("bell.mp3"); } catch (_) {}
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", e => {
  if (e.request.method !== "GET") return;
  e.respondWith(
    caches.match(e.request).then(hit =>
      hit ||
      fetch(e.request).then(res => {
        const copy = res.clone();
        caches.open(CACHE).then(c => c.put(e.request, copy));
        return res;
      }).catch(() => caches.match("index.html"))
    )
  );
});

self.addEventListener("push", e => {
  let d = {};
  try { d = e.data.json(); } catch (_) {}
  e.waitUntil(self.registration.showNotification(d.title || "dhamma.bell", {
    body: d.body || "The gong has sounded.",
    icon: "icon-192.png", badge: "icon-192.png",
    tag: "dhamma.bell", renotify: true,
    vibrate: [300, 150, 300, 150, 600],
  }));
});

self.addEventListener("notificationclick", e => {
  e.notification.close();
  e.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(list => {
      for (const c of list) if ("focus" in c) return c.focus();
      return self.clients.openWindow("./");
    })
  );
});
