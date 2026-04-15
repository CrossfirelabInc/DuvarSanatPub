const CACHE_NAME = 'duvarsanat-v2';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  // Skip API and upload requests — let network handle them
  if (event.request.url.includes('/api/') || event.request.url.includes('/uploads/')) {
    return;
  }
  // Network-first: try network, fall back to cache (for offline support)
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // Cache successful responses for offline use
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});
