export function urlBase64ToUint8Array(base64) {
    const padding = '='.repeat((4 - base64.length % 4) % 4);
    const b64 = (base64 + padding).replace(/-/g, '+').replace(/_/g, '/');
    const raw = atob(b64);
    return new Uint8Array([...raw].map(c => c.charCodeAt(0)));
}

export async function registerServiceWorker() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;
    try {
        const reg = await navigator.serviceWorker.register('/static/core/js/service-worker.js', { scope: '/' });
        const sub = await reg.pushManager.getSubscription();
        return { registration: reg, subscription: sub };
    } catch { return null; }
}

export async function subscribeToPush(vapidPublicKey) {
    const info = await registerServiceWorker();
    if (!info) return null;
    const { registration } = info;
    let sub = info.subscription;
    if (!sub) {
        sub = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
        });
    }
    // Envoyer l'abonnement au serveur
    await fetch('/api/push/subscribe/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRF() },
        body: JSON.stringify(sub.toJSON()),
    });
    return sub;
}

export async function unsubscribeFromPush() {
    const info = await registerServiceWorker();
    if (!info?.subscription) return;
    await info.subscription.unsubscribe();
    await fetch('/api/push/unsubscribe/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRF() },
    });
}

function getCSRF() {
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : '';
}
