// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { scanMessage, scanOnce, scanSupported } from './scanner';

const video = () => { const v = document.createElement('video'); v.play = vi.fn().mockResolvedValue(undefined); return v; };
const stream = () => { const stop = vi.fn(); return { stream: { getTracks: () => [{ stop }] } as unknown as MediaStream, stop }; };
afterEach(() => { delete (globalThis as { BarcodeDetector?: unknown }).BarcodeDetector; vi.restoreAllMocks(); });

describe('lectura de códigos con cámara', () => {
  it('sin soporte lo dice y no toca la cámara', async () => {
    expect(scanSupported({}, {})).toBe(false);
    expect(await scanOnce(video())).toEqual({ ok: false, reason: 'unsupported' });
    expect(scanMessage('unsupported')).toMatch(/Escribe el código/);
  });
  it('permiso denegado: mensaje con alternativa operativa', async () => {
    (globalThis as { BarcodeDetector?: unknown }).BarcodeDetector = class {};
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia: vi.fn().mockRejectedValue(Object.assign(new Error('x'), { name: 'NotAllowedError' })) } });
    expect(await scanOnce(video())).toEqual({ ok: false, reason: 'denied' });
    expect(scanMessage('denied')).toMatch(/ajustes/);
  });
  it('lee un código y SIEMPRE libera la cámara', async () => {
    const { stream: s, stop } = stream();
    (globalThis as { BarcodeDetector?: unknown }).BarcodeDetector = class { detect = vi.fn().mockResolvedValueOnce([]).mockResolvedValueOnce([{ rawValue: ' BR0001 ' }]); };
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia: vi.fn().mockResolvedValue(s) } });
    expect(await scanOnce(video())).toEqual({ ok: true, value: 'BR0001' });
    expect(stop).toHaveBeenCalled();
  });
  it('cancelar detiene la lectura y libera la cámara', async () => {
    const { stream: s, stop } = stream();
    (globalThis as { BarcodeDetector?: unknown }).BarcodeDetector = class { detect = vi.fn().mockResolvedValue([]); };
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia: vi.fn().mockResolvedValue(s) } });
    const ctl = new AbortController(); setTimeout(() => ctl.abort(), 50);
    expect(await scanOnce(video(), ctl.signal)).toEqual({ ok: false, reason: 'cancelled' });
    expect(stop).toHaveBeenCalled();
  });
});
