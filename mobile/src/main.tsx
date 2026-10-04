import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './app/App';
import { createRuntime } from './app/bootstrap';
import './styles.css';
import { installErrorLogging } from './modules/tracker/lib/diag';

installErrorLogging();

createRoot(document.getElementById('root')!).render(<StrictMode><App runtime={createRuntime()} /></StrictMode>);

// Instalable y con shell sin conexión en la versión web (no aplica dentro del contenedor nativo).
if ('serviceWorker' in navigator && location.protocol === 'https:') {
  window.addEventListener('load', () => { void navigator.serviceWorker.register('./sw.js').catch(() => {}); });
}
