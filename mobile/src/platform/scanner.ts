// Native scanning uses the maintained Capacitor adapter; web keeps BarcodeDetector.
// Manual input/keyboard readers remain available after permission denial or cancellation.
import { Capacitor } from '@capacitor/core';
export type ScanResult = { ok: true; value: string } | { ok: false; reason: 'unsupported' | 'denied' | 'cancelled' | 'error' };

type DetectorCtor = new (opts?: { formats?: string[] }) => { detect(source: CanvasImageSource): Promise<{ rawValue: string }[]> };

export function scanSupported(w: { BarcodeDetector?: unknown } = globalThis as never, nav: { mediaDevices?: { getUserMedia?: unknown } } = navigator): boolean {
  return Capacitor.isNativePlatform() || (typeof w.BarcodeDetector === 'function' && typeof nav.mediaDevices?.getUserMedia === 'function');
}

export async function scanNative(scan: () => Promise<{ ScanResult: string }>, signal?: AbortSignal): Promise<ScanResult> {
  if (signal?.aborted) return { ok: false, reason: 'cancelled' };
  try {
    const result = await scan();
    if (signal?.aborted || !result.ScanResult?.trim()) return { ok: false, reason: 'cancelled' };
    return { ok: true, value: result.ScanResult.trim() };
  } catch (error) {
    const code = String((error as { code?: string; name?: string }).code ?? (error as Error).name ?? '');
    return { ok: false, reason: /permission|notallowed|denied/i.test(code) ? 'denied' : /cancel/i.test(code) ? 'cancelled' : 'error' };
  }
}

/** Abre la cámara trasera, lee UN código y libera la cámara siempre. `signal` permite cancelar. */
export async function scanOnce(video: HTMLVideoElement, signal?: AbortSignal, timeoutMs = 30_000): Promise<ScanResult> {
  if (Capacitor.isNativePlatform()) {
    const { CapacitorBarcodeScanner, CapacitorBarcodeScannerTypeHintALLOption, CapacitorBarcodeScannerAndroidScanningLibrary } = await import('@capacitor/barcode-scanner');
    return scanNative(() => CapacitorBarcodeScanner.scanBarcode({ hint: CapacitorBarcodeScannerTypeHintALLOption.ALL,
      scanInstructions: 'Apunta al código de la credencial', scanText: 'Leer código',
      android: { scanningLibrary: CapacitorBarcodeScannerAndroidScanningLibrary.ZXING } }), signal);
  }
  if (!scanSupported()) return { ok: false, reason: 'unsupported' };
  let stream: MediaStream | null = null;
  try {
    try { stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false }); }
    catch (e) { return { ok: false, reason: ['NotAllowedError', 'SecurityError', 'PermissionDeniedError'].includes((e as DOMException).name) ? 'denied' : 'error' }; }
    video.srcObject = stream;
    await video.play();
    const Detector = (globalThis as unknown as { BarcodeDetector: DetectorCtor }).BarcodeDetector;
    const detector = new Detector({ formats: ['qr_code', 'code_128', 'code_39', 'ean_13', 'ean_8', 'itf'] });
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      if (signal?.aborted) return { ok: false, reason: 'cancelled' };
      const found = await detector.detect(video).catch(() => []);
      if (found[0]?.rawValue) return { ok: true, value: found[0].rawValue.trim() };
      await new Promise((r) => setTimeout(r, 200));
    }
    return { ok: false, reason: 'error' };
  } finally {
    stream?.getTracks().forEach((t) => t.stop());
    video.srcObject = null;
  }
}

export const scanMessage = (reason: Extract<ScanResult, { ok: false }>['reason']): string => ({
  unsupported: 'Este teléfono no permite leer códigos con la cámara. Escribe el código o usa un lector.',
  denied: 'La cámara está bloqueada. Actívala en los ajustes del teléfono o escribe el código.',
  cancelled: 'Lectura cancelada.',
  error: 'No se pudo leer el código. Acércalo e inténtalo de nuevo, o escríbelo.',
})[reason];
