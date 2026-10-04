import { useState } from 'react';
import { pointQueue, storageHealth } from '../lib/queue';

/** Aviso y recuperación de puntos GPS que el servidor rechazó, o que no pudieron guardarse por falta de espacio. */
export default function RejectedPoints() {
  const [total, setTotal] = useState(pointQueue.rejectedTotal());
  const [msg, setMsg] = useState('');
  const problem = storageHealth.hasProblem();
  if (!total && !problem) return null;

  const exportCopy = () => {
    const blob = new Blob([pointQueue.exportRejected()], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `puntos-gps-rechazados-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    setMsg('Copia generada. Los puntos siguen guardados en este teléfono.');
  };
  const retry = () => {
    const sessions = Object.keys(pointQueue.rejected());
    const moved = sessions.reduce((n, id) => n + pointQueue.requeueRejected(id), 0);
    setTotal(pointQueue.rejectedTotal());
    setMsg(moved ? `${moved} puntos volvieron a la cola de envío.` : 'No se pudieron mover: revisa el espacio del teléfono.');
  };

  return (
    <article className="card stack" aria-label="Puntos GPS con problemas">
      <h3>Puntos GPS con problemas</h3>
      {total > 0 && <p className="muted">El servidor rechazó {total} puntos de ruta. No se borran: quedan guardados aquí hasta que se resuelvan.</p>}
      {problem && <p className="banner" role="alert">El teléfono no tiene espacio para apartar puntos rechazados; siguen en la cola de envío. Libera espacio o envía una copia a soporte.</p>}
      <div className="grid2">
        <button onClick={exportCopy} disabled={!total}>Guardar copia</button>
        <button onClick={retry} disabled={!total}>Reintentar envío</button>
      </div>
      {msg && <p className="muted" role="status">{msg}</p>}
    </article>
  );
}
