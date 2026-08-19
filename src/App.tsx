import { lazy, Suspense, useEffect, useState, type ReactNode } from "react";
import LoginPage from "./pages/LoginPage";
import { useAuthWeb } from "./services/useAuthWeb";
import type { OperationsView } from "./pages/OperationsWorkspace";

const OperationsWorkspace = lazy(() => import("./pages/OperationsWorkspace"));

type IconName = "overview" | "live" | "route" | "stats" | "chart" | "masters" | "history" | "logout";

const iconPaths: Record<IconName, ReactNode> = {
  overview: <><rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/></>,
  live: <><path d="M3 12h3l2-5 4 10 3-7 2 2h4"/><circle cx="12" cy="12" r="9"/></>,
  route: <><circle cx="6" cy="19" r="2"/><circle cx="18" cy="5" r="2"/><path d="M8 19h3a4 4 0 0 0 4-4V9a4 4 0 0 1 3-4"/></>,
  stats: <><path d="M4 19V9M10 19V5M16 19v-7M22 19H2"/></>,
  chart: <><path d="M4 19V5M4 19h16"/><path d="m7 15 4-5 3 2 5-7"/></>,
  masters: <><path d="M4 6h16M4 12h16M4 18h16"/><circle cx="8" cy="6" r="2"/><circle cx="16" cy="12" r="2"/><circle cx="10" cy="18" r="2"/></>,
  history: <><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/></>,
  logout: <><path d="M10 17l5-5-5-5M15 12H3"/><path d="M14 3h5a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-5"/></>,
};

const viewMeta: Record<OperationsView, { eyebrow: string; title: string; description: string }> = {
  userView: { eyebrow: "Centro de operaciones", title: "Resumen de jornada", description: "Una lectura ejecutiva del avance, la flota y los eventos recientes." },
  live: { eyebrow: "Flota en terreno", title: "Monitoreo operacional", description: "Vehículos en movimiento, pasadas agrícolas y telemetría sobre el mapa." },
  routes: { eyebrow: "Rendimiento de flota", title: "Odómetro y utilización", description: "Distancia, horómetro, superficie y rendimiento calculados por máquina." },
  stats: { eyebrow: "Información operacional", title: "Indicadores de jornada", description: "Métricas ponderadas, comparaciones y explicación de cada cálculo." },
  chartsStats: { eyebrow: "Análisis visual", title: "Analítica interactiva", description: "Tendencias de cobertura, distancia, consumo y eficiencia diaria." },
  masters: { eyebrow: "Configuración y calidad", title: "Maestros operacionales", description: "Máquinas, conductores, centros de costo, polígonos y salud de datos." },
  sessions: { eyebrow: "Trazabilidad", title: "Historial de sesiones", description: "Búsqueda, filtros y resultados operacionales por recorrido." },
};

const navItems: { id: OperationsView; label: string; icon: IconName }[] = [
  { id: "userView", label: "Resumen", icon: "overview" },
  { id: "live", label: "Monitoreo", icon: "live" },
  { id: "routes", label: "Odómetro", icon: "route" },
  { id: "stats", label: "Indicadores", icon: "stats" },
  { id: "chartsStats", label: "Analítica", icon: "chart" },
  { id: "masters", label: "Maestros", icon: "masters" },
  { id: "sessions", label: "Historial", icon: "history" },
];

function viewFromHash(): OperationsView {
  const candidate = window.location.hash.replace(/^#\/?/, "") as OperationsView;
  return candidate in viewMeta ? candidate : "userView";
}
function AppIcon({ name }: { name: IconName }) {
  return <svg className="app-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{iconPaths[name]}</svg>;
}

function ViewLoader() {
  return <main className="view-loader" aria-live="polite" aria-busy="true"><span className="view-loader__spinner" aria-hidden="true"/><span>Cargando módulo…</span></main>;
}

export default function App() {
  const { token, isReady } = useAuthWeb();
  if (!isReady) return <div className="view-loader"><span className="view-loader__spinner"/>Cargando sesión…</div>;
  if (!token) return <LoginPage />;
  return <AuthedApp />;
}

function AuthedApp() {
  const { logout, user } = useAuthWeb();
  const [view, setView] = useState<OperationsView>(viewFromHash);

  useEffect(() => {
    const sync = () => setView(viewFromHash());
    window.addEventListener("hashchange", sync);
    window.addEventListener("popstate", sync);
    return () => { window.removeEventListener("hashchange", sync); window.removeEventListener("popstate", sync); };
  }, []);

  const navigate = (next: OperationsView) => {
    setView(next);
    if (viewFromHash() !== next) window.history.pushState(null, "", `#${next}`);
  };

  const currentMeta = viewMeta[view];
  const initial = (user?.full_name || user?.username || "U").slice(0, 1).toUpperCase();

  return (
    <div className="app-shell app-shell--redesign">
      <aside className="app-sidebar">
        <div className="app-brand"><div className="app-brand__mark"><span>S</span></div><div><strong>Steps Tracker</strong><span>Operaciones en terreno</span></div></div>
        <nav className="app-sidebar__nav" aria-label="Navegación principal"><span className="app-sidebar__label">Workspace</span>{navItems.map((item) => <button key={item.id} type="button" className={`app-sidebar__item ${view === item.id ? "is-active" : ""}`} onClick={() => navigate(item.id)} aria-current={view === item.id ? "page" : undefined}><AppIcon name={item.icon}/><span>{item.label}</span>{item.id === "live" && <span className="app-sidebar__badge">4</span>}</button>)}</nav>
        <div className="app-sidebar__footer"><div className="app-user-card"><span className="app-user-card__avatar">{initial}</span><span className="app-user-card__identity"><strong>{user?.full_name || "Usuario Tracker"}</strong><small>{user?.username || "Sesión activa"}</small></span><button type="button" className="app-user-card__logout" onClick={logout} title="Cerrar sesión" aria-label="Cerrar sesión"><AppIcon name="logout"/></button></div></div>
      </aside>
      <div className="app-main">
        <header className="app-topbar"><div className="app-topbar__path"><span>Steps</span><b>/</b>{currentMeta.title}</div><div className="app-topbar__status"><span className="status-pulse"/> Plataforma operacional</div></header>
        <section className="app-page-heading"><div><span className="app-page-heading__eyebrow">{currentMeta.eyebrow}</span><h1>{currentMeta.title}</h1><p>{currentMeta.description}</p></div></section>
        <Suspense fallback={<ViewLoader/>}><OperationsWorkspace view={view}/></Suspense>
      </div>
    </div>
  );
}
