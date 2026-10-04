// Política de autorización sin conexión (ADR-5). Pura y probada.
export type AccessMode = 'online' | 'offline_valid' | 'offline_expired';

/**
 * - En línea y validado: permisos al día.
 * - Sin conexión dentro del plazo (`offline_until`): se puede operar con los permisos de la última validación.
 * - Sin conexión vencido el plazo: se bloquean ACCIONES NUEVAS protegidas; la cola existente se conserva.
 * Compromiso documentado: una revocación remota no llega a un teléfono sin conexión hasta que vuelva a validar.
 */
export function accessMode(input: { validatedOnline: boolean; offlineUntil: string | null; now: number }): AccessMode {
  if (input.validatedOnline) return 'online';
  const until = input.offlineUntil ? Date.parse(input.offlineUntil) : NaN;
  return Number.isFinite(until) && input.now < until ? 'offline_valid' : 'offline_expired';
}

export const mayStartProtectedAction = (mode: AccessMode): boolean => mode !== 'offline_expired';
