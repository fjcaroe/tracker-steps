/**
 * Service worker de la App de Colaciones.
 *
 * Todas las rutas se resuelven contra el ámbito de registro, no contra una ruta
 * fija: la misma aplicación se sirve en `https://colaciones.stepsapp.cl/` y en
 * `https://desarrollo.stepsapp.cl/colaciones/app/`.
 */
const VERSION = "2026.08.21.4";
const CACHE = `steps-colaciones-${VERSION}`;
const SCOPE = new URL("./", self.location).href;

const APP_SHELL = [
  "./",
  "./index.html",
  "./styles.css",
  "./manifest.webmanifest",
  "./icon.png",
  "./src/ui/main.js",
  "./src/ui/view.js",
  "./src/core/index.js",
  "./src/core/constants.js",
  "./src/core/errors.js",
  "./src/core/identity.js",
  "./src/core/api-client.js",
  "./src/core/queue.js",
  "./src/core/sync-engine.js",
  "./src/core/totem-session.js",
  "./src/core/diagnostics.js",
  "./src/core/migrations.js",
  "./src/adapters/web/fetch-transport.js",
  "./src/adapters/web/indexeddb-queue-repository.js",
  "./src/adapters/web/web-stores.js",
  "./src/adapters/web/web-device-info.js",
  "./src/adapters/web/web-network-monitor.js",
  "./src/adapters/web/web-scanner.js",
].map((path) => new URL(path, self.location).href);

self.addEventListener("install", (event) => {
  // Sin `skipWaiting`: la versión nueva espera a que la App confirme que no hay
  // capturas en vuelo. Así una actualización nunca interrumpe una marcación.
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(APP_SHELL)));
});

self.addEventListener("message", (event) => {
  if (event.data?.type === "SKIP_WAITING") self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)));
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  // La API nunca se cachea: una respuesta vieja aquí significa registrar mal.
  if (url.pathname.startsWith("/colaciones/api/")) return;
  if (!request.url.startsWith(SCOPE)) return;

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() => caches.match(new URL("./index.html", self.location).href)),
    );
    return;
  }

  event.respondWith((async () => {
    const cached = await caches.match(request);
    if (cached) return cached;
    const response = await fetch(request);
    if (response.ok && response.type === "basic") {
      const cache = await caches.open(CACHE);
      cache.put(request, response.clone());
    }
    return response;
  })());
});
