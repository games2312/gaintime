self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(clients.claim()));

const GOLD = '#f59e0b';

self.addEventListener('push', (e) => {
    let data = {};
    try {
        data = e.data.json();
    } catch {
        data = { title: 'GainTime', body: e.data.text() };
    }
    const opts = {
        body: data.body || '',
        icon: data.icon || '/static/core/img/icon-192.png',
        badge: '/static/core/img/badge-72.png',
        vibrate: [200, 100, 200],
        data: { url: data.url || '/' },
        actions: data.actions || [],
        requireInteraction: true,
    };
    e.waitUntil(self.registration.showNotification(data.title || 'GainTime', opts));
});

self.addEventListener('notificationclick', (e) => {
    e.notification.close();
    const url = e.notification.data?.url || '/';
    e.waitUntil(clients.openWindow(url));
});
