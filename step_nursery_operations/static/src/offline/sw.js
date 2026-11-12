const cacheName = "steps-nursery-shell-v1";
const shell = "/nursery-offline/";
const assets = [shell, "/step_nursery_operations/static/src/offline/app.js",
    "/step_nursery_operations/static/src/offline/offline.css"];
self.addEventListener("install", event => event.waitUntil(caches.open(cacheName)
    .then(cache => cache.addAll(assets)).then(() => self.skipWaiting())));
self.addEventListener("activate", event => event.waitUntil(caches.keys().then(keys => Promise.all(keys
    .filter(key => key.startsWith("steps-nursery-shell-") && key !== cacheName)
    .map(key => caches.delete(key)))).then(() => self.clients.claim())));
self.addEventListener("fetch", event => {
    const url = new URL(event.request.url);
    if (event.request.method !== "GET" || url.origin !== self.location.origin || !assets.includes(url.pathname)) return;
    event.respondWith(fetch(event.request).catch(async () => {
        const cache = await caches.open(cacheName);
        return (await cache.match(url.pathname)) || Response.error();
    }));
});
