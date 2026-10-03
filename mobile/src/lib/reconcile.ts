// Reconciliación entre la jornada guardada en el teléfono y lo que dice el servidor.
import type { SessionSummary } from './api';
import type { Active } from './queue';

export type Reconcile =
  | { kind: 'keep' }
  | { kind: 'clear'; reason: 'closed' }
  | { kind: 'adopt'; session: SessionSummary };

/** `open` son las sesiones abiertas del usuario según el servidor. */
export function reconcile(local: Active | null, open: SessionSummary[]): Reconcile {
  if (local) return open.some((s) => s.id === local.sessionId) ? { kind: 'keep' } : { kind: 'clear', reason: 'closed' };
  const latest = [...open].sort((a, b) => Date.parse(b.started_at) - Date.parse(a.started_at))[0];
  return latest ? { kind: 'adopt', session: latest } : { kind: 'keep' };
}

/** Texto "hace 3 min" para el indicador de último envío. */
export function sinceText(ts: number | null, now = Date.now()): string {
  if (ts == null) return 'sin envíos aún';
  const s = Math.max(0, Math.floor((now - ts) / 1000));
  if (s < 60) return 'hace instantes';
  if (s < 3600) return `hace ${Math.floor(s / 60)} min`;
  return `hace ${Math.floor(s / 3600)} h`;
}
