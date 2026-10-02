// Registro local de errores (sin datos personales) para el diagnóstico que el conductor puede enviar a soporte.
import { APP_VERSION, mobile } from './api';

const KEY = 'steps_movil_errors';
const MAX = 40;

function read(): string[] { try { const raw = localStorage.getItem(KEY); return raw ? (JSON.parse(raw) as string[]) : []; } catch { return []; } }

export function logError(message: string) {
  const list = read();
  list.push(`${new Date().toISOString()} ${message}`.slice(0, 400));
  try { localStorage.setItem(KEY, JSON.stringify(list.slice(-MAX))); } catch { /* sin espacio */ }
}
export const errorLog = () => read();

export function installErrorLogging() {
  window.addEventListener('error', (e) => logError(`error: ${e.message}`));
  window.addEventListener('unhandledrejection', (e) => logError(`rechazo: ${(e.reason as Error)?.message ?? String(e.reason)}`));
}

export function sendDiagnostic(message: string, extra: string): Promise<{ ok: boolean }> {
  return mobile.diagnostic({ version: APP_VERSION, message, log: [extra, ...read()].join('\n').slice(0, 20000) });
}
