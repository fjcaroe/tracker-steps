import { useEffect, useState } from 'react';
import { RuntimeProvider, useRuntime, useSession, useSyncState } from './context';
import type { Runtime } from './runtime';
import Welcome from './screens/Welcome';
import Onboarding from './screens/Onboarding';
import CompanyPicker from './screens/CompanyPicker';
import Portal from './screens/Portal';
import ModuleHost from './screens/ModuleHost';
import Profile from './screens/Profile';
import SyncScreen from './screens/SyncScreen';
import { Banner, NavBar, Spinner, TopBar } from '../shared/ui';
import { runMigrations, type Journal } from '../migrations';

type Tab = 'inicio' | 'sync' | 'perfil';

function Shell() {
  const runtime = useRuntime();
  const session = useSession();
  const sync = useSyncState();
  const [tab, setTab] = useState<Tab>('inicio');
  const [open, setOpen] = useState<{ id: string; view?: string } | null>(null);
  const [online, setOnline] = useState(typeof navigator === 'undefined' ? true : navigator.onLine);
  const [migration, setMigration] = useState<Journal['failed'] | null>(null);

  useEffect(() => {
    // Primero las migraciones locales (copia de seguridad del Tracker, sin tocar el origen); nunca bloquean el arranque.
    const legacy = typeof localStorage === 'undefined' ? { length: 0, key: () => null, getItem: () => null } : localStorage;
    void runMigrations({ kv: runtime.kv, legacy, now: Date.now }).then((j) => setMigration(j.failed ?? null), () => undefined)
      .then(() => runtime.session.boot()).then(() => runtime.refresh());
  }, [runtime]);
  useEffect(() => { runtime.start(); return () => runtime.stop(); }, [runtime]);
  useEffect(() => {
    const on = () => setOnline(true), off = () => setOnline(false);
    window.addEventListener('online', on); window.addEventListener('offline', off);
    return () => { window.removeEventListener('online', on); window.removeEventListener('offline', off); };
  }, []);
  // Al entrar o cambiar de empresa se relee la cola de ese ámbito y se reanuda lo que esperaba sesión.
  useEffect(() => { if (session.status === 'signed_in') { void runtime.refresh().then(() => runtime.sync()); } setOpen(null); }, [runtime, session.status, session.orgUid]); // eslint-disable-line react-hooks/exhaustive-deps

  if (session.status === 'booting') return <main className="boot"><Spinner label="Abriendo Steps…" /></main>;
  if (session.status === 'signed_out') return <Welcome />;

  const manifest = open ? runtime.manifests.find((m) => m.id === open.id) : null;
  if (manifest && session.orgUid) return <ModuleHost manifest={manifest} view={open?.view} onExit={() => setOpen(null)} />;

  const ready = !!session.orgUid && !!session.catalog;
  return (
    <div className="ui-shell">
      <TopBar title="Steps" right={<span className="topbar__user">{session.me?.person.name}</span>} />
      {migration && <Banner tone="warn">No pudimos guardar la copia de seguridad de los datos del Tracker ({migration.reason}). Tus datos siguen intactos; se reintentará al abrir la app.</Banner>}
      {!online && <Banner tone="warn">Sin conexión: todo se guarda en el teléfono y se envía al volver la señal.</Banner>}
      <main className="ui-main">
        {tab === 'perfil' && <Profile />}
        {tab === 'sync' && ready && <SyncScreen />}
        {tab === 'inicio' && (session.needsOrgChoice ? <CompanyPicker /> : ready ? <Portal manifests={runtime.manifests} onOpen={(id, view) => setOpen({ id, view })} /> : session.orgUid ? <Spinner label="Validando tu acceso…" /> : <Onboarding />)}
        {tab === 'sync' && !ready && <Onboarding />}
      </main>
      <NavBar current={tab} onSelect={setTab} items={[{ id: 'inicio', label: 'Inicio' }, { id: 'sync', label: 'Sincronización', badge: sync.pending + sync.rejected }, { id: 'perfil', label: 'Perfil' }]} />
    </div>
  );
}

export default function App({ runtime }: { runtime: Runtime }) {
  return <RuntimeProvider runtime={runtime}><Shell /></RuntimeProvider>;
}
