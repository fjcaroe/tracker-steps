/**
 * Transporte HTTP de la PWA: `fetch` contra el mismo origen.
 *
 * Al compartir origen con la API no hace falta CORS ni credenciales. La App
 * móvil usa un transporte nativo distinto con la misma firma.
 */
export function createFetchTransport({ fetchImpl = globalThis.fetch.bind(globalThis) } = {}) {
  return async function transport({ method, url, body, timeoutMs = 15_000 }) {
    const controller = typeof AbortController === "function" ? new AbortController() : null;
    const timer = controller ? setTimeout(() => controller.abort(), timeoutMs) : null;
    try {
      const response = await fetchImpl(url, {
        method,
        cache: "no-store",
        credentials: "omit",
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
        signal: controller?.signal,
      });
      let payload = null;
      try {
        payload = await response.json();
      } catch (_) {
        // Un 502 de Nginx responde HTML: se trata por código, no por cuerpo.
        payload = null;
      }
      return { status: response.status, body: payload };
    } finally {
      if (timer) clearTimeout(timer);
    }
  };
}
