import { beforeEach, describe, expect, it } from 'vitest';
import { memoryKv } from '../shared/storage';
import { memorySecureStore } from '../platform/secureStore';
import { FakeSteps } from '../testing/fakeServer';
import { accessMode, mayStartProtectedAction } from './offline';
import { SessionManager } from './session';

const DEVICE = { uuid: 'dev-1', platform: 'web', label: 'Prueba', app_version: '2.0.0-test' };
const SUPPORTED = { colaciones: 1, mobilization: 1, tracker: 1 };
let server: FakeSteps, kv: ReturnType<typeof memoryKv>, secure: ReturnType<typeof memorySecureStore>;

const manager = () => new SessionManager({ kv, secure, device: async () => DEVICE, supported: SUPPORTED, fetchImpl: server.fetch, baseUrl: 'https://fake.test/steps_app/v1', now: () => server.now });
beforeEach(() => { server = new FakeSteps(); kv = memoryKv(); secure = memorySecureStore(); });

describe('política sin conexión', () => {
  const until = '2026-10-07T12:00:00Z', at = (h: number) => Date.parse('2026-10-04T12:00:00Z') + h * 3_600_000;
  it('en línea, dentro del plazo y vencido', () => {
    expect(accessMode({ validatedOnline: true, offlineUntil: until, now: at(0) })).toBe('online');
    expect(accessMode({ validatedOnline: false, offlineUntil: until, now: at(71) })).toBe('offline_valid');
    expect(accessMode({ validatedOnline: false, offlineUntil: until, now: at(72) })).toBe('offline_expired');
    expect(accessMode({ validatedOnline: false, offlineUntil: null, now: at(0) })).toBe('offline_expired');
    expect(mayStartProtectedAction('offline_valid')).toBe(true);
    expect(mayStartProtectedAction('offline_expired')).toBe(false);
  });
});

describe('registro e incorporación', () => {
  it('una persona recién registrada no ve módulos ni empresa y queda en incorporación', async () => {
    const s = manager(); await s.boot();
    await s.register('ana@example.test', 'clave-segura-2026', 'Ana');
    const snap = s.getSnapshot();
    expect(snap.status).toBe('signed_in');
    expect(snap.me?.onboarding).toBe('no_organization');
    expect(snap.catalog).toBeNull();
    expect(s.permissions().size).toBe(0);
    expect(s.can('colaciones.register')).toBe(false);
    expect(s.scope()).toBeNull();
  });

  it('una invitación válida habilita únicamente lo asignado', async () => {
    const s = manager(); await s.boot(); await s.register('ana@example.test', 'clave-segura-2026', 'Ana');
    server.people[0].verified = true;
    server.invitations.push({ token: 'inv-1', email: 'ana@example.test', orgUid: 'org-a', roles: [['colaciones', 'persona']] });
    await s.api.acceptInvitation('inv-1');
    await s.refreshAccess();
    const snap = s.getSnapshot();
    expect(snap.orgUid).toBe('org-a');
    expect(snap.catalog?.modules.map((m) => m.code)).toEqual(['colaciones']);
    expect(s.can('colaciones.read_own')).toBe(true);
    expect(s.can('colaciones.register')).toBe(false);
    expect(s.can('mobilization.drive')).toBe(false);
  });

  it('una invitación con el correo sin verificar se rechaza', async () => {
    const s = manager(); await s.boot(); await s.register('ana@example.test', 'clave-segura-2026', 'Ana');
    server.invitations.push({ token: 'inv-1', email: 'ana@example.test', orgUid: 'org-a', roles: [['colaciones', 'persona']] });
    await expect(s.api.acceptInvitation('inv-1')).rejects.toMatchObject({ code: 'email_not_verified' });
  });

  it('solicitar acceso deja la membresía pendiente sin habilitar nada', async () => {
    const s = manager(); await s.boot(); await s.register('ana@example.test', 'clave-segura-2026', 'Ana');
    await s.api.requestAccess('AAAA1111', 'Soy conductor');
    await s.refreshAccess();
    expect(s.getSnapshot().me?.onboarding).toBe('request_pending');
    expect(s.getSnapshot().orgUid).toBeNull();
  });
});

describe('empresas y revalidación', () => {
  it('con varias empresas activas pide elegir y revalida al cambiar', async () => {
    const p = server.addPerson('ana@example.test');
    server.grant(p.id, 'org-a', ['colaciones', 'operador']); server.grant(p.id, 'org-b', ['mobilization', 'conductor']);
    const s = manager(); await s.boot(); await s.login('ana@example.test', 'clave-segura-2026');
    expect(s.getSnapshot().needsOrgChoice).toBe(true);
    expect(s.getSnapshot().catalog).toBeNull();
    await s.selectOrg('org-a');
    expect(s.getSnapshot().catalog?.modules.map((m) => m.code)).toEqual(['colaciones']);
    await s.selectOrg('org-b');
    expect(s.getSnapshot().catalog?.modules.map((m) => m.code)).toEqual(['mobilization']);
    expect(s.scope()).toEqual({ personId: p.id, orgUid: 'org-b' });
  });

  it('la revocación en línea se refleja al revalidar', async () => {
    const p = server.addPerson('ana@example.test'); server.grant(p.id, 'org-a', ['colaciones', 'operador']);
    const s = manager(); await s.boot(); await s.login('ana@example.test', 'clave-segura-2026');
    expect(s.can('colaciones.register')).toBe(true);
    server.revokeGrants(p.id, 'org-a');
    await s.revalidate();
    expect(s.getSnapshot().orgUid).toBeNull();
    expect(s.can('colaciones.register')).toBe(false);
    expect(s.getSnapshot().notice).toMatch(/Ya no tienes acceso/);
  });

  it('un módulo cuyo contrato la app no entiende no se ofrece y se informa', async () => {
    const p = server.addPerson('ana@example.test'); server.grant(p.id, 'org-a', ['colaciones', 'operador'], ['tracker', 'operador']);
    server.contract.tracker = 2;
    const s = manager(); await s.boot(); await s.login('ana@example.test', 'clave-segura-2026');
    expect(s.getSnapshot().catalog?.modules.map((m) => m.code)).toEqual(['colaciones']);
    expect(s.getSnapshot().catalog?.incompatible_modules[0]).toMatchObject({ code: 'tracker', reason: 'app_update_required' });
  });
});

describe('sesión y sin conexión', () => {
  it('reabre sin conexión con la caché mientras el plazo vale, y bloquea acciones nuevas al vencer', async () => {
    const p = server.addPerson('ana@example.test'); server.grant(p.id, 'org-a', ['colaciones', 'operador']);
    let s = manager(); await s.boot(); await s.login('ana@example.test', 'clave-segura-2026');
    server.offline = true;
    s = manager(); await s.boot();
    expect(s.getSnapshot()).toMatchObject({ status: 'signed_in', access: 'offline_valid', orgUid: 'org-a' });
    expect(s.can('colaciones.register')).toBe(true);
    server.now += 73 * 3_600_000;
    s = manager(); await s.boot();
    expect(s.getSnapshot().access).toBe('offline_expired');
    expect(s.can('colaciones.register')).toBe(false);
    expect(s.scope()).not.toBeNull(); // la cola se sigue identificando para conservarla
  });

  it('un token de acceso vencido se renueva solo, una vez, aunque lleguen varias llamadas', async () => {
    const p = server.addPerson('ana@example.test'); server.grant(p.id, 'org-a', ['colaciones', 'operador']);
    const s = manager(); await s.boot(); await s.login('ana@example.test', 'clave-segura-2026');
    server.expireAccessTokens();
    await Promise.all([s.api.devices(), s.api.devices(), s.api.devices()]);
    expect(server.requests.filter((r) => r.path === '/auth/refresh')).toHaveLength(1);
  });

  it('sin red al renovar no se cierra la sesión', async () => {
    const p = server.addPerson('ana@example.test'); server.grant(p.id, 'org-a', ['colaciones', 'operador']);
    const s = manager(); await s.boot(); await s.login('ana@example.test', 'clave-segura-2026');
    server.expireAccessTokens(); server.offline = true;
    await expect(s.api.devices()).rejects.toMatchObject({ code: 'network' });
    expect(s.getSnapshot().status).toBe('signed_in');
  });

  it('el servidor revoca la sesión: la app vuelve a la pantalla de acceso con aviso', async () => {
    const p = server.addPerson('ana@example.test'); server.grant(p.id, 'org-a', ['colaciones', 'operador']);
    const s = manager(); await s.boot(); await s.login('ana@example.test', 'clave-segura-2026');
    server.revokeSessions(p.id);
    await expect(s.api.devices()).rejects.toMatchObject({ status: 401 });
    expect(s.getSnapshot()).toMatchObject({ status: 'signed_out', notice: expect.stringMatching(/sesión/i) });
    expect(secure.data.size).toBe(0);
  });

  it('cerrar sesión borra credenciales y caché pero no toca las colas guardadas', async () => {
    const p = server.addPerson('ana@example.test'); server.grant(p.id, 'org-a', ['colaciones', 'operador']);
    const s = manager(); await s.boot(); await s.login('ana@example.test', 'clave-segura-2026');
    await kv.set(`steps.queue.v1.${p.id}.org-a`, '[{"id":"x"}]');
    await s.logout();
    expect(secure.data.size).toBe(0);
    expect(await kv.get(`steps.session.v1.${p.id}`)).toBeNull();
    expect(await kv.get(`steps.queue.v1.${p.id}.org-a`)).toBe('[{"id":"x"}]');
    expect(s.getSnapshot().status).toBe('signed_out');
  });

  it('credenciales incorrectas no abren sesión', async () => {
    server.addPerson('ana@example.test');
    const s = manager(); await s.boot();
    await expect(s.login('ana@example.test', 'mala-clave-123')).rejects.toMatchObject({ code: 'invalid_credentials' });
    expect(s.getSnapshot().status).toBe('signed_out');
  });
});
