// Posición puntual para marcar eventos. Se pide solo al ejecutar la acción; si se deniega o tarda, el evento sigue sin ubicación.
import { Capacitor } from '@capacitor/core';

export type OnePosition = { lat: number; lon: number; accuracy: number };
export type GeoResult = { position: OnePosition | null; reason: 'ok' | 'denied' | 'unavailable' | 'timeout' };

export async function currentPosition(timeoutMs = 4000): Promise<GeoResult> {
  try {
    if (Capacitor.isNativePlatform()) {
      const { Geolocation } = await import('@capacitor/geolocation');
      const status = await Geolocation.checkPermissions();
      if (status.location === 'denied') return { position: null, reason: 'denied' };
      if (status.location !== 'granted') {
        const asked = await Geolocation.requestPermissions({ permissions: ['location'] });
        if (asked.location !== 'granted') return { position: null, reason: 'denied' };
      }
      const p = await Geolocation.getCurrentPosition({ enableHighAccuracy: true, timeout: timeoutMs });
      return { position: { lat: p.coords.latitude, lon: p.coords.longitude, accuracy: p.coords.accuracy }, reason: 'ok' };
    }
    if (!('geolocation' in navigator)) return { position: null, reason: 'unavailable' };
    return await new Promise<GeoResult>((resolve) => navigator.geolocation.getCurrentPosition(
      (p) => resolve({ position: { lat: p.coords.latitude, lon: p.coords.longitude, accuracy: p.coords.accuracy }, reason: 'ok' }),
      (err) => resolve({ position: null, reason: err.code === err.PERMISSION_DENIED ? 'denied' : err.code === err.TIMEOUT ? 'timeout' : 'unavailable' }),
      { enableHighAccuracy: true, timeout: timeoutMs },
    ));
  } catch { return { position: null, reason: 'unavailable' }; }
}
