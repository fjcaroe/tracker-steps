// Arrendamiento de envío: evita que dos pestañas/procesos de la misma instalación envíen la misma cola a la vez.
// No es una cerradura atómica entre procesos (el almacenamiento no la ofrece): reduce la ventana de doble envío y la idempotencia
// del servidor (UUID por operación) garantiza que, aun así, el resultado sea una sola operación.
import type { KeyValueStore } from '../shared/storage';

const KEY = 'steps.sync.lease.v1';
const TTL_MS = 60_000;

export async function acquireLease(kv: KeyValueStore, owner: string, now = Date.now()): Promise<boolean> {
  try {
    const raw = await kv.get(KEY);
    if (raw) {
      const held = JSON.parse(raw) as { owner: string; until: number };
      if (held.owner !== owner && held.until > now) return false;
    }
    await kv.set(KEY, JSON.stringify({ owner, until: now + TTL_MS }));
  } catch { /* sin almacenamiento: se envía igualmente; el servidor es idempotente */ }
  return true;
}

export async function releaseLease(kv: KeyValueStore, owner: string): Promise<void> {
  try {
    const raw = await kv.get(KEY);
    if (raw && (JSON.parse(raw) as { owner: string }).owner === owner) await kv.remove(KEY);
  } catch { /* nada */ }
}
