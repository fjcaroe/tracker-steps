import { APP_VERSION, mobile } from './api';

const syncKey = (userId: number) => `tracker-last-confirmed-sync:${userId}`;

export function recordHealthSync(userId: number) {
  try { localStorage.setItem(syncKey(userId), new Date().toISOString()); } catch { /* almacenamiento no disponible */ }
}

export function healthSyncTime(userId: number): string | null {
  try {
    const time = localStorage.getItem(syncKey(userId));
    return time && Number.isFinite(Date.parse(time)) ? time : null;
  } catch {
    return null;
  }
}

export function reportTrackerHealth(userId: number, pending: number | null) {
  const platform = (window as Window & { Capacitor?: { getPlatform?(): string } }).Capacitor?.getPlatform?.() ?? 'web';
  return mobile.heartbeat({ version: APP_VERSION, platform, pending, last_sync_at: healthSyncTime(userId) });
}
