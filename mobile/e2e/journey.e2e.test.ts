// Recorrido de aceptación contra Odoo real: registro → administración → sesión → operación sin señal → llegada única → verificación →
// revocación → aislamiento → recuperación. El cliente es el MISMO código de la app (SessionManager, Runtime, cola durable, handlers).
import { beforeAll, describe, expect, it } from 'vitest';
import { Runtime } from '../src/app/runtime';
import { SessionManager } from '../src/app/session';
import { MODULES } from '../src/modules';
import { buildRegistration, colacionesApi, groupFor as colGroup } from '../src/modules/colaciones/service';
import { buildEvent, groupFor as tripGroup, mobilizationApi } from '../src/modules/mobilization/service';
import { supportedContracts } from '../src/modules/registry';
import { memorySecureStore } from '../src/platform/secureStore';
import { memoryKv } from '../src/shared/storage';
import { BASE, OdooUser, summary, type Summary } from './odoo';

const API = `${BASE}/steps_app/v1`;
let S: Summary;
let net = { down: false };
const flaky: typeof fetch = (input, init) => (net.down ? Promise.reject(new TypeError('sin señal (simulado)')) : fetch(input, init));

type Phone = { kv: ReturnType<typeof memoryKv>; session: SessionManager; runtime: Runtime };
/** Un «teléfono»: almacenamiento propio (se puede reutilizar para simular el mismo equipo con otra cuenta). */
function phone(kv = memoryKv(), secure = memorySecureStore(), uuid = 'phone-' + Math.random().toString(36).slice(2)): Phone {
  const session = new SessionManager({ kv, secure, device: async () => ({ uuid, platform: 'e2e', label: 'E2E', app_version: 'e2e' }), supported: supportedContracts(MODULES), fetchImpl: flaky, baseUrl: API });
  return { kv, session, runtime: new Runtime(session, kv, MODULES) };
}
async function signIn(email: string, kv?: ReturnType<typeof memoryKv>, org?: 'norte' | 'sur'): Promise<Phone> {
  const p = phone(kv);
  await p.session.boot();
  await p.session.login(email, S.password);
  if (org) await p.session.selectOrg(S.companies[org].org_uid);
  await p.runtime.refresh();
  return p;
}
const user = (key: string) => S.users[key];

beforeAll(() => { S = summary(); });

describe('Recorrido extremo a extremo con Odoo real', () => {
  const nuevo = 'nuevo@demo.steps.test';

  it('1-2. Una persona se registra, queda sin acceso, y un administrador la identifica y habilita desde Odoo', async () => {
    const p = phone(); await p.session.boot();
    await p.session.register(nuevo, S.password, 'Persona Nueva');
    expect(p.session.getSnapshot().me?.onboarding).toBe('no_organization');
    expect(p.session.getSnapshot().catalog).toBeNull();
    // Sin membresía no puede consultar nada empresarial, ni forzando la cabecera de empresa.
    await expect(p.session.api.request('GET', '/colaciones/me')).rejects.toMatchObject({ code: 'organization_required' });
    const forced = await fetch(`${API}/catalog`, { headers: { Authorization: `Bearer ${(p.session as unknown as { tokens: { access_token: string } }).tokens.access_token}`, 'X-Steps-Org': S.companies.norte.org_uid } });
    expect(forced.status).toBe(403);

    // El correo se verifica (en el piloto sin correo saliente lo hace un administrador del sistema, con auditoría) y se acepta la invitación.
    const sysadmin = await OdooUser.login('admin', process.env.STEPS_E2E_ADMIN_PASSWORD ?? 'admin');
    const [identity] = await sysadmin.searchRead('step.app.identity', [['subject', '=', nuevo]], ['id']);
    await sysadmin.ok('step.app.identity', 'action_mark_email_verified', [[identity.id as number]]);
    await p.session.api.acceptInvitation(S.invitation.code);
    await p.session.refreshAccess();
    expect(p.session.getSnapshot().orgUid).toBe(S.companies.norte.org_uid);
    expect(p.session.getSnapshot().catalog?.modules.map((m) => m.code)).toEqual(['colaciones']);
    expect(p.session.can('colaciones.read_own')).toBe(true);
    expect(p.session.can('colaciones.register')).toBe(false);
    // La invitación se consumió.
    await expect(p.session.api.acceptInvitation(S.invitation.code)).rejects.toMatchObject({ code: 'invalid_invitation' });
  });

  it('2. El administrador de Norte aprueba una solicitud con el asistente; el de Sur y el usuario sin acceso no pueden', async () => {
    const adminNorte = await OdooUser.login(user('admin_norte'), S.password);
    const adminSur = await OdooUser.login(user('admin_sur'), S.password);
    const nadie = await OdooUser.login(user('sin_acceso'), S.password);
    const [request] = await adminNorte.searchRead('step.app.membership', [['state', '=', 'requested']], ['id', 'person_id', 'request_note']);
    expect(request.request_note).toMatch(/conductor/);
    // Otra empresa no la ve ni la toca; el usuario sin permisos recibe un error de acceso.
    expect(await adminSur.searchRead('step.app.membership', [['id', '=', request.id]], ['id'])).toEqual([]);
    expect((await adminSur.call('step.app.membership', 'write', [[request.id], { state: 'active' }])).error).toBeTruthy();
    expect((await nadie.call('step.app.membership', 'search_read', [[]], { fields: ['id'] })).error).toMatch(/AccessError/);
    // Aprobación guiada: un paso, sin editar registros técnicos.
    const [role] = await adminNorte.searchRead('step.app.module.role', [['code', '=', 'persona'], ['module_id.code', '=', 'colaciones']], ['id']);
    const wizard = await adminNorte.ok<number>('step.app.grant.wizard', 'create', [{ membership_id: request.id, role_ids: [[6, 0, [role.id]]] }]);
    await adminNorte.ok('step.app.grant.wizard', 'action_assign', [[wizard]]);
    const [after] = await adminNorte.searchRead('step.app.membership', [['id', '=', request.id]], ['state']);
    expect(after.state).toBe('active');
    const audit = await adminNorte.searchRead('step.app.audit', [['person_id', '=', (request.person_id as [number])[0]]], ['action']);
    expect(audit.map((a) => a.action)).toEqual(expect.arrayContaining(['grant_created', 'membership_state']));
    // La persona aprobada inicia sesión y ve solo lo asignado.
    const solicita = await signIn('solicita@demo.steps.test');
    expect(solicita.session.getSnapshot().catalog?.modules.map((m) => m.code)).toEqual(['colaciones']);
  });

  it('3-8. Colaciones: el operador registra SIN señal, llega UNA vez al volver, persona y Odoo lo comprueban', async () => {
    const op = await signIn('operador@demo.steps.test');
    expect(op.session.can('colaciones.register')).toBe(true);
    expect(op.session.can('mobilization.drive')).toBe(false);
    const { totems } = await colacionesApi(op.session.api).totems();
    expect(totems.map((t) => t.id)).toEqual([S.companies.norte.totem_ids[0]]); // solo el tótem de su alcance
    const barcode = S.companies.norte.employee_barcodes['1'];

    net.down = true;
    const cap = buildRegistration(totems[0], barcode);
    await op.runtime.enqueue({ module: 'colaciones', kind: 'register', group: colGroup(totems[0].id), payload: cap.payload, id: cap.id });
    // «Doble pulsación»: el mismo UUID no crea otra operación.
    await op.runtime.enqueue({ module: 'colaciones', kind: 'register', group: colGroup(totems[0].id), payload: cap.payload, id: cap.id });
    expect(op.runtime.getSnapshot()).toMatchObject({ pending: 1, rejected: 0 });
    net.down = false;
    await op.runtime.sync();
    expect(op.runtime.getSnapshot().pending).toBe(0);

    const adminNorte = await OdooUser.login(user('admin_norte'), S.password);
    const rows = await adminNorte.searchRead('step.colacion.registration', [['client_uuid', '=', cap.id]], ['employee_id', 'app_operator_id', 'source']);
    expect(rows).toHaveLength(1);
    expect((rows[0].app_operator_id as [number, string])[1]).toBe('Operador Demo');
    // Aislamiento en Odoo: el administrador de la otra empresa no ve este registro.
    const adminSur = await OdooUser.login(user('admin_sur'), S.password);
    expect(await adminSur.searchRead('step.colacion.registration', [['client_uuid', '=', cap.id]], ['id'])).toEqual([]);

    // Reenvío de lo mismo (respuesta perdida): sigue habiendo un solo registro.
    const q = op.runtime.queue()!;
    await q.update({ [cap.id]: { state: 'pending' } });
    await op.runtime.sync();
    expect(await adminNorte.searchRead('step.colacion.registration', [['client_uuid', '=', cap.id]], ['id'])).toHaveLength(1);

    // La beneficiaria comprueba su propio resultado y solo el suyo.
    const benef = await signIn('beneficiaria@demo.steps.test');
    const mine = await colacionesApi(benef.session.api).me();
    expect(mine).toMatchObject({ linked: true, today: { registered: true } });
    await expect(colacionesApi(benef.session.api).totems()).rejects.toMatchObject({ status: 403 });

    // Un beneficiario no habilitado y un código inexistente: rechazos definitivos conservados con su motivo.
    for (const code of [S.companies.norte.employee_barcodes['3'], 'NOEXISTE']) {
      const c = buildRegistration(totems[0], code);
      await op.runtime.enqueue({ module: 'colaciones', kind: 'register', group: colGroup(totems[0].id), payload: c.payload, id: c.id });
    }
    await op.runtime.sync();
    expect(op.runtime.getSnapshot()).toMatchObject({ pending: 0, rejected: 2 });
    expect((await op.runtime.ops('colaciones')).filter((o) => o.state === 'rejected').map((o) => o.error).join(' ')).toMatch(/habilitado/);

    // El operador no alcanza el tótem 2 aunque sea de su empresa (alcance de la concesión).
    const second = S.companies.norte.totem_ids[1];
    const out = await op.session.api.request<{ results: { status: string; message: string }[] }>('POST', '/colaciones/register', { totem_id: second, records: [{ client_uuid: 'fuera-alcance-1', identifier: S.companies.norte.employee_barcodes['2'], event_datetime: new Date().toISOString(), offline: true }] });
    expect(out.results[0]).toMatchObject({ status: 'rejected', message: 'resource_out_of_scope' });
  });

  it('5-8. Movilización: dos conductores con servicios distintos; eventos sin señal, una sola vez y con autoría; el supervisor lo comprueba', async () => {
    const c1 = await signIn('conductor1@demo.steps.test');
    const c2 = await signIn('conductor2@demo.steps.test');
    const api1 = mobilizationApi(c1.session.api), api2 = mobilizationApi(c2.session.api);
    expect((await api1.trips()).trips.map((t) => t.id)).toEqual([S.trips.conductor1]);
    expect((await api2.trips()).trips.map((t) => t.id)).toEqual([S.trips.conductor2]);
    await expect(api2.trip(S.trips.conductor1)).rejects.toMatchObject({ status: 404 }); // ni el detalle ni nada del otro conductor
    const detail = (await api1.trip(S.trips.conductor1)).trip;
    expect(detail).toMatchObject({ state: 'draft' });
    expect((detail as unknown as { stops: { name: string }[] }).stops.map((s) => s.name)).toEqual(['Fundo', 'Cruce', 'Planta']);

    const tripId = S.trips.conductor1, g = tripGroup(tripId);
    net.down = true;
    await c1.runtime.enqueue({ module: 'mobilization', kind: 'trip_open', group: g, payload: { tripId } });
    const marks = ['3', '4'].map((n) => buildEvent({ type: 'boarding', method: 'barcode', identifier: S.companies.norte.employee_barcodes[n] }));
    for (const e of marks) await c1.runtime.enqueue({ module: 'mobilization', kind: 'event', group: g, payload: { tripId, tripName: 'x', event: e, label: 'Subida' } });
    await c1.runtime.enqueue({ module: 'mobilization', kind: 'trip_close', group: g, payload: { tripId } });
    expect(c1.runtime.getSnapshot().pending).toBe(4);
    net.down = false;
    await c1.runtime.sync();
    expect(c1.runtime.getSnapshot()).toMatchObject({ pending: 0, rejected: 0 });

    // Reenvío del lote completo: no duplica.
    const q = c1.runtime.queue()!;
    await q.update(Object.fromEntries((await q.list()).filter((o) => o.kind === 'event').map((o) => [o.id, { state: 'pending' as const }])));
    await c1.runtime.sync();

    const sup = await signIn('supervisor@demo.steps.test');
    const { trips } = await mobilizationApi(sup.session.api).supervisorTrips();
    const t = trips.find((x) => x.id === tripId)!;
    expect(t).toMatchObject({ state: 'closed', boarded_count: 2, driver: 'Chofer Uno Demo' });
    expect(t.events).toHaveLength(2);
    expect(t.events!.every((e) => e.by === 'Conductor Uno')).toBe(true);
    // El supervisor no conduce, y el conductor no supervisa.
    await expect(mobilizationApi(sup.session.api).trips()).rejects.toMatchObject({ status: 403 });
    await expect(mobilizationApi(c1.session.api).supervisorTrips()).rejects.toMatchObject({ status: 403 });
    // En Odoo hay exactamente 2 eventos, ambos con la persona autora.
    const admin = await OdooUser.login(user('admin_norte'), S.password);
    const events = await admin.searchRead('step.mobilization.passenger.event', [['trip_id', '=', tripId]], ['app_person_id', 'state']);
    expect(events).toHaveLength(2);
    expect(new Set(events.map((e) => (e.app_person_id as [number, string])[1]))).toEqual(new Set(['Conductor Uno']));
  });

  it('9. Revocar un acceso cambia las autorizaciones reales; lo capturado antes se acepta y lo posterior no', async () => {
    const op = await signIn('operador@demo.steps.test');
    const totem = { id: S.companies.norte.totem_ids[0], name: 'Casino norte 1' };
    net.down = true;
    const before = buildRegistration(totem, S.companies.norte.employee_barcodes['2']); // capturada antes de la revocación
    await op.runtime.enqueue({ module: 'colaciones', kind: 'register', group: colGroup(totem.id), payload: before.payload, id: before.id });
    await new Promise((r) => setTimeout(r, 1500));
    const admin = await OdooUser.login(user('admin_norte'), S.password);
    const [m] = await admin.searchRead('step.app.membership', [['person_id.email', '=', 'operador@demo.steps.test']], ['id']);
    const grants = await admin.searchRead('step.app.grant', [['membership_id', '=', m.id as number], ['revoked_at', '=', false]], ['id']);
    await admin.ok('step.app.grant', 'action_revoke', [grants.map((g) => g.id as number)]);
    await new Promise((r) => setTimeout(r, 1500));
    const after = buildRegistration(totem, S.companies.norte.employee_barcodes['4']); // capturada DESPUÉS de revocar
    await op.runtime.enqueue({ module: 'colaciones', kind: 'register', group: colGroup(totem.id), payload: after.payload, id: after.id });
    net.down = false;
    await op.runtime.sync();
    const states = Object.fromEntries((await op.runtime.ops('colaciones')).map((o) => [o.id, o]));
    expect(states[before.id].state).toBe('confirmed');
    expect(states[after.id]).toMatchObject({ state: 'rejected' });
    expect(states[after.id].error).toMatch(/grant_not_valid_at_capture|no_grant/);
    // Online: el teléfono deja de ver el módulo y la API lo niega.
    await op.session.revalidate();
    expect(op.session.can('colaciones.register')).toBe(false);
    expect(op.session.getSnapshot().catalog?.modules.map((x) => x.code) ?? []).not.toContain('colaciones');
    // Suspender la membresía entera corta incluso la consulta en línea.
    await admin.ok('step.app.membership', 'action_suspend', [[m.id as number]]);
    await op.session.revalidate();
    expect(op.session.getSnapshot().orgUid).toBeNull();
    await expect(op.session.api.request('GET', '/colaciones/totems')).rejects.toMatchObject({ code: 'organization_required' });
  });

  it('10. Cambiar de cuenta o de empresa no mezcla ni elimina pendientes', async () => {
    // Misma persona en dos empresas: cada empresa tiene su cola.
    const kv = memoryKv();
    const multi = await signIn('multi@demo.steps.test', kv);
    expect(multi.session.getSnapshot().needsOrgChoice).toBe(true);
    await multi.session.selectOrg(S.companies.sur.org_uid);
    expect(multi.session.getSnapshot().catalog?.modules.map((m) => m.code)).toEqual(['mobilization']);
    const tripId = S.trips.multi_sur;
    net.down = true;
    await multi.runtime.enqueue({ module: 'mobilization', kind: 'trip_open', group: tripGroup(tripId), payload: { tripId } });
    await multi.session.selectOrg(S.companies.norte.org_uid).catch(() => undefined); // sin red: no puede validar
    net.down = false;
    await multi.session.selectOrg(S.companies.norte.org_uid);
    expect(multi.session.getSnapshot().catalog?.modules.map((m) => m.code).sort()).toEqual(['colaciones', 'tracker']);
    expect(await multi.runtime.ops('mobilization')).toEqual([]); // la cola de Sur no se mezcla con Norte
    await multi.session.selectOrg(S.companies.sur.org_uid);
    expect((await multi.runtime.ops('mobilization'))).toHaveLength(1); // sigue guardada en su empresa (puede haber salido ya al volver la señal)
    await multi.runtime.sync();
    expect((await multi.runtime.ops('mobilization'))[0].state).toBe('confirmed');
    // Segunda cuenta en el MISMO teléfono: no ve ni envía lo ajeno.
    net.down = true;
    const tripN = S.trips.conductor2;
    const c2 = await (async () => { net.down = false; const p = await signIn('conductor2@demo.steps.test', kv); net.down = true; return p; })();
    await c2.runtime.enqueue({ module: 'mobilization', kind: 'trip_open', group: tripGroup(tripN), payload: { tripId: tripN } });
    await c2.session.logout(); // se cierra la sesión con el teléfono todavía sin señal
    net.down = false;
    const again = await signIn('conductor1@demo.steps.test', kv);
    expect(again.runtime.getSnapshot().foreign.length).toBeGreaterThan(0);
    await again.runtime.sync();
    const admin = await OdooUser.login(user('admin_norte'), S.password);
    const [t2] = await admin.searchRead('step.movi.registry', [['id', '=', tripN]], ['state']);
    expect(t2.state).toBe('draft'); // no se abrió con la sesión equivocada
    const back = await signIn('conductor2@demo.steps.test', kv);
    await back.runtime.sync();
    const [t2b] = await admin.searchRead('step.movi.registry', [['id', '=', tripN]], ['state']);
    expect(t2b.state).toBe('open'); // al volver su dueño, se envía
  });

  it('Recuperación de acceso y dispositivo perdido', async () => {
    const lost = await signIn('beneficiaria@demo.steps.test');
    const other = await signIn('beneficiaria@demo.steps.test');
    const sys = await OdooUser.login('admin', process.env.STEPS_E2E_ADMIN_PASSWORD ?? 'admin');
    const [identity] = await sys.searchRead('step.app.identity', [['subject', '=', 'beneficiaria@demo.steps.test']], ['id']);
    const notice = await sys.ok<{ params: { message: string } }>('step.app.identity', 'action_issue_recovery_code', [[identity.id as number]]);
    const code = notice.params.message.split(': ').pop()!.trim();
    const r = await fetch(`${API}/auth/recover/confirm`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: 'beneficiaria@demo.steps.test', code, password: S.password + '-nueva' }) });
    expect((await r.json()).ok).toBe(true);
    for (const p of [lost, other]) await expect(p.session.api.devices()).rejects.toMatchObject({ status: 401 });
    const p = phone(); await p.session.boot();
    await p.session.login('beneficiaria@demo.steps.test', S.password + '-nueva');
    expect(p.session.getSnapshot().status).toBe('signed_in');
    const reuse = await fetch(`${API}/auth/recover/confirm`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: 'beneficiaria@demo.steps.test', code, password: 'otra-clave-larga-1' }) });
    expect((await reuse.json()).error).toBe('invalid_recovery');
  });
});
