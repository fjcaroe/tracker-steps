// Reconciliación entre la jornada guardada en el teléfono y lo que dice el servidor (puro, probado).
import type { Machine, SessionSummary, WorkOrderSummary } from './api';
import type { Active } from './queue';

export type Reconciled =
  | { kind: 'keep' }
  | { kind: 'closed' }
  | { kind: 'choose'; candidates: SessionSummary[] };

/** Decide qué hacer con la jornada local según las jornadas que el servidor conoce. */
export function reconcile(local: Active | null, remote: SessionSummary[]): Reconciled {
  if (local) {
    const found = remote.find((s) => s.id === local.sessionId);
    // Si el servidor no la lista (fuera de alcance o histórico antiguo) no se descarta: no perder datos.
    return found && found.status === 'closed' ? { kind: 'closed' } : { kind: 'keep' };
  }
  const open = remote.filter((s) => s.status === 'open');
  return open.length ? { kind: 'choose', candidates: open } : { kind: 'keep' };
}

/** Reconstruye la jornada activa de un teléfono nuevo a partir de datos del servidor. */
export function buildActive(s: SessionSummary, wo: WorkOrderSummary | null, machine: Machine | null): Active {
  return {
    sessionId: s.id,
    workOrderId: s.work_order_id ?? wo?.id ?? 0,
    machineId: s.machine_id,
    machineName: s.machine_name ?? machine?.name ?? `Máquina ${s.machine_id}`,
    startedAt: new Date(s.started_at).getTime(),
    hourmeterStart: wo?.hourmeter_initial ?? 0,
    tankStart: wo?.fuel_tank_start_liters ?? 0,
    tankCapacity: machine?.tank_capacity_liters ?? null,
    distanceM: Number(s.total_distance_m ?? 0),
  };
}
