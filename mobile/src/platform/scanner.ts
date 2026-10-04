// Lectura de códigos con la cámara mediante la API web BarcodeDetector + getUserMedia. EXPERIMENTAL: no validada en dispositivo.
// Si el navegador/WebView no la ofrece, o la persona niega el permiso, la interfaz conserva la alternativa operativa: escribir el código
// o usar un lector tipo teclado. No hay plugin nativo de escaneo en esta versión (pendiente: p. ej. ML Kit con validación en Android/iOS).
export type ScanResult = { ok: true; value: string } | { ok: false; reason: 'unsupported' | 'denied' | 'cancelled' | 'error' };

type DetectorCtor = new (opts?: { formats?: string[] }) => { detect(source: CanvasImageSource): Promise<{ rawValue: string }[]> };

export function scanSupported(w: { BarcodeDetector?: unknown } = globalThis as never, nav: { mediaDevices?: { getUserMedia?: unknown } } = navigator): boolean {
  return typeof w.BarcodeDetector === 'function' && typeof nav.mediaDevices?.getUserMedia === 'function';
}

/** Abre la cámara trasera, lee UN código y libera la cámara siempre. `signal` permite cancelar. */
export async function scanOnce(video: HTMLVideoElement, signal?: AbortSignal, timeoutMs = 30_000): Promise<ScanResult> {
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
