// Colaciones: dos experiencias con permisos distintos. El token del tótem NO se usa aquí: la persona opera con su sesión.
import type { Api } from '../../app/api';
import { ApiError } from '../../app/api';
import type { ColacionRecord, ColacionResult, ColacionesMe, Totem } from '../../shared/contracts';
import type { Handler, Outcome } from '../../sync/engine';
import { uuid, type QueueOp } from '../../sync/queue';

export const MODULE = 'colaciones';
export type RegisterPayload = { totemId: number; totemName: string; record: ColacionRecord };

export const colacionesApi = (api: Api) => ({
  me: () => api.request<ColacionesMe>('GET', '/colaciones/me'),
  totems: () => api.request<{ ok: true; totems: Totem[]; max_batch_records: number }>('GET', '/colaciones/totems'),
});

/** Captura inmutable: el UUID nace aquí y es la clave de idempotencia de punta a punta. */
export function buildRegistration(totem: Pick<Totem, 'id' | 'name'>, identifier: string, now = new Date()): { id: string; payload: RegisterPayload } {
  const id = uuid();
  return { id, payload: { totemId: totem.id, totemName: totem.name, record: { client_uuid: id, identifier: identifier.trim(), event_datetime: now.toISOString(), offline: true } } };
}

export const groupFor = (totemId: number) => `colaciones:totem:${totemId}`;

export const colacionesHandlers = (api: Api): Record<string, Handler> => ({
  'colaciones:register': {
    batch: 50,
    // Minimización de datos: una vez confirmada, el identificador del trabajador no se conserva en el teléfono.
    redact: (op: QueueOp) => ({ ...(op.payload as RegisterPayload), record: { ...(op.payload as RegisterPayload).record, identifier: '' } }),
    async send(ops): Promise<Outcome[]> {
      const totemId = (ops[0].payload as RegisterPayload).totemId;
      let response: { results: ColacionResult[] };
      try {
        response = await api.request<{ ok: true; results: ColacionResult[] }>('POST', '/colaciones/register', { totem_id: totemId, records: ops.map((o) => (o.payload as RegisterPayload).record) });
      } catch (e) {
        // El tótem ya no está autorizado/existe: es una decisión del servidor sobre ESTE destino, se conserva para revisión (no se descarta).
        if (e instanceof ApiError && e.code === 'totem_not_authorized') return ops.map(() => ({ status: 'auth_required', code: e.code, message: e.message }));
        throw e;
      }
      return ops.map((op, i): Outcome => {
        const r = response.results.find((x) => x.client_uuid === op.id) ?? response.results[i];
        if (!r) return { status: 'retry', code: 'server', message: 'Sin resultado para esta captura.' };
        if (r.status === 'registered') return { status: 'confirmed', result: { registration: r.registration, employee: r.employee, duplicate: false } };
        if (r.status === 'duplicate') return { status: 'confirmed', result: { registration: r.registration, employee: r.employee, duplicate: true } };
        if (r.status === 'rejected') return { status: 'rejected', code: 'rejected', message: r.message ?? 'El servidor rechazó esta captura.' };
        return { status: 'retry', code: 'server', message: r.message ?? undefined };
      });
    },
  },
});

/** Texto en lenguaje de negocio para el motivo de rechazo del servidor. */
export function rejectionText(message?: string): string {
  const known: Record<string, string> = {
    grant_not_valid_at_capture: 'Tu acceso como operador no estaba vigente cuando se hizo esta captura.',
    access_ended_before_capture: 'Tu acceso a la empresa ya había terminado cuando se hizo esta captura.',
    resource_out_of_scope: 'No tienes autorizado este tótem.',
    no_grant: 'No tienes autorizado registrar colaciones.',
    invalid_event_datetime: 'La hora del teléfono no es válida.',
  };
  return (message && known[message]) || message || 'El servidor rechazó esta captura.';
}
