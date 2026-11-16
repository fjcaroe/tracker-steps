import { APP_VERSION, mobile } from './api';

const KEY = 'tracker-support-errors';
const MAX = 40;
type ErrorKind = 'error' | 'rechazo';
type LogEntry = { time: string; kind: ErrorKind };

function read(): LogEntry[] {
  try {
    const data: unknown = JSON.parse(localStorage.getItem(KEY) ?? '[]');
    return Array.isArray(data) ? data.filter((entry): entry is LogEntry =>
      Boolean(entry) && typeof entry.time === 'string'
      && new Date(Date.parse(entry.time)).toJSON() === entry.time
      && (entry.kind === 'error' || entry.kind === 'rechazo')).slice(-MAX) : [];
  } catch {
    return [];
  }
}

function logError(kind: ErrorKind) {
  const list = [...read(), { time: new Date().toISOString(), kind }];
  try { localStorage.setItem(KEY, JSON.stringify(list.slice(-MAX))); } catch { /* sin espacio */ }
}

export function installErrorLogging() {
  window.addEventListener('error', () => logError('error'));
  window.addEventListener('unhandledrejection', () => logError('rechazo'));
}

export function sendDiagnostic(pending: number | null, online: boolean): Promise<{ ok: boolean }> {
  const summary = `pendientes=${pending ?? 'sin consultar'} conexión=${online ? 'disponible' : 'sin conexión'}`;
  const log = [summary, ...read().map(({ time, kind }) => `${time} ${kind}`)].join('\n');
  return mobile.diagnostic({ version: APP_VERSION, message: 'Diagnóstico enviado desde Perfil', log });
}
