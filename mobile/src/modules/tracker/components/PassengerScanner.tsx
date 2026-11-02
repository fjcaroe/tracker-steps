import { useEffect, useRef, useState } from 'react';
import jsQR from 'jsqr';
type Detector = { detect(source: HTMLVideoElement): Promise<{ rawValue: string }[]> };
type Decoder = { new(options: { formats: string[] }): Detector; getSupportedFormats(): Promise<string[]> };

export default function PassengerScanner({ onCode, onClose }: { onCode: (value: string) => void; onClose: () => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true; let stream: MediaStream | null = null; let timer = 0; const deadline = Date.now() + 30_000;
    void (async () => {
      try {
        const Decoder = (window as Window & { BarcodeDetector?: Decoder }).BarcodeDetector;
        if (!navigator.mediaDevices?.getUserMedia) throw new Error('Cámara no disponible. Usa el código o la lista.');
        let detector: Detector | null = null;
        if (Decoder) {
          try {
            const formats = (await Decoder.getSupportedFormats()).filter((f) => ['qr_code', 'code_128', 'code_39'].includes(f));
            if (formats.length) detector = new Decoder({ formats });
          } catch { /* The bundled QR decoder works without the experimental API. */ }
        }
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d', { willReadFrequently: true });
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false });
        if (!active) { stream.getTracks().forEach((track) => track.stop()); return; }
        const element = video.current; if (!element) return;
        element.srcObject = stream; await element.play();
        const scan = async () => {
          if (!active) return;
          if (Date.now() > deadline) { stream?.getTracks().forEach((track) => track.stop()); setError('No se leyó un QR. Cierra la cámara para volver a intentar o usa el código.'); return; }
          try {
            let values: { rawValue: string }[] = [];
            if (detector) values = await detector.detect(element);
            else if (context && element.videoWidth) {
              canvas.width = Math.min(800, element.videoWidth);
              canvas.height = Math.round(element.videoHeight * canvas.width / element.videoWidth);
              context.drawImage(element, 0, 0, canvas.width, canvas.height);
              const pixels = context.getImageData(0, 0, canvas.width, canvas.height);
              const decoded = jsQR(pixels.data, pixels.width, pixels.height);
              if (decoded) values = [{ rawValue: decoded.data }];
            }
            if (!active) return;
            if (values[0]?.rawValue) { onCode(values[0].rawValue); return; }
          } catch { /* Skip unavailable frames during focus. */ }
          if (active) timer = window.setTimeout(() => { void scan(); }, 350);
        };
        void scan();
      } catch (cause) { stream?.getTracks().forEach((track) => track.stop()); if (active) setError(cause instanceof Error ? cause.message : 'No se pudo abrir la cámara. Usa el código o la lista.'); }
    })();
    return () => { active = false; clearTimeout(timer); stream?.getTracks().forEach((track) => track.stop()); };
  }, [onCode]);
  return <section className="card stack" aria-label="Lector de pasajeros">
    <p>Apunta al QR del pasajero. Se selecciona su ficha; confirma luego la subida o bajada.</p>
    {error ? <p role="alert">{error}</p> : <video ref={video} muted playsInline style={{ width: '100%', maxHeight: 240 }} />}
    <button onClick={onClose}>Cerrar cámara</button>
  </section>;
}
