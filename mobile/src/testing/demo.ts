// Modo demostración: la app completa contra el servidor FALSO del contrato, con datos ficticios. Es para trabajo visual y capturas
// (`npm run demo`); no existe en las compilaciones normales (el código se elimina en build). NUNCA habla con un servidor real.
import { memoryKv, type KeyValueStore } from '../shared/storage';
import { buildRegistration, groupFor } from '../modules/colaciones/service';
import { FakeSteps } from './fakeServer';

export const DEMO_PASSWORD = 'demo-clave-2026';
export type ScenarioName = 'nuevo' | 'conductor' | 'beneficiaria' | 'pendientes' | 'multiempresa' | 'supervisor' | 'sin-modulos';
export type Scenario = { server: FakeSteps; kv: KeyValueStore; email: string; title: string; seed: () => Promise<void> };

export const SCENARIOS: Record<ScenarioName, string> = {
  nuevo: 'Usuario nuevo (sin empresa): se registra y ve la incorporación',
  conductor: 'Conductor con un servicio asignado',
  beneficiaria: 'Beneficiaria de Colaciones con historial',
  pendientes: 'Operador con operaciones pendientes y una rechazada',
  multiempresa: 'Persona con varias empresas y módulos (incluye Tracker)',
  supervisor: 'Supervisor de Movilización con un servicio en curso',
  'sin-modulos': 'Persona con empresa activa pero sin módulos asignados',
};

export function scenario(name: ScenarioName): Scenario {
  const server = new FakeSteps();
  const kv = memoryKv();
  let seed = async () => undefined as void;
  let email = `${name}@demo.steps.test`;
  switch (name) {
    case 'nuevo': break; // no existe: se crea desde «Crear cuenta»
    case 'conductor': { const p = server.addPerson(email, DEMO_PASSWORD, 'Conductor Demo'); server.grant(p.id, 'org-a', ['mobilization', 'conductor']); server.addTrip('org-a', p.id); break; }
    case 'beneficiaria': {
      const p = server.addPerson(email, DEMO_PASSWORD, 'Beneficiaria Demo'); server.grant(p.id, 'org-a', ['colaciones', 'persona']).employee = 1;
      for (let d = 0; d < 6; d++) server.registrations.set(`hist-${d}`, { employee: 'E1', orgUid: 'org-a', operator: 0, day: new Date(server.now - d * 86_400_000).toISOString().slice(0, 10), code: `COL/${100 + d}` });
      break;
    }
    case 'pendientes': {
      const p = server.addPerson(email, DEMO_PASSWORD, 'Operador Demo'); server.grant(p.id, 'org-a', ['colaciones', 'operador']);
      seed = async () => { // se ejecuta tras iniciar sesión: deja operaciones pendientes y una rechazada en la cola del teléfono
        const { DurableQueue } = await import('../sync/queue');
        const q = new DurableQueue(kv, { personId: p.id, orgUid: 'org-a' });
        for (const code of ['BR0001', 'BR0002']) { const c = buildRegistration({ id: 1, name: 'Casino 1' }, code); await q.enqueue({ module: 'colaciones', kind: 'register', group: groupFor(1), payload: c.payload, id: c.id }); }
        const bad = buildRegistration({ id: 1, name: 'Casino 1' }, 'BR0003'); const op = await q.enqueue({ module: 'colaciones', kind: 'register', group: groupFor(1), payload: bad.payload, id: bad.id });
        await q.update({ [op.id]: { state: 'rejected', code: 'rejected', error: 'El trabajador no está habilitado para recibir colación.', settledAt: new Date().toISOString() } });
        server.offline = true; // el teléfono parte sin señal para que lo pendiente se vea
      };
      break;
    }
    case 'multiempresa': { const p = server.addPerson(email, DEMO_PASSWORD, 'Persona Multi'); server.grant(p.id, 'org-a', ['colaciones', 'persona'], ['tracker', 'operador']).employee = 2; server.grant(p.id, 'org-b', ['mobilization', 'conductor']); server.addTrip('org-b', p.id); break; }
    case 'supervisor': {
      const s = server.addPerson(email, DEMO_PASSWORD, 'Supervisor Demo'); server.grant(s.id, 'org-a', ['mobilization', 'supervisor']);
      const d = server.addPerson('conductor-s@demo.steps.test', DEMO_PASSWORD, 'Conductor Uno'); server.grant(d.id, 'org-a', ['mobilization', 'conductor']);
      const t = server.addTrip('org-a', d.id, 'open'); server.events.set(`${t.id}:k1`, { tripId: t.id, passenger: 'Pasajero Cuatro', type: 'boarding', by: d.id });
      break;
    }
    case 'sin-modulos': { const p = server.addPerson(email, DEMO_PASSWORD, 'Persona Sin Módulos'); server.grant(p.id, 'org-a'); break; }
  }
  return { server, kv, email, title: SCENARIOS[name], seed };
}
