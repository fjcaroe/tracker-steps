// Reconcilia la jornada guardada en el teléfono con las jornadas abiertas en el servidor.
import type { SessionSummary, WorkOrderFull, Machine } from './api';
import type { Active } from './queue';

export type Reconciliation =
  | { action: 'keep' }                              // la jornada local sigue abierta en el servidor
  | { action: 'clear' }                             // el servidor ya la cerró: limpiar y avisar
  | { action: 'offer'; sessions: SessionSummary[] } // no hay jornada local: ofrecer retomar las abiertas
  | { action: 'none' };

export function reconcile(local: Active | null, open: SessionSummary[]): Reconciliation {
  if (local) return open.some((s) => s.id === local.sessionId) ? { action: 'keep' } : { action: 'clear' };
  return open.length ? { action: 'offer', sessions: open } : { action: 'none' };
}

/** Reconstruye la jornada activa local a partir de lo que guarda el servidor (el reloj conserva el tiempo real). */
export function activeFromServer(s: SessionSummary, wo: WorkOrderFull | undefined, machine: Machine | undefined): Active | null {
  if (!wo || wo.hourmeter_initial == null || wo.fuel_tank_start_liters == null) return null;
  return {
    sessionId: s.id, workOrderId: wo.id, machineId: s.machine_id, machineName: s.machine_name ?? machine?.name ?? `Máquina ${s.machine_id}`,
    startedAt: new Date(s.started_at).getTime(), hourmeterStart: wo.hourmeter_initial, tankStart: wo.fuel_tank_start_liters,
    tankCapacity: machine?.tank_capacity_liters ?? null, distanceM: 0,
  };
}
