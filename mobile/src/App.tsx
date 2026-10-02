import { useCallback, useEffect, useState } from 'react';
import { loginWithOdoo, me, setUnauthorizedHandler, tokenStore, type User } from './lib/api';
import { activeStore } from './lib/queue';
import Login from './screens/Login';
import Journey from './screens/Journey';
import History from './screens/History';
import Profile from './screens/Profile';

type Tab = 'journey' | 'history' | 'profile';
const tabs: { id: Tab; label: string; icon: string }[] = [
  { id: 'journey', label: 'Jornada', icon: 'M12 3v18M3 12h18' },
  { id: 'history', label: 'Historial', icon: 'M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5M12 7v5l3 2' },
  { id: 'profile', label: 'Perfil', icon: 'M20 21a8 8 0 0 0-16 0M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8' },
];

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [booting, setBooting] = useState(true);
  const [tab, setTab] = useState<Tab>('journey');
  const [online, setOnline] = useState(navigator.onLine);

  const logout = useCallback(() => { tokenStore.set(null); setUser(null); }, []);

  useEffect(() => {
    setUnauthorizedHandler(logout);
    (async () => {
      if (tokenStore.get()) { try { setUser(await me()); setBooting(false); return; } catch { /* token vencido: se intenta Odoo */ } }
      const odoo = await loginWithOdoo();
      if (odoo) setUser(odoo.user);
      setBooting(false);
    })();
  }, [logout]);

  useEffect(() => {
    const on = () => setOnline(true), off = () => setOnline(false);
    window.addEventListener('online', on); window.addEventListener('offline', off);
    return () => { window.removeEventListener('online', on); window.removeEventListener('offline', off); };
  }, []);

  if (booting) return <main className="boot" role="status"><span className="spinner" />Abriendo Steps…</main>;
  if (!user) return <Login onLogin={setUser} />;

  return (
    <div className="shell">
      <header className="topbar">
        <span className="brand"><b>S</b>Steps <em>Móvil</em></span>
        <span className="topbar__user">{user.full_name}</span>
      </header>
      {!online && <p className="banner" role="status">Sin conexión: los puntos GPS se guardan y se envían al volver la señal.</p>}
      <main className="content">
        {tab === 'journey' && <Journey online={online} />}
        {tab === 'history' && <History />}
        {tab === 'profile' && <Profile user={user} onLogout={() => { if (activeStore.get() && !confirm('Tienes una jornada en curso. Si sales, seguirá abierta hasta que la cierres. ¿Salir igual?')) return; logout(); }} />}
      </main>
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
