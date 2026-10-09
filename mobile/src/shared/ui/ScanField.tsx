import { useEffect, useRef, useState } from 'react';
import { scanMessage, scanOnce, scanSupported } from '../../platform/scanner';
import { Banner, Button, Field } from '.';

/** Campo de código con alternativa operativa: escribir, lector tipo teclado, o cámara si el teléfono la ofrece. */
export default function ScanField({ label, hint, value, onChange }: { label: string; hint?: string; value: string; onChange: (v: string) => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const abort = useRef<AbortController | null>(null);
  const mounted = useRef(true);
  const [scanning, setScanning] = useState(false);
  const [problem, setProblem] = useState('');
  const supported = scanSupported();
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; abort.current?.abort(); }; }, []);

  const start = async () => {
    if (!video.current) return;
    setProblem(''); setScanning(true); abort.current = new AbortController();
    const r = await scanOnce(video.current, abort.current.signal);
    if (!mounted.current) return;
    setScanning(false);
    if (abort.current.signal.aborted) return;
    if (r.ok) onChange(r.value); else if (r.reason !== 'cancelled') setProblem(scanMessage(r.reason));
  };
  return (
    <>
      <Field label={label} hint={hint}><input value={value} onChange={(e) => onChange(e.target.value)} autoCapitalize="none" autoComplete="off" /></Field>
      {supported && (scanning
        ? <Button onClick={() => abort.current?.abort()}>Cancelar lectura</Button>
        : <Button onClick={() => void start()}>Leer con la cámara</Button>)}
      <video ref={video} playsInline muted hidden={!scanning} style={{ width: '100%', borderRadius: 12 }} />
      {problem && <Banner tone="warn">{problem}</Banner>}
    </>
  );
}
