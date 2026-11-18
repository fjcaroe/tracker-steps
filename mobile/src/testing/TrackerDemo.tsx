import { useState } from 'react';
import { Banner, Button, Card, TopBar } from '../shared/ui';

/** In-memory interaction only. Does not import Tracker's API, GPS or legacy stores. */
export default function TrackerDemo({ onExit }: { onExit: () => void }) {
  const [state, setState] = useState<'ready' | 'active' | 'paused' | 'finished'>('ready');
  return <div className="ui-shell"><TopBar title="Tracker" onBack={onExit} /><main className="ui-main ui-screen">
    <Banner tone="warn">Simulación de Tracker: no registra GPS ni envía datos. El piloto real conserva el acceso propio de Tracker.</Banner>
    <Card label="Tarea ficticia"><h2>Aplicación en Fundo Norte</h2><p>Tractor Demo 01 · Cuartel 3 · Operación ficticia</p><small>Este recorrido permite probar los botones de jornada. No valida seguimiento, sincronización ni maquinaria real.</small></Card>
    <Card label="Jornada ficticia"><h3>{state === 'ready' ? 'Por iniciar' : state === 'active' ? 'Jornada ficticia en curso' : state === 'paused' ? 'Jornada ficticia en pausa' : 'Jornada ficticia finalizada'}</h3>
      {state === 'ready' && <Button onClick={() => setState('active')}>Iniciar jornada ficticia</Button>}
      {state === 'active' && <Button onClick={() => setState('paused')}>Pausar jornada ficticia</Button>}
      {state === 'paused' && <Button onClick={() => setState('active')}>Retomar jornada ficticia</Button>}
      {(state === 'active' || state === 'paused') && <Button onClick={() => setState('finished')}>Finalizar jornada ficticia</Button>}
      {state === 'finished' && <Button onClick={() => setState('ready')}>Reiniciar simulación</Button>}
    </Card>
  </main></div>;
}
