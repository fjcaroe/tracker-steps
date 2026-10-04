import type { User } from '../lib/api';
import type { OwnerState } from '../lib/owner';
import { exportLocalData } from '../lib/owner';

/** Compuerta de propietario: hay datos del Tracker en este teléfono que no se enviarán con esta cuenta sin confirmación. Nada se borra. */
export default function OwnerGate({ state, user, onClaim, onLogout, onExit }: { state: OwnerState; user: User; onClaim: () => void; onLogout: () => void; onExit: () => void }) {
  const save = () => {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([exportLocalData()], { type: 'application/json' }));
    a.download = `tracker-datos-locales-${new Date().toISOString().slice(0, 10)}.json`; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  };
  return (
    <main className="content stack" aria-label="Datos pendientes del Tracker">
      <section className="card stack">
        {state.kind !== 'foreign'
          ? <>
              <h2>Hay datos sin dueño conocido en este teléfono</h2>
              <p>Quedaron jornadas o puntos de ruta guardados por una versión anterior de la app. No podemos saber de quién son, y no los enviaremos con tu cuenta ({user.full_name}) sin que lo confirmes.</p>
              <button className="primary" onClick={onClaim}>Sí, son míos: enviarlos</button>
              <button onClick={save}>Guardar una copia primero</button>
            </>
          : <>
              <h2>Hay datos pendientes de otra cuenta</h2>
              <p>Este teléfono tiene datos del Tracker que pertenecen a <strong>{state.owner.name}</strong>. No se envían con la cuenta de {user.full_name} ni se borran.</p>
              <p className="muted">Entra con la cuenta de {state.owner.name} para enviarlos, o guarda una copia y pide ayuda a soporte.</p>
              <button onClick={save}>Guardar una copia</button>
              <button onClick={onLogout}>Entrar con otra cuenta del Tracker</button>
            </>}
        <button className="link" onClick={onExit}>‹ Volver al inicio de Steps</button>
      </section>
    </main>
  );
}
