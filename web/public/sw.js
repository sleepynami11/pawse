// Minimal service worker: lets the app be installed and open the shell offline.
// Network-first for everything, falling back to cache. Never caches API calls.
const CACHE = 'pawse-shell-v2';

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(['./', 'manifest.webmanifest', 'icon.svg'])));
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith('pawse-shell-') && k !== CACHE).map((k) => caches.delete(k))))
  );
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  const url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== self.location.origin) return;
  if (url.search || !(url.pathname === '/app/' || url.pathname.startsWith('/app/assets/') || ['/app/icon.svg', '/app/manifest.webmanifest'].includes(url.pathname))) return;
  e.respondWith(
    fetch(req)
      .then((res) => {
        if (!res.ok || res.headers.get('Cache-Control')?.includes('no-store')) return res;
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy));
        return res;
      })
      .catch(() => caches.match(req).then((hit) => hit || caches.match('./')))
  );
});
