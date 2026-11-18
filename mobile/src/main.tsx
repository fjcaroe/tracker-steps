import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './app/App';
import { createDemoRuntime, createRuntime } from './app/bootstrap';
import './styles.css';
import { installErrorLogging } from './modules/tracker/lib/diag';
import { Capacitor } from '@capacitor/core';

installErrorLogging();
const root = createRoot(document.getElementById('root')!);

if (import.meta.env.MODE === 'tracker') {
  // Production /truck/ keeps its existing access and local storage. The
  // unified portal remains a separate pilot until its server is promoted.
  void import('./modules/tracker/TrackerModule').then(({ default: Tracker }) => root.render(
    <StrictMode><Tracker onExit={() => window.location.assign('/')} /></StrictMode>));
} else if (import.meta.env.MODE === 'demo') {
  // Datos ficticios y servidor falso: la insignia lo deja siempre a la vista para que nadie lo confunda con producción.
  void Promise.all([createDemoRuntime(), import('./testing/DemoHeader')]).then(([{ runtime, title }, { default: DemoHeader }]) => root.render(
    <StrictMode><DemoHeader title={title} /><App runtime={runtime} /></StrictMode>));
} else {
  root.render(<StrictMode>{import.meta.env.MODE === 'pilot' && <aside style={{ background: '#f8df91', color: '#3a2b00', padding: 'calc(6px + env(safe-area-inset-top)) 12px 6px', fontSize: 12 }}>PILOTO · Desarrollo · Usa únicamente registros de prueba.</aside>}<App runtime={createRuntime()} /></StrictMode>);
  // Instalable y con shell sin conexión en la versión web (no aplica dentro del contenedor nativo).
  if (!Capacitor.isNativePlatform() && 'serviceWorker' in navigator && location.protocol === 'https:') {
    window.addEventListener('load', () => { void navigator.serviceWorker.register('./sw.js').catch(() => {}); });
  }
}
