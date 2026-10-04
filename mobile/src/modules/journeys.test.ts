// Recorridos completos del piloto contra el servidor FALSO del contrato (no es evidencia de Odoo; ver testing/fakeServer.ts).
import { beforeEach, describe, expect, it } from 'vitest';
import { Runtime } from '../app/runtime';
import { SessionManager } from '../app/session';
import { memorySecureStore } from '../platform/secureStore';
import { memoryKv } from '../shared/storage';
import { FakeSteps } from '../testing/fakeServer';
import { buildRegistration, colacionesApi, colacionesHandlers, groupFor as colGroup } from './colaciones/service';
import { buildEvent, groupFor as tripGroup, mobilizationApi, mobilizationHandlers } from './mobilization/service';
import { DurableQueue } from '../sync/queue';
import type { ModuleManifest } from './registry';

const SUPPORTED = { colaciones: 1, mobilization: 1, tracker: 1 };
const manifests = (): ModuleManifest[] => [
  { id: 'colaciones', contractVersion: 1, name: 'C', tagline: '', icon: '', capabilities: [], requiredPermissions: ['colaciones.read_own', 'colaciones.register'], load: async () => ({ default: () => null }), handlers: colacionesHandlers },
  { id: 'mobilization', contractVersion: 1, name: 'M', tagline: '', icon: '', capabilities: [], requiredPermissions: ['mobilization.drive'], load: async () => ({ default: () => null }), handlers: mobilizationHandlers },
];
let server: FakeSteps, kv: ReturnType<typeof memoryKv>;

async function device(email: string, kvOverride = kv) {
  const session = new SessionManager({ kv: kvOverride, secure: memorySecureStore(), device: async () => ({ uuid: `dev-${email}`, platform: 'web', app_version: 't' }), supported: SUPPORTED, fetchImpl: server.fetch, baseUrl: 'https://fake.test/steps_app/v1', now: () => server.now });
  await session.boot(); await session.login(email, 'clave-segura-2026');
  const runtime = new Runtime(session, kvOverride, manifests());
  await runtime.refresh();
  return { session, runtime };
}
beforeEach(() => { server = new FakeSteps(); kv = memoryKv(); });

describe('Colaciones: administrador asigna → persona consulta → operador registra (también tras un corte)', () => {
  it('recorrido completo', async () => {
    const worker = server.addPerson('trabajador@example.test'), op = server.addPerson('operador@example.test');
    server.grant(worker.id, 'org-a', ['colaciones', 'persona']).employee = 1;
    server.grant(op.id, 'org-a', ['colaciones', 'operador']);

    // La persona consulta lo suyo y NO puede registrar.
    const w = await device('trabajador@example.test');
    expect(w.session.can('colaciones.read_own')).toBe(true);
    expect(w.session.can('colaciones.register')).toBe(false);
    expect(await colacionesApi(w.session.api).me()).toMatchObject({ linked: true, today: { registered: false } });
    await expect(colacionesApi(w.session.api).totems()).rejects.toMatchObject({ status: 403 });

    // El operador captura SIN señal: se guarda y el teléfono lo muestra como pendiente.
    const o = await device('operador@example.test');
    expect(o.session.can('colaciones.register')).toBe(true);
    const { totems } = await colacionesApi(o.session.api).totems();
    expect(totems.map((t) => t.id)).toEqual([1]); // solo los tótems de su empresa
    server.offline = true;
    const cap = buildRegistration(totems[0], 'BR0001');
    await o.runtime.enqueue({ module: 'colaciones', kind: 'register', group: colGroup(1), payload: cap.payload, id: cap.id });
    await o.runtime.sync();
    expect(o.runtime.getSnapshot()).toMatchObject({ pending: 1, rejected: 0, lastHalt: 'network' });
    expect(server.registrations.size).toBe(0);

    // Vuelve la señal: llega una sola vez, con autoría del operador, y no queda el identificador del trabajador.
    server.offline = false;
    await o.runtime.sync();
    expect(server.registrations.size).toBe(1);
    expect([...server.registrations.values()][0]).toMatchObject({ employee: 'Trabajador Uno', operator: op.id });
    const [confirmed] = await o.runtime.ops('colaciones');
    expect(confirmed).toMatchObject({ state: 'confirmed', result: { employee: 'Trabajador Uno', duplicate: false } });
    expect((confirmed.payload as { record: { identifier: string } }).record.identifier).toBe('');
    expect(o.runtime.getSnapshot().pending).toBe(0);

    // La persona ve su registro; nunca el de otros.
    expect(await colacionesApi(w.session.api).me()).toMatchObject({ today: { registered: false } }); // vinculada a otro trabajador de prueba
  });

  it('duplicado: un reenvío con el mismo UUID y otro intento el mismo día no generan segunda entrega', async () => {
    const op = server.addPerson('operador@example.test'); server.grant(op.id, 'org-a', ['colaciones', 'operador']);
    const o = await device('operador@example.test');
    const totem = { id: 1, name: 'Casino 1' };
    const first = buildRegistration(totem, 'BR0001');
    await o.runtime.enqueue({ module: 'colaciones', kind: 'register', group: colGroup(1), payload: first.payload, id: first.id });
    // Doble pulsación: mismo UUID → una sola operación.
    await o.runtime.enqueue({ module: 'colaciones', kind: 'register', group: colGroup(1), payload: first.payload, id: first.id });
    await o.runtime.sync();
    // Reenvío simulado del mismo lote tras perder la respuesta.
    const q = o.runtime.queue()!;
    await q.update({ [first.id]: { state: 'pending' } });
    await o.runtime.sync();
    // Otro UUID, mismo trabajador, mismo día.
    const again = buildRegistration(totem, 'BR0001');
    await o.runtime.enqueue({ module: 'colaciones', kind: 'register', group: colGroup(1), payload: again.payload, id: again.id });
    await o.runtime.sync();
    expect(server.registrations.size).toBe(1);
    const results = (await o.runtime.ops('colaciones')).map((x) => [x.state, (x.result as { duplicate: boolean }).duplicate]);
    expect(results).toEqual([['confirmed', true], ['confirmed', true]]);
  });

  it('rechazos del servidor se conservan con su motivo y no frenan otras capturas', async () => {
    const op = server.addPerson('operador@example.test'); server.grant(op.id, 'org-a', ['colaciones', 'operador']);
    const o = await device('operador@example.test');
    const totem = { id: 1, name: 'Casino 1' };
    for (const code of ['BR0003', 'NOEXISTE', 'BR9999', 'BR0002']) {
      const c = buildRegistration(totem, code);
      await o.runtime.enqueue({ module: 'colaciones', kind: 'register', group: colGroup(1), payload: c.payload, id: c.id });
    }
    await o.runtime.sync();
    expect((await o.runtime.ops('colaciones')).map((x) => x.state)).toEqual(['rejected', 'rejected', 'rejected', 'confirmed']);
    expect(o.runtime.getSnapshot()).toMatchObject({ rejected: 3, pending: 0 });
    // Rechazadas no desaparecen: se pueden exportar.
    expect(JSON.parse(await o.runtime.queue()!.exportJson()).ops.filter((x: { state: string }) => x.state === 'rejected')).toHaveLength(3);
  });

  it('capturas anteriores a la revocación se aceptan; posteriores se rechazan con motivo', async () => {
    const op = server.addPerson('operador@example.test'); server.grant(op.id, 'org-a', ['colaciones', 'operador']);
    const o = await device('operador@example.test');
    server.offline = true;
    const before = buildRegistration({ id: 1, name: 'Casino 1' }, 'BR0001', new Date(server.now - 3_600_000));
    await o.runtime.enqueue({ module: 'colaciones', kind: 'register', group: colGroup(1), payload: before.payload, id: before.id });
    server.now += 60_000;
    server.revokeGrants(op.id, 'org-a'); server.now += 60_000;
    const after = buildRegistration({ id: 1, name: 'Casino 1' }, 'BR0002', new Date(server.now));
    await o.runtime.enqueue({ module: 'colaciones', kind: 'register', group: colGroup(1), payload: after.payload, id: after.id });
    server.offline = false;
    await o.runtime.sync();
    const [a, b] = await o.runtime.ops('colaciones');
    expect(a.state).toBe('confirmed');
    expect(b).toMatchObject({ state: 'rejected', error: 'access_ended_before_capture' });
  });

  it('aislamiento: otro usuario o empresa en el mismo teléfono no mezcla ni envía las operaciones ajenas', async () => {
    const a = server.addPerson('a@example.test'), b = server.addPerson('b@example.test');
    server.grant(a.id, 'org-a', ['colaciones', 'operador']); server.grant(b.id, 'org-a', ['colaciones', 'operador']); server.grant(a.id, 'org-b', ['colaciones', 'operador']);
    const da = await device('a@example.test');
    await da.session.selectOrg('org-a');
    server.offline = true;
    const cap = buildRegistration({ id: 1, name: 'Casino 1' }, 'BR0001');
    await da.runtime.enqueue({ module: 'colaciones', kind: 'register', group: colGroup(1), payload: cap.payload, id: cap.id });
    server.offline = false;
    await da.session.logout();
    // B entra en el MISMO teléfono (misma memoria local): ve que hay datos ajenos y no los envía.
    const db = await device('b@example.test');
    expect(db.runtime.getSnapshot().foreign.map((f) => f.scope.personId)).toEqual([a.id]);
    await db.runtime.sync();
    expect(server.registrations.size).toBe(0);
    expect(await db.runtime.ops('colaciones')).toEqual([]);
    // Cuando A vuelve, su cola sigue intacta y se envía.
    const da2 = await device('a@example.test');
    await da2.session.selectOrg('org-a');
    expect((await da2.runtime.ops('colaciones')).length).toBe(1); // sigue guardada, nadie la borró
    await da2.runtime.sync(); // al volver a entrar se reanuda lo que esperaba sesión
    expect(server.registrations.size).toBe(1);
    // Cambiar de empresa no mezcla colas.
    await da2.session.selectOrg('org-b');
    expect(await da2.runtime.ops('colaciones')).toEqual([]);
  });

  it('sesión vencida durante el envío: la cola se conserva y no se marca como rechazo del negocio', async () => {
    const op = server.addPerson('operador@example.test'); server.grant(op.id, 'org-a', ['colaciones', 'operador']);
    const o = await device('operador@example.test');
    const c = buildRegistration({ id: 1, name: 'Casino 1' }, 'BR0001');
    const scope = o.session.scope()!;
    await o.runtime.queue()!.enqueue({ module: 'colaciones', kind: 'register', group: colGroup(1), payload: c.payload, id: c.id });
    server.revokeSessions(op.id);
    const summary = await o.runtime.sync();
    expect(summary?.halted).toBe('auth');
    expect((await new DurableQueue(kv, scope).list())[0].state).toBe('auth_required');
    expect(o.session.getSnapshot().status).toBe('signed_out');
    expect(server.registrations.size).toBe(0);
  });
});

describe('Movilización: asignación en Odoo → conductor → eventos con y sin red → supervisor', () => {
  it('recorrido completo sin duplicados y con autoría', async () => {
    const d1 = server.addPerson('conductor1@example.test'), d2 = server.addPerson('conductor2@example.test'), sup = server.addPerson('supervisor@example.test');
    server.grant(d1.id, 'org-a', ['mobilization', 'conductor']); server.grant(d2.id, 'org-a', ['mobilization', 'conductor']); server.grant(sup.id, 'org-a', ['mobilization', 'supervisor']);
    const mine = server.addTrip('org-a', d1.id), other = server.addTrip('org-a', d2.id);

    const c = await device('conductor1@example.test');
    const api = mobilizationApi(c.session.api);
    expect((await api.trips()).trips.map((t) => t.id)).toEqual([mine.id]);
    await expect(api.trip(other.id)).rejects.toMatchObject({ status: 404 }); // el servicio de otro conductor no existe para él

    // Sin red: abrir, marcar dos pasajeros y cerrar. Todo queda en orden en el teléfono.
    server.offline = true;
    const g = tripGroup(mine.id);
    await c.runtime.enqueue({ module: 'mobilization', kind: 'trip_open', group: g, payload: { tripId: mine.id } });
    const events = [buildEvent({ type: 'boarding', method: 'barcode', identifier: 'BR0001' }), buildEvent({ type: 'boarding', method: 'barcode', identifier: 'BR0002' })];
    for (const e of events) await c.runtime.enqueue({ module: 'mobilization', kind: 'event', group: g, payload: { tripId: mine.id, tripName: mine.name, event: e, label: e.identifier } });
    await c.runtime.enqueue({ module: 'mobilization', kind: 'trip_close', group: g, payload: { tripId: mine.id } });
    expect(c.runtime.getSnapshot().pending).toBe(4);

    server.offline = false;
    await c.runtime.sync();
    expect(c.runtime.getSnapshot()).toMatchObject({ pending: 0, rejected: 0 });
    expect(server.trips.find((t) => t.id === mine.id)!.state).toBe('closed');
    expect(server.events.size).toBe(2);

    // Reenviar el mismo lote (respuesta perdida) no duplica.
    const q = c.runtime.queue()!;
    await q.update(Object.fromEntries((await q.list()).filter((o) => o.kind === 'event').map((o) => [o.id, { state: 'pending' as const }])));
    await c.runtime.sync();
    expect(server.events.size).toBe(2);

    // Un pasajero ajeno o un evento tras el cierre se rechaza de forma definitiva, sin bloquear nada más.
    const late = buildEvent({ type: 'alighting', method: 'barcode', identifier: 'BR0001' });
    await c.runtime.enqueue({ module: 'mobilization', kind: 'event', group: g, payload: { tripId: mine.id, tripName: mine.name, event: late, label: 'x' } });
    await c.runtime.sync();
    expect((await c.runtime.ops('mobilization')).at(-1)).toMatchObject({ state: 'rejected', error: 'trip_not_open' });

    // El supervisor consulta el resultado; el conductor no puede supervisar.
    const s = await device('supervisor@example.test');
    const result = await mobilizationApi(s.session.api).supervisorTrips();
    const trip = result.trips.find((t) => t.id === mine.id)!;
    expect(trip).toMatchObject({ boarded_count: 2, driver: 'conductor1' });
    expect(trip.events!.every((e) => e.by === 'conductor1')).toBe(true);
    await expect(mobilizationApi(c.session.api).supervisorTrips()).rejects.toMatchObject({ status: 403 });
  });

  it('un corte a mitad de lote no pierde ni duplica: abrir y cerrar respetan el orden del servicio', async () => {
    const d = server.addPerson('conductor@example.test'); server.grant(d.id, 'org-a', ['mobilization', 'conductor']);
    const trip = server.addTrip('org-a', d.id);
    const c = await device('conductor@example.test');
    const g = tripGroup(trip.id);
    await c.runtime.enqueue({ module: 'mobilization', kind: 'trip_open', group: g, payload: { tripId: trip.id } });
    await c.runtime.enqueue({ module: 'mobilization', kind: 'event', group: g, payload: { tripId: trip.id, tripName: trip.name, event: buildEvent({ type: 'boarding', method: 'barcode', identifier: 'BR0001' }), label: 'x' } });
    await c.runtime.enqueue({ module: 'mobilization', kind: 'trip_close', group: g, payload: { tripId: trip.id } });
    // Falla transitoria del servidor al enviar los eventos: el cierre NO debe adelantarse.
    await c.runtime.sync();
    const sent = server.requests.map((r) => r.path);
    expect(sent.indexOf(`/mobilization/trips/${trip.id}/open`)).toBeLessThan(sent.indexOf(`/mobilization/trips/${trip.id}/events`));
    expect(sent.indexOf(`/mobilization/trips/${trip.id}/events`)).toBeLessThan(sent.indexOf(`/mobilization/trips/${trip.id}/close`));
  });

  it('un conductor sin permiso (revocado) no consulta servicios y su cola de eventos previos se conserva', async () => {
    const d = server.addPerson('conductor@example.test'); server.grant(d.id, 'org-a', ['mobilization', 'conductor']);
    const trip = server.addTrip('org-a', d.id, 'open');
    const c = await device('conductor@example.test');
    server.offline = true;
    const before = buildEvent({ type: 'boarding', method: 'barcode', identifier: 'BR0001' }, new Date(server.now - 600_000));
    await c.runtime.enqueue({ module: 'mobilization', kind: 'event', group: tripGroup(trip.id), payload: { tripId: trip.id, tripName: trip.name, event: before, label: 'x' } });
    server.offline = false; server.now += 1000;
    server.revokeGrants(d.id, 'org-a'); server.now += 1000;
    await c.runtime.sync();
    expect((await c.runtime.ops('mobilization'))[0].state).toBe('confirmed'); // capturado antes de la revocación
    await c.session.revalidate();
    expect(c.session.can('mobilization.drive')).toBe(false);
    // Tras revalidar, la app ya no tiene empresa activa: no llega a pedir nada al servidor.
    expect(c.session.getSnapshot().orgUid).toBeNull();
    await expect(mobilizationApi(c.session.api).trips()).rejects.toMatchObject({ code: 'organization_required' });
  });
});
