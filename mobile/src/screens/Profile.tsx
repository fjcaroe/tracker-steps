import { useState } from 'react';
import { API_BASE, APP_VERSION, type User } from '../lib/api';
import { sendDiagnostic } from '../lib/diag';
import { applySettings, loadSettings, saveSettings, type Settings } from '../lib/settings';
import { pendingTotal } from '../lib/sync';
import { Sheet } from './Sheets';
import RejectedPoints from './RejectedPoints';

export function HelpSheet({ onClose }: { onClose: () => void }) {
  return (
    <Sheet title="Cómo usar Steps Móvil" onClose={onClose}>
      <ol className="steps">
        <li><strong>Permite la ubicación.</strong> Al iniciar la jornada el teléfono pedirá permiso: elige «Permitir mientras se usa la app» y mantén el GPS activo.</li>
        <li><strong>Inicia la jornada</strong> con la máquina, la labor y el horómetro. Si tu supervisor te asignó una tarea, ábrela desde «Hoy».</li>
        <li><strong>Revisa tu máquina</strong> con «Revisión previa» y reporta cualquier falla con foto.</li>
        <li><strong>Sin señal no pasa nada:</strong> todo queda guardado en el teléfono y se envía solo al volver la conexión.</li>
        <li><strong>Mantén la pantalla encendida</strong> o la app abierta: si el teléfono la cierra, el registro de ruta se detiene.</li>
        <li><strong>Al terminar</strong> toca «Finalizar jornada» e ingresa horómetro y litros.</li>
      </ol>
    </Sheet>
  );
}

export default function Profile({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [s, setS] = useState<Settings>(loadSettings);
  const [help, setHelp] = useState(false);
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);
  const update = (patch: Partial<Settings>) => { const next = { ...s, ...patch }; setS(next); saveSettings(next); applySettings(next); };

  const diagnostic = async () => {
    setBusy(true); setMsg('');
    try { await sendDiagnostic('Diagnóstico enviado por el usuario', `usuario=${user.username} pendientes=${pendingTotal()} online=${navigator.onLine} ua=${navigator.userAgent}`); setMsg('Diagnóstico enviado. Gracias.'); }
    catch (e) { setMsg(`No se pudo enviar: ${(e as Error).message}`); } finally { setBusy(false); }
  };
  const checkUpdate = async () => {
    setMsg('Buscando actualización…');
    try {
      const regs = await navigator.serviceWorker?.getRegistrations?.() ?? [];
      await Promise.all(regs.map((r) => r.update()));
      const keys = await caches?.keys?.() ?? [];
      await Promise.all(keys.map((k) => caches.delete(k)));
    } catch { /* sin service worker */ }
    window.location.reload();
  };

  return (
    <section className="stack">
      <article className="card">
        <h2>{user.full_name}</h2>
        <p className="muted">{user.username} · {user.is_admin ? 'Administrador' : 'Operador'}</p>
      </article>
      <article className="card stack">
        <h3>Pantalla y avisos</h3>
        <label>Tamaño de letra
          <select value={String(s.fontScale)} onChange={(e) => update({ fontScale: Number(e.target.value) })}>
            <option value="1">Normal</option><option value="1.15">Grande</option><option value="1.3">Muy grande</option>
          </select></label>
        <label>Modo noche
          <select value={s.night} onChange={(e) => update({ night: e.target.value as Settings['night'] })}>
            <option value="auto">Automático</option><option value="on">Activado</option><option value="off">Desactivado</option>
          </select></label>
        <label className="check"><input type="checkbox" checked={s.gloves} onChange={(e) => update({ gloves: e.target.checked })} />Modo guantes (botones más grandes)</label>
        <label className="check"><input type="checkbox" checked={s.sound} onChange={(e) => update({ sound: e.target.checked })} />Sonido y vibración en los avisos</label>
        <label>Aviso de velocidad (km/h, 0 = sin aviso)
          <input inputMode="numeric" value={String(s.speedLimitKmh)} onChange={(e) => update({ speedLimitKmh: Math.max(0, Number(e.target.value.replace(/\D/g, '')) || 0) })} /></label>
        <label>Pausa sugerida tras conducir (minutos, 0 = sin aviso)
          <input inputMode="numeric" value={String(s.breakAfterMin)} onChange={(e) => update({ breakAfterMin: Math.max(0, Number(e.target.value.replace(/\D/g, '')) || 0) })} /></label>
      </article>
      <article className="card">
        <h3>Ubicación</h3>
        <p className="muted">La app registra tu posición solo mientras tienes una jornada en curso. Si el navegador o el teléfono bloquea el permiso, actívalo en los ajustes del sitio o de la aplicación.</p>
        <button onClick={() => setHelp(true)}>Ayuda de primer uso</button>
      </article>
      <article className="card stack">
        <h3>Soporte</h3>
        <small>Versión {APP_VERSION} · {pendingTotal()} elementos por enviar</small>
        <small>Servidor: {API_BASE}</small>
        <div className="grid2"><button onClick={() => void diagnostic()} disabled={busy}>Enviar diagnóstico</button><button onClick={() => void checkUpdate()}>Buscar actualización</button></div>
        {msg && <p className="muted" role="status">{msg}</p>}
      </article>
      <RejectedPoints />
      <button className="danger" onClick={onLogout}>Cerrar sesión</button>
      {help && <HelpSheet onClose={() => setHelp(false)} />}
    </section>
  );
}
