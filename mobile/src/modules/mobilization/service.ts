// Movilización: el conductor opera con su sesión personal; la autoría de cada evento es la persona, no un dispositivo compartido.
import type { Api } from '../../app/api';
import { ApiError } from '../../app/api';
import type { EventResult, PassengerEvent, Trip } from '../../shared/contracts';
import type { Handler, Outcome } from '../../sync/engine';
import { uuid } from '../../sync/queue';

export const MODULE = 'mobilization';
export const groupFor = (tripId: number) => `mobilization:trip:${tripId}`;
export type TripPayload = { tripId: number };
export type EventPayload = { tripId: number; tripName: string; event: PassengerEvent; label: string };

export const mobilizationApi = (api: Api) => ({
  trips: () => api.request<{ ok: true; trips: Trip[] }>('GET', '/mobilization/trips'),
  trip: (id: number) => api.request<{ ok: true; trip: Trip }>('GET', `/mobilization/trips/${id}`),
  searchPassengers: (q: string) => api.request<{ ok: true; passengers: { id: number; name: string }[] }>('GET', `/mobilization/passengers?q=${encodeURIComponent(q)}`),
  supervisorTrips: () => api.request<{ ok: true; date: string; trips: Trip[] }>('GET', '/mobilization/supervisor/trips'),
});

export function buildEvent(input: { type: 'boarding' | 'alighting'; method: PassengerEvent['method']; identifier?: string; passengerId?: number; position?: { lat: number; lon: number; accuracy: number } | null }, now = new Date()): PassengerEvent {
  return {
    idempotency_key: uuid(), method: input.method, identifier: input.identifier?.trim() || undefined, passenger_id: input.passengerId,
    event_type: input.type, device_datetime: now.toISOString(),
    ...(input.position ? { latitude: input.position.lat, longitude: input.position.lon, accuracy: input.position.accuracy, location_source: 'gps' as const } : {}),
  };
}

const BUSINESS_CODES = ['cannot_open', 'invalid_state', 'trip_not_found'];

/** Un código de negocio conocido es un rechazo definitivo de ESTA operación; cualquier otro error se reintenta o pide acceso. */
function business(e: unknown): Outcome | null {
  return e instanceof ApiError && BUSINESS_CODES.includes(e.code) ? { status: 'rejected', code: e.code, message: e.message } : null;
}

export const mobilizationHandlers = (api: Api): Record<string, Handler> => ({
  'mobilization:trip_open': {
    async send(ops): Promise<Outcome[]> {
      try { await api.request('POST', `/mobilization/trips/${(ops[0].payload as TripPayload).tripId}/open`, {}); return [{ status: 'confirmed' }]; }
      catch (e) { const o = business(e); if (o) return [o]; throw e; }
    },
  },
  'mobilization:trip_close': {
    async send(ops): Promise<Outcome[]> {
      try { await api.request('POST', `/mobilization/trips/${(ops[0].payload as TripPayload).tripId}/close`, {}); return [{ status: 'confirmed' }]; }
      catch (e) { const o = business(e); if (o) return [o]; throw e; }
    },
  },
  'mobilization:event': {
    batch: 100,
    // Minimización: tras confirmar no se conserva el identificador del pasajero en el teléfono.
    redact: (op) => { const p = op.payload as EventPayload; return { ...p, event: { ...p.event, identifier: undefined } }; },
    async send(ops): Promise<Outcome[]> {
      const tripId = (ops[0].payload as EventPayload).tripId;
      let response: { results: EventResult[] };
      try { response = await api.request<{ ok: true; results: EventResult[] }>('POST', `/mobilization/trips/${tripId}/events`, { events: ops.map((o) => (o.payload as EventPayload).event) }); }
      catch (e) { if (e instanceof ApiError && e.code === 'trip_not_found') return ops.map(() => ({ status: 'rejected' as const, code: e.code, message: 'Este servicio ya no está asignado a ti.' })); throw e; }
      return ops.map((op, i): Outcome => {
        const key = (op.payload as EventPayload).event.idempotency_key;
        const r = response.results.find((x) => x.idempotency_key === key) ?? response.results[i];
        if (!r) return { status: 'retry', code: 'server' };
        if (r.status === 'created' || r.status === 'duplicate') return { status: 'confirmed', result: { duplicate: r.status === 'duplicate' } };
        if (r.status === 'rejected') return { status: 'rejected', code: 'rejected', message: r.message };
        return { status: 'retry', code: 'server', message: r.message };
      });
    },
  },
});

export function rejectionText(message?: string): string {
  const known: Record<string, string> = {
    passenger_not_authorized: 'Ese pasajero no está autorizado en esta empresa.',
    trip_not_open: 'El servicio ya estaba cerrado cuando llegó la marca.',
    grant_not_valid_at_capture: 'Tu acceso como conductor no estaba vigente cuando se hizo la marca.',
    access_ended_before_capture: 'Tu acceso a la empresa ya había terminado cuando se hizo la marca.',
    device_clock_ahead: 'La hora del teléfono está adelantada. Corrígela.',
    invalid_event: 'La marca no es válida.',
    cannot_open: 'No se pudo iniciar el servicio.',
  };
  return (message && known[message]) || message || 'El servidor rechazó esta operación.';
}
