import { describe, expect, it } from 'vitest';
import { nativeFetch } from './http';

describe('cliente HTTP nativo', () => {
  it('envía JSON con cabeceras y devuelve una Response normal', async () => {
    let seen: Record<string, unknown> = {};
    const f = nativeFetch({ request: async (o) => { seen = o; return { status: 200, data: '{"ok":true}', headers: {} }; } });
    const r = await f('https://x.test/a', { method: 'POST', headers: { Authorization: 'Bearer t', 'X-Steps-Org': 'o' }, body: JSON.stringify({ a: 1 }) });
    expect(seen).toMatchObject({ url: 'https://x.test/a', method: 'POST', data: { a: 1 } });
    expect((seen.headers as Record<string, string>).authorization).toBe('Bearer t');
    expect(await r.json()).toEqual({ ok: true });
  });
  it('un error de red nativo se vuelve TypeError (sin conexión), no un rechazo del servidor', async () => {
    const f = nativeFetch({ request: async () => { throw new Error('offline'); } });
    await expect(f('https://x.test/a')).rejects.toBeInstanceOf(TypeError);
  });
  it('conserva el estado HTTP de los errores del servidor', async () => {
    const f = nativeFetch({ request: async () => ({ status: 401, data: { ok: false, error: 'token_expired' }, headers: {} }) });
    const r = await f('https://x.test/a');
    expect([r.status, (await r.json()).error]).toEqual([401, 'token_expired']);
  });
});
