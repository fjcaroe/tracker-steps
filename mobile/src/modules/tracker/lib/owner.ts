// Propietario de los datos locales del Tracker. Las claves antiguas (`steps_movil_*`) no identifican a quién pertenecen:
// nunca se atribuyen automáticamente a quien inicie sesión. Sin dueño conocido se pide confirmación; con dueño distinto no se envían.
import { activeStore, pointQueue } from './queue';
import { outboxStore, pendingTotal } from './sync';

const OWNER_KEY = 'steps_movil_owner';
export type Owner = { userId: number; name: string };
export type OwnerState = { kind: 'ok' } | { kind: 'claim' } | { kind: 'foreign'; owner: Owner };

function read(): Owner | null { try { const raw = localStorage.getItem(OWNER_KEY); return raw ? (JSON.parse(raw) as Owner) : null; } catch { return null; } }
function write(owner: Owner): boolean { try { localStorage.setItem(OWNER_KEY, JSON.stringify(owner)); return localStorage.getItem(OWNER_KEY) === JSON.stringify(owner); } catch { return false; } }

export const ownerStore = { get: read, set: write };

/** ¿Hay en este teléfono algo del Tracker que aún no llegó al servidor o que se conserva para soporte? */
export function hasLocalData(): boolean {
  return pendingTotal() > 0 || activeStore.get() != null || pointQueue.rejectedTotal() > 0 || outboxStore.ops().length > 0;
}

export function ownerState(user: { id: number; full_name: string }): OwnerState {
  const owner = read();
  if (!hasLocalData()) { write({ userId: user.id, name: user.full_name }); return { kind: 'ok' }; }
  if (!owner) return { kind: 'claim' };
  return owner.userId === user.id ? { kind: 'ok' } : { kind: 'foreign', owner };
}

/** La persona confirma que los datos sin dueño conocido son suyos. */
export function claimLocalData(user: { id: number; full_name: string }): boolean { return write({ userId: user.id, name: user.full_name }); }

/** Copia de todo lo del Tracker guardado en el teléfono (sin credenciales) para entregar a soporte o recuperar. */
export function exportLocalData(): string {
  const data: Record<string, unknown> = {};
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (!key || !key.startsWith('steps_movil_') || key === 'steps_movil_token') continue;
      const raw = localStorage.getItem(key);
      try { data[key] = raw ? JSON.parse(raw) : null; } catch { data[key] = raw; }
    }
  } catch { /* sin almacenamiento */ }
  return JSON.stringify({ exportedAt: new Date().toISOString(), data }, null, 2);
}
