const CACHE = 'gaintime-v2';
const PRECACHE = [
    '/dashboard/',
    '/static/manifest.json',
    'https://cdn.tailwindcss.com',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
    'https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700&display=swap',
    'https://cdn.jsdelivr.net/npm/canvas-confetti@1.6.0/dist/confetti.browser.min.js',
];

self.addEventListener('install', (e) => {
    self.skipWaiting();
    e.waitUntil(
        caches.open(CACHE).then((c) => c.addAll(PRECACHE))
    );
});

self.addEventListener('activate', (e) => {
    e.waitUntil(clients.claim());
});

self.addEventListener('fetch', (e) => {
    if (e.request.method !== 'GET') return;
    if (e.request.url.startsWith('chrome-extension')) return;

    e.respondWith(
        caches.match(e.request).then((cached) => {
            const fetched = fetch(e.request).then((res) => {
                if (res.ok && res.type === 'basic') {
                    const clone = res.clone();
                    caches.open(CACHE).then((c) => c.put(e.request, clone));
                }
                return res;
            }).catch(() => cached);
            return cached || fetched;
        }).catch(() => {
            if (e.request.mode === 'navigate') {
                return caches.match('/offline/');
            }
        })
    );
});

const GOLD = '#f59e0b';

self.addEventListener('push', (e) => {
    let data = {};
    try { data = e.data.json(); } catch { data = { title: 'GainTime', body: e.data.text() }; }
    const opts = {
        body: data.body || '',
        icon: data.icon || '/static/core/img/icon-512.svg',
        badge: '/static/core/img/badge-72.svg',
        vibrate: [200, 100, 200],
        data: { url: data.url || '/' },
        actions: data.actions || [],
        requireInteraction: true,
    };
    e.waitUntil(self.registration.showNotification(data.title || 'GainTime', opts));
});

self.addEventListener('notificationclick', (e) => {
    e.notification.close();
    e.waitUntil(clients.openWindow(e.notification.data?.url || '/'));
});
