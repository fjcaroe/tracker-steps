import type { BackgroundGeolocationPlugin, Location } from '@capacitor-community/background-geolocation';
import type { Fix, GeoError, Stop } from './geo';

export type GpsProfile = 'precise' | 'balanced';
type Notifications = { requestPermissions(): Promise<{ display: string }> };

export function backgroundFix(location: Location, now = Date.now()): Fix | null {
  if (location.time == null || !Number.isFinite(location.time) || location.time <= 0 ||
      location.time > now + 60000 || now - location.time > 120000 ||
      !Number.isFinite(location.latitude) || Math.abs(location.latitude) > 90 ||
      !Number.isFinite(location.longitude) || Math.abs(location.longitude) > 180 ||
      !Number.isFinite(location.accuracy) || location.accuracy < 0) return null;
  return { ts: location.time, lat: location.latitude, lon: location.longitude,
    speed_mps: location.speed != null && Number.isFinite(location.speed) && location.speed >= 0 ? location.speed : null, accuracy_m: location.accuracy };
}

/** Explicit location permission and Android notice; never runs without a journey. */
export async function startBackgroundWatcher(plugin: BackgroundGeolocationPlugin,
  notifications: Notifications | null, profile: GpsProfile,
  onFix: (f: Fix) => void, onError: (e: GeoError) => void): Promise<Stop | null> {
  if (notifications && (await notifications.requestPermissions()).display !== 'granted') {
    onError('notifications'); return null;
  }
  let stopped = false;
  const id = await plugin.addWatcher({ backgroundTitle: 'Steps Móvil',
    backgroundMessage: 'Steps está registrando la ruta de tu jornada',
    requestPermissions: true, stale: false, distanceFilter: profile === 'balanced' ? 25 : 5 }, (location, error) => {
    if (stopped) return;
    if (error) { onError(error.code === 'NOT_AUTHORIZED' ? 'denied' : 'unavailable'); return; }
    const fix = location && backgroundFix(location);
    if (fix) onFix(fix);
  });
  return () => { if (stopped) return; stopped = true; void plugin.removeWatcher({ id }).catch(() => {}); };
}
