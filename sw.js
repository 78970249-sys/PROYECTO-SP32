// Guarda la app para que funcione sin internet (útil al configurar el Wi-Fi de KusiVox).
const CACHE = "kusivox-v4";
const ARCHIVOS = ["./", "index.html", "manifest.webmanifest", "img/icon-192.png", "img/icon-512.png",
  "img/maskable-512.png", "img/apple-touch-icon.png", "img/kusi-cabeza.png", "img/neutral.gif", "img/happy.gif",
  "img/winking.gif", "img/thinking.gif", "img/loving.gif"];
self.addEventListener("install", (e) => { e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ARCHIVOS))); self.skipWaiting(); });
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))));
  self.clients.claim();
});
self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET" || new URL(e.request.url).origin !== location.origin) return;
  e.respondWith(caches.match(e.request).then((r) => r || fetch(e.request)));
});
