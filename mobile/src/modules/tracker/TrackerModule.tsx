import { useCallback, useEffect, useState } from 'react';
import { loginWithOdoo, me, refreshToken, setUnauthorizedHandler, tokenStore, type Task, type User } from './lib/api';
import { activeStore } from './lib/queue';
import { applySettings, loadSettings, saveSettings } from './lib/settings';
import { pendingTotal } from './lib/sync';
import Login from './screens/Login';
import Journey from './screens/Journey';
import Tasks from './screens/Tasks';
import History from './screens/History';
import Profile, { HelpSheet } from './screens/Profile';
import Supervisor from './screens/Supervisor';

type Tab = 'journey' | 'tasks' | 'history' | 'supervisor' | 'profile';
const ALL_TABS: { id: Tab; label: string; icon: string; admin?: boolean }[] = [
  { id: 'journey', label: 'Jornada', icon: 'M12 3v18M3 12h18' },
  { id: 'tasks', label: 'Hoy', icon: 'M9 11l3 3 8-8M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h9' },
  { id: 'history', label: 'Historial', icon: 'M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5M12 7v5l3 2' },
  { id: 'supervisor', label: 'Supervisor', icon: 'M12 3l9 4v5c0 5-4 8-9 9-5-1-9-4-9-9V7z', admin: true },
  { id: 'profile', label: 'Perfil', icon: 'M20 21a8 8 0 0 0-16 0M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8' },
];
const REFRESHED = 'steps_movil_token_refreshed';
const TWELVE_HOURS = 12 * 3600 * 1000;

/** Renueva el token si pasaron más de 12 h desde la última renovación (vigencia total: 30 días). */
async function renewIfDue() {
  let last = 0;
  try { last = Number(localStorage.getItem(REFRESHED) || 0); } catch { /* nada */ }
  if (Date.now() - last < TWELVE_HOURS || !tokenStore.get()) return;
  try { await refreshToken(); localStorage.setItem(REFRESHED, String(Date.now())); } catch { /* sin red: se reintenta */ }
}

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [booting, setBooting] = useState(true);
  const [tab, setTab] = useState<Tab>('journey');
  const [online, setOnline] = useState(navigator.onLine);
  const [preset, setPreset] = useState<Task | null>(null);
  const [help, setHelp] = useState(false);

  const logout = useCallback(() => { tokenStore.set(null); setUser(null); }, []);

  useEffect(() => { applySettings(loadSettings()); }, []);
  useEffect(() => {
    setUnauthorizedHandler(logout);
    (async () => {
      if (tokenStore.get()) { try { setUser(await me()); setBooting(false); void renewIfDue(); return; } catch { /* token vencido: se intenta Odoo */ } }
      const odoo = await loginWithOdoo();
      if (odoo) setUser(odoo.user);
      setBooting(false);
    })();
  }, [logout]);

  useEffect(() => { if (user && !loadSettings().seenHelp) setHelp(true); }, [user]);

  useEffect(() => {
    const on = () => setOnline(true), off = () => setOnline(false);
    const visible = () => { if (document.visibilityState === 'visible') void renewIfDue(); };
    window.addEventListener('online', on); window.addEventListener('offline', off);
    document.addEventListener('visibilitychange', visible);
    return () => { window.removeEventListener('online', on); window.removeEventListener('offline', off); document.removeEventListener('visibilitychange', visible); };
  }, []);

  const closeHelp = () => { setHelp(false); saveSettings({ ...loadSettings(), seenHelp: true }); };
  const startTask = (t: Task) => { setPreset(t); setTab('journey'); };
  const safeLogout = () => {
    const pending = pendingTotal();
    const lines = [activeStore.get() ? 'Tienes una jornada en curso: seguirá abierta hasta que la cierres.' : '', pending ? `Hay ${pending} elementos sin enviar: se enviarán cuando vuelvas a entrar con señal.` : ''].filter(Boolean);
    if (lines.length && !confirm(`${lines.join('\n')}\n¿Salir igual?`)) return;
    logout();
  };

  if (booting) return <main className="boot" role="status"><span className="spinner" />Abriendo Steps…</main>;
  if (!user) return <Login onLogin={setUser} />;
  const tabs = ALL_TABS.filter((t) => !t.admin || user.is_admin);

  return (
    <div className="shell">
      <header className="topbar">
        <span className="brand"><b>S</b>Steps <em>Móvil</em></span>
        <span className="topbar__user">{user.full_name}</span>
      </header>
      {!online && <p className="banner" role="status">Sin conexión: todo se guarda en el teléfono y se envía al volver la señal.</p>}
      <main className="content">
        {tab === 'journey' && <Journey online={online} preset={preset} onPresetUsed={() => setPreset(null)} />}
        {tab === 'tasks' && <Tasks onStart={startTask} onOpenJourney={() => setTab('journey')} />}
        {tab === 'history' && <History />}
        {tab === 'supervisor' && user.is_admin && <Supervisor />}
        {tab === 'profile' && <Profile user={user} onLogout={safeLogout} />}
      </main>
      {help && <HelpSheet onClose={closeHelp} />}
      <nav className="tabbar" aria-label="Secciones">
        {tabs.map((t) => (
          <button key={t.id} className={tab === t.id ? 'is-active' : ''} aria-current={tab === t.id ? 'page' : undefined} onClick={() => setTab(t.id)}>
            <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={t.icon} /></svg>
            {t.label}
          </button>
        ))}
      </nav>
    </div>
  );
}
