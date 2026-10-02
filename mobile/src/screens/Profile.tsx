import type { User } from '../lib/api';
import { API_BASE } from '../lib/api';

export default function Profile({ user, onLogout }: { user: User; onLogout: () => void }) {
  return (
    <section className="stack">
      <article className="card">
        <h2>{user.full_name}</h2>
        <p className="muted">{user.username} · {user.is_admin ? 'Administrador' : 'Operador'}</p>
      </article>
      <article className="card">
        <h3>Ubicación</h3>
        <p className="muted">La app registra tu posición solo mientras tienes una jornada en curso. Si el navegador o el teléfono bloquea el permiso, actívalo en los ajustes del sitio o de la aplicación.</p>
        <small className="muted">Servidor: {API_BASE}</small>
      </article>
      <button className="danger" onClick={onLogout}>Cerrar sesión</button>
    </section>
  );
}
