// En iOS/Android la WebView sale con origen https://localhost o capacitor://localhost: una API en otro dominio exigiría CORS (y las cabeceras
// propias como X-Steps-Org lo complicarían). En nativo se usa el cliente HTTP del sistema (CapacitorHttp), que no está sujeto a CORS, SOLO para
// la API de Steps: el cliente del Tracker conserva su propio camino sin cambios. En web se usa fetch normal (mismo origen que Odoo o proxy).
import { Capacitor, CapacitorHttp } from '@capacitor/core';

type NativeHttp = { request(options: { url: string; method: string; headers: Record<string, string>; data?: unknown; responseType?: 'text' }): Promise<{ status: number; data: unknown; headers: Record<string, string> }> };

export function nativeFetch(http: NativeHttp): typeof fetch {
  return async (input, init) => {
    const headers: Record<string, string> = {};
    new Headers(init?.headers as HeadersInit).forEach((v, k) => { headers[k] = v; });
    let data: unknown;
    if (typeof init?.body === 'string') { try { data = JSON.parse(init.body); } catch { data = init.body; } }
    let res;
    try { res = await http.request({ url: String(input), method: init?.method ?? 'GET', headers, data, responseType: 'text' as const }); }
    catch (e) { throw new TypeError((e as Error)?.message || 'network down'); } // el cliente lo traduce a «sin conexión»
    const text = typeof res.data === 'string' ? res.data : JSON.stringify(res.data ?? null);
    const nobody = res.status === 204 || res.status === 304;
    return new Response(nobody ? null : text, { status: res.status, headers: { 'Content-Type': 'application/json' } });
  };
}

export const platformFetch: typeof fetch = (input, init) => (Capacitor.isNativePlatform() ? nativeFetch(CapacitorHttp) : fetch)(input, init);
