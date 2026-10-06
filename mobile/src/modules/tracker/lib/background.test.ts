import { describe, expect, it, vi } from 'vitest';
import type { BackgroundGeolocationPlugin, Location } from '@capacitor-community/background-geolocation';
import { backgroundFix, startBackgroundWatcher } from './background';

const location = (patch: Partial<Location> = {}): Location => ({ time: Date.now(), latitude: -33.4, longitude: -70.6,
  accuracy: 5, speed: 2, altitude: null, altitudeAccuracy: null, bearing: null, simulated: false, ...patch });

describe('background tracking lifecycle', () => {
  function setup() {
    let callback: Parameters<BackgroundGeolocationPlugin['addWatcher']>[1] = () => {};
    const plugin: BackgroundGeolocationPlugin = { addWatcher: vi.fn(async (_options, fn) => { callback = fn; return 'watch-1'; }),
      removeWatcher: vi.fn(async () => {}), openSettings: vi.fn(async () => {}) };
    return { plugin, emit: (l?: Location, e?: Error & { code?: string }) => callback(l, e) };
  }
  it('requires Android notification permission before starting location', async () => {
    const { plugin } = setup(); const error = vi.fn();
    expect(await startBackgroundWatcher(plugin, { requestPermissions: async () => ({ display: 'denied' }) }, 'precise', vi.fn(), error)).toBeNull();
    expect(plugin.addWatcher).not.toHaveBeenCalled(); expect(error).toHaveBeenCalledWith('notifications');
  });
  it('preserves the native timestamp and stops capture after the journey closes', async () => {
    const { plugin, emit } = setup(); const fix = vi.fn();
    const stop = await startBackgroundWatcher(plugin, null, 'precise', fix, vi.fn());
    const l = location(); emit(l); expect(fix).toHaveBeenCalledWith(expect.objectContaining({ ts: l.time, lat: l.latitude }));
    stop!(); stop!(); emit(l); expect(fix).toHaveBeenCalledTimes(1);
    expect(plugin.removeWatcher).toHaveBeenCalledTimes(1);
    expect(plugin.removeWatcher).toHaveBeenCalledWith({ id: 'watch-1' });
  });
  it('uses background mode, explicit permission and the configured battery profile', async () => {
    const { plugin } = setup(); await startBackgroundWatcher(plugin, null, 'balanced', vi.fn(), vi.fn());
    expect(plugin.addWatcher).toHaveBeenCalledWith(expect.objectContaining({ distanceFilter: 25, stale: false, requestPermissions: true, backgroundMessage: expect.any(String) }), expect.any(Function));
  });
  it('reports revoked location permission without pretending it recorded a fix', async () => {
    const { plugin, emit } = setup(); const fix = vi.fn(), error = vi.fn();
    await startBackgroundWatcher(plugin, null, 'precise', fix, error);
    emit(undefined, Object.assign(new Error(), { code: 'NOT_AUTHORIZED' }));
    expect(error).toHaveBeenCalledWith('denied'); expect(fix).not.toHaveBeenCalled();
  });
  it('does not replace missing or stale GPS timestamps with the current time', () => {
    expect(backgroundFix(location({ time: null }))).toBeNull();
    expect(backgroundFix(location({ time: Date.now() - 180000 }))).toBeNull();
    expect(backgroundFix(location({ latitude: NaN }))).toBeNull();
    expect(backgroundFix(location({ longitude: 181 }))).toBeNull();
  });
});
