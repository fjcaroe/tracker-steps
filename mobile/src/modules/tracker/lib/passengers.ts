import { api, API_BASE, ApiError, tokenStore, type PassengerService } from './api';

export type PassengerState = 'pending' | 'boarded' | 'alighted' | 'no_show';
export type BoardingEvent = { id: string; passenger_id: string; kind: Exclude<PassengerState, 'pending'>;
  expected_version: number; occurred_at: string; lat: number | null; lon: number | null; accuracy_m: number | null };
export type Manifest = Omit<PassengerService, 'passengers'> & { manifest_version: number; occupied: number;
  passengers: (PassengerService['passengers'][number] & { state: PassengerState })[];
  events: { id: string; passenger_id: string; kind: BoardingEvent['kind']; occurred_at: string }[] };
export type Workspace = { serviceId: string; base: Manifest | null; expiresAt: number; queue: BoardingEvent[] };
type Account = Record<string, Workspace>;
const TTL = 24 * 3600_000;
const scope = (userId: number) => `${API_BASE}|${userId}`;

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('steps-passengers-i10', 1);
    request.onupgradeneeded = () => request.result.createObjectStore('accounts');
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(new Error('No se puede guardar en este teléfono. No se registró el cambio.'));
  });
}

/** One record per API/account. IDB read/write transactions serialize tabs. */
async function transaction<T>(userId: number, change: (account: Account) => T): Promise<T> {
  const db = await open();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('accounts', 'readwrite');
    const store = tx.objectStore('accounts');
    const request = store.get(scope(userId));
    let result: T;
    let cause: unknown;
    request.onsuccess = () => {
      try {
        const account = (request.result ?? {}) as Account;
        for (const row of Object.values(account)) if (row.expiresAt <= Date.now()) row.base = null;
        result = change(account);
        store.put(account, scope(userId));
      } catch (error) { cause = error; tx.abort(); }
    };
    tx.oncomplete = () => { db.close(); resolve(result); };
    tx.onabort = tx.onerror = () => { db.close(); reject(cause ?? new Error('No se pudo guardar. El cambio no quedó registrado.')); };
  });
}

export function project(row: Workspace): Manifest | null {
  if (!row.base || row.expiresAt <= Date.now()) return null;
  const base = structuredClone(row.base);
  const received = new Set(base.events.map((e) => e.id));
  for (const event of row.queue) {
    if (received.has(event.id)) continue;
    const passenger = base.passengers.find((p) => p.id === event.passenger_id);
    if (passenger) passenger.state = event.kind;
    base.manifest_version++;
  }
  base.occupied = base.passengers.filter((p) => p.state === 'boarded').length;
  return base;
}

export const passengerStore = {
  read: (userId: number) => transaction(userId, (account) => structuredClone(Object.values(account))),
  prepare: (userId: number, manifest: Manifest) => transaction(userId, (account) => {
    const old = account[manifest.id];
    if (old?.queue.length) throw new Error('Sincroniza los pendientes antes de preparar de nuevo.');
    account[manifest.id] = { serviceId: manifest.id, base: manifest, expiresAt: Date.now() + TTL, queue: [] };
  }),
  forget: (userId: number, serviceId?: string) => transaction(userId, (account) => {
    for (const row of Object.values(account)) if (!serviceId || row.serviceId === serviceId) row.base = null;
  }),
  reconcile: (userId: number, manifest: Manifest) => transaction(userId, (account) => {
    const row = account[manifest.id]; if (!row) return;
    const receipts = new Set(manifest.events.map((e) => e.id));
    const remaining = row.queue.filter((e) => !receipts.has(e.id));
    const states = new Map(manifest.passengers.map((p) => [p.id, p.state]));
    for (const [index, event] of remaining.entries()) {
      const old = states.get(event.passenger_id);
      const valid = event.kind === 'boarded' ? old === 'pending' || old === 'no_show' : event.kind === 'alighted' ? old === 'boarded' : old === 'pending';
      if (!valid) throw new Error('Un pendiente contradice el manifiesto confirmado. Conservamos la cola; solicita revisión del supervisor.');
      const passenger = manifest.passengers.find((p) => p.id === event.passenger_id)!;
      if (event.kind === 'boarded' && (Array.from(states.values()).filter((s) => s === 'boarded').length >= manifest.capacity ||
        (passenger.seat != null && manifest.passengers.some((p) => states.get(p.id) === 'boarded' && p.seat === passenger.seat)))) {
        throw new Error('Un pendiente supera la capacidad o usa un asiento ocupado. Conservamos la cola para revisión.');
      }
      event.expected_version = manifest.manifest_version + index;
      states.set(event.passenger_id, event.kind);
    }
    row.queue = remaining; row.base = manifest; row.expiresAt = Date.now() + TTL;
  }),
  enqueue: (userId: number, serviceId: string, passengerId: string, kind: BoardingEvent['kind'],
    location: { lat: number; lon: number; accuracy_m: number } | null = null) => transaction(userId, (account) => {
    const row = account[serviceId]; const manifest = row && project(row);
    if (!manifest) throw new Error('Prepara el servicio con señal antes de registrar pasajeros.');
    if (manifest.route_status === 'cancelled') throw new Error('La ruta está cancelada. Consulta al supervisor.');
    const passenger = manifest.passengers.find((p) => p.id === passengerId);
    if (!passenger) throw new Error('El código no corresponde a este servicio.');
    if ((kind === 'boarded' && !['pending', 'no_show'].includes(passenger.state)) ||
      (kind === 'alighted' && passenger.state !== 'boarded') || (kind === 'no_show' && passenger.state !== 'pending')) {
      throw new Error('La acción no corresponde al estado actual del pasajero.');
    }
    if (kind === 'boarded' && manifest.occupied >= manifest.capacity) throw new Error('Capacidad completa. Registra primero los descensos.');
    if (kind === 'boarded' && passenger.seat != null && manifest.passengers.some((p) => p.state === 'boarded' && p.seat === passenger.seat)) throw new Error('El asiento aún está ocupado. Registra primero el descenso.');
    if (row.queue.length >= 5000) throw new Error('Hay demasiados pendientes. Sincroniza antes de continuar.');
    row.queue.push({ id: crypto.randomUUID(), passenger_id: passengerId, kind, expected_version: manifest.manifest_version,
      occurred_at: new Date().toISOString(), lat: location?.lat ?? null, lon: location?.lon ?? null, accuracy_m: location?.accuracy_m ?? null });
  }),
};

const syncing = new Map<string, Promise<void>>();
export function syncPassengers(userId: number): Promise<void> {
  const key = scope(userId); const active = syncing.get(key); if (active) return active;
  const token = tokenStore.get();
  const task = (async () => {
    for (const row of await passengerStore.read(userId)) {
      for (;;) {
        const latest = (await passengerStore.read(userId)).find((r) => r.serviceId === row.serviceId);
        const head = latest?.queue[0]; if (!head) break;
        if (tokenStore.get() !== token) throw new ApiError('La sesión cambió. Los pendientes conservan su cuenta original.', 401);
        let manifest: Manifest;
        try {
          manifest = await api<Manifest>(`/mobile/services/${row.serviceId}/events`, { method: 'POST', cache: 'no-store', body: JSON.stringify(head) });
        } catch (cause) {
          if (cause instanceof ApiError && [401, 403, 404].includes(cause.status)) await passengerStore.forget(userId, row.serviceId);
          throw cause;
        }
        await transaction(userId, (account) => {
          const record = account[row.serviceId]; if (!record) return;
          const receipts = new Set(manifest.events.map((e) => e.id));
          if (!receipts.has(head.id)) throw new Error('El servidor no confirmó el evento. Los pendientes se conservan.');
          record.queue = record.queue.filter((e) => !receipts.has(e.id));
          // Logout/expiry must not resurrect personal information after an in-flight request.
          if (record.base && record.expiresAt > Date.now() && manifest.manifest_version >= record.base.manifest_version) record.base = manifest;
        });
      }
    }
  })().finally(() => { syncing.delete(key); });
  syncing.set(key, task); return task;
}

/** Codes contain only the immutable manifest passenger UUID, never a RUT. */
export function findPassenger(manifest: Manifest, text: string): string | null {
  const value = text.trim().replace(/^steps:passenger:/i, '');
  return manifest.passengers.find((p) => p.id === value)?.id ?? null;
}
