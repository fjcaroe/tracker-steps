// Utilidades geográficas puras (probadas) y acceso a la posición en web o nativo.
export type Fix = { ts: number; lat: number; lon: number; speed_mps: number | null; accuracy_m: number | null };

export function haversineMeters(a: { lat: number; lon: number }, b: { lat: number; lon: number }): number {
  const rad = (d: number) => (d * Math.PI) / 180;
  const h = Math.sin(rad(b.lat - a.lat) / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(rad(b.lon - a.lon) / 2) ** 2;
  return 2 * 6371000 * Math.asin(Math.sqrt(h));
}

/** Descarta posiciones imprecisas y saltos imposibles; devuelve si el fix debe registrarse. */
export function acceptFix(prev: Fix | null, next: Fix, maxAccuracyM = 60, maxSpeedMps = 70): boolean {
  if (next.accuracy_m != null && next.accuracy_m > maxAccuracyM) return false;
  if (!prev) return true;
  const dt = (next.ts - prev.ts) / 1000;
  if (dt <= 0) return false;
  return haversineMeters(prev, next) / dt <= maxSpeedMps;
}

export type Stop = () => void;
export type GeoError = 'denied' | 'unavailable' | 'notifications';

/** Observa la posición. En Android/iOS usa el plugin nativo; en web, la API del navegador. */
export async function watchPosition(onFix: (f: Fix) => void, onError: (e: GeoError) => void,
  options: { profile?: 'precise' | 'balanced'; onMode?: (mode: 'background' | 'foreground') => void } = {}): Promise<Stop> {
  const { Capacitor, registerPlugin } = await import('@capacitor/core');
  if (Capacitor.isNativePlatform()) {
    if (Capacitor.isPluginAvailable('BackgroundGeolocation')) {
      try {
        const { startBackgroundWatcher } = await import('./background');
        const notification = Capacitor.getPlatform() === 'android'
          ? (await import('@capacitor/local-notifications')).LocalNotifications : null;
        const stop = await startBackgroundWatcher(registerPlugin('BackgroundGeolocation'), notification,
          options.profile ?? 'precise', onFix, onError);
        if (stop) options.onMode?.('background');
        return stop ?? (() => {});
      } catch { onError('unavailable'); return () => {}; }
    }
    options.onMode?.('foreground');
    const { Geolocation } = await import('@capacitor/geolocation');
    const perm = await Geolocation.requestPermissions();
    if (perm.location !== 'granted') { onError('denied'); return () => {}; }
    const id = await Geolocation.watchPosition({ enableHighAccuracy: true, timeout: 20000, maximumAge: 0 }, (pos, err) => {
      if (err || !pos) { onError('unavailable'); return; }
      onFix({ ts: pos.timestamp, lat: pos.coords.latitude, lon: pos.coords.longitude, speed_mps: pos.coords.speed ?? null, accuracy_m: pos.coords.accuracy ?? null });
    });
    return () => { void Geolocation.clearWatch({ id }); };
  }
  options.onMode?.('foreground');
  if (!('geolocation' in navigator)) { onError('unavailable'); return () => {}; }
  const id = navigator.geolocation.watchPosition(
    (pos) => onFix({ ts: pos.timestamp, lat: pos.coords.latitude, lon: pos.coords.longitude, speed_mps: pos.coords.speed, accuracy_m: pos.coords.accuracy }),
    (err) => onError(err.code === err.PERMISSION_DENIED ? 'denied' : 'unavailable'),
    { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 },
  );
  return () => navigator.geolocation.clearWatch(id);
}

type WakeLockNavigator = Navigator & { wakeLock?: { request(type: 'screen'): Promise<{ release(): Promise<void> }> } };

/** Mantiene la pantalla encendida mientras se registra (donde el navegador lo permite). */
export async function keepAwake(): Promise<() => void> {
  try {
    const lock = await (navigator as WakeLockNavigator).wakeLock?.request('screen');
    return () => { void lock?.release(); };
  } catch { return () => {}; }
}
