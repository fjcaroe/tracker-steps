import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './app/App';
import { createDemoRuntime, createRuntime } from './app/bootstrap';
import './styles.css';
import { installErrorLogging } from './modules/tracker/lib/diag';

installErrorLogging();
const root = createRoot(document.getElementById('root')!);

if (import.meta.env.MODE === 'demo') {
  // Datos ficticios y servidor falso: la insignia lo deja siempre a la vista para que nadie lo confunda con producción.
  void createDemoRuntime().then(({ runtime, title }) => root.render(
    <StrictMode><div style={{ background: '#7a1510', color: '#fff', padding: '4px 12px', fontSize: 12, textAlign: 'center' }}>MODO DEMOSTRACIÓN · datos ficticios · {title}</div><App runtime={runtime} /></StrictMode>));
} else {
  root.render(<StrictMode><App runtime={createRuntime()} /></StrictMode>);
  // Instalable y con shell sin conexión en la versión web (no aplica dentro del contenedor nativo).
  if ('serviceWorker' in navigator && location.protocol === 'https:') {
    window.addEventListener('load', () => { void navigator.serviceWorker.register('./sw.js').catch(() => {}); });
  }
}
