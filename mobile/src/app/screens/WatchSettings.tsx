import { useEffect, useState } from 'react';
import { useRuntime, useSession } from '../context';
import { setWatchEnabled, watchAvailable, watchEnabled } from '../../platform/watch';
import { Banner, Button, Card } from '../../shared/ui';

export default function WatchSettings() {
  const runtime = useRuntime();
  const { me } = useSession();
  const [enabled, setEnabled] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { let active = true; void watchEnabled(runtime).then((v) => { if (active) setEnabled(v); }).catch(() => { if (active) setError('No pudimos leer la asociación del reloj.'); }); return () => { active = false; }; }, [runtime, me?.person.id]);
  if (!watchAvailable()) return null;
  return <Card label="Apple Watch"><h3>Steps en tu reloj</h3>
    <p>Muestra la empresa activa, los módulos habilitados y los pendientes de Colaciones y Movilización. Puedes pedir abrir un módulo en el iPhone.</p>
    <small>No se envían contraseñas, ubicación ni datos de pasajeros. El reloj oculta el resumen tras cinco minutos sin actualizar. Los pendientes propios de Tracker se revisan dentro de Tracker.</small>
    <Button disabled={busy} onClick={() => { setBusy(true); setError(''); void setWatchEnabled(runtime, !enabled).then(() => setEnabled(!enabled)).catch(() => setError('No pudimos guardar la asociación. Vuelve a intentarlo.')).finally(() => setBusy(false)); }}>{enabled ? 'Dejar de compartir con Apple Watch' : 'Compartir resumen con Apple Watch'}</Button>
    <small>Instala Steps Watch en el reloj enlazado a este iPhone. {enabled ? 'Resumen habilitado para esta cuenta.' : 'Resumen desactivado.'}</small>
    {error && <Banner tone="bad">{error}</Banner>}
  </Card>;
}
