import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './styles.css';
import { installErrorLogging } from './lib/diag';

installErrorLogging();

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>);

// Instalable y con shell sin conexión en la versión web (no aplica dentro del contenedor nativo).
if ('serviceWorker' in navigator && location.protocol === 'https:') {
  window.addEventListener('load', () => { void navigator.serviceWorker.register('./sw.js').catch(() => {}); });
}
