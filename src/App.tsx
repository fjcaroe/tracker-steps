// src/App.tsx
import { lazy, Suspense, useEffect, useState, type ReactNode } from "react";
import type { MastersView } from "./pages/MastersPage";
import { useTracker, type TrackerMode } from "./hooks/useTracker";
import LoginPage from "./pages/LoginPage";
import { useAuthWeb } from "./services/useAuthWeb";
import { apiJson, setApiAuthToken } from "./services/http";
import type { TrackPoint } from "./types";

const TrackerControl = lazy(() => import("./components/TrackerControl"));
const TrackerMap = lazy(() => import("./components/TrackerMap"));
const SessionsPage = lazy(() => import("./pages/SessionsPage"));
const RoutesPage = lazy(() => import("./pages/RoutesPage"));
const UserViewPage = lazy(() => import("./pages/UserViewPage"));
const StatsPage = lazy(() => import("./pages/StatsPage"));
const ChartsStatsPage = lazy(() => import("./pages/ChartsStatsPage"));
const MastersPage = lazy(() => import("./pages/MastersPage"));

type ActiveSession = {
  id: string;
  machine_id: number;
  machine_name?: string | null;
  driver_name?: string | null;
  cost_center_name?: string | null;
  started_at: string;
  points_count: number;
};

type FieldPolygon = {
  id: number;
  name: string;
  color?: string | null;
  polygon: { lat: number; lon: number }[];
};

type View =
  | "live"
  | "routes"
  | "sessions"
  | "userView"
  | "stats"
  | "chartsStats"
  | "masters";

function formatTime(ts: number) {
  const d = new Date(ts);
  return d.toLocaleTimeString("es-CL", { hour12: false });
}

function formatNumber(n: number | null | undefined, decimals = 5) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return n.toFixed(decimals);
}
function toRad(deg: number): number {
  return (deg * Math.PI) / 180;
}

function haversineMeters(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371000;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const φ1 = toRad(lat1);
  const φ2 = toRad(lat2);

  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(φ1) * Math.cos(φ2) * Math.sin(dLon / 2) ** 2;

  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

function downsampleStride<T>(items: T[], max: number): T[] {
  if (items.length <= max) return items;
  const step = Math.ceil(items.length / max);
  const result: T[] = [];
  for (let index = 0; index < items.length; index += step) result.push(items[index]);
  return result;
}

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

function AppIcon({ name }: { name: IconName }) {
  return (
    <svg className="app-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {iconPaths[name]}
    </svg>
  );
}

const viewMeta: Record<View, { eyebrow: string; title: string; description: string }> = {
  userView: { eyebrow: "Centro de operaciones", title: "Resumen de jornada", description: "Actividad, tareas y estado general de la operación agrícola." },
  live: { eyebrow: "Flota en terreno", title: "Monitoreo en tiempo real", description: "Ubicación, recorrido y actividad de cada vehículo en una sola vista." },
  routes: { eyebrow: "Rendimiento de flota", title: "Odómetro y recorridos", description: "Distancias acumuladas y trazabilidad por máquina." },
  stats: { eyebrow: "Información operacional", title: "Indicadores", description: "Consulta el desempeño consolidado por período y centro de costo." },
  chartsStats: { eyebrow: "Análisis visual", title: "Gráficos y tendencias", description: "Explora patrones y compara la evolución de la operación." },
  masters: { eyebrow: "Configuración", title: "Maestros", description: "Administra los datos base que utiliza Tracker Steps." },
  sessions: { eyebrow: "Trazabilidad", title: "Sesiones históricas", description: "Revisa viajes terminados y reproduce sus recorridos." },
};

function viewFromHash(): View {
  const candidate = window.location.hash.replace(/^#\/?/, "") as View;
  return candidate in viewMeta ? candidate : "userView";
}

function ViewLoader() {
  return (
    <main className="view-loader" aria-live="polite" aria-busy="true">
      <span className="view-loader__spinner" aria-hidden="true" />
      <span>Cargando módulo…</span>
    </main>
  );
}

/**
 * App SOLO decide qué mostrar (loading/login/app).
 * Importante: aquí no se ejecutan hooks "extra" condicionales.
 */
export default function App() {
  const { token, isReady } = useAuthWeb();

  if (!isReady) {
    return <div style={{ padding: 16, fontWeight: 800 }}>Cargando sesión…</div>;
  }

  if (!token) {
    return <LoginPage />;
  }

  return <AuthedApp />;
}

/**
 * Todo lo que usa useEffect/useTracker/etc vive aquí,
 * y se ejecuta siempre que este componente esté montado.
 */
function AuthedApp() {
  const { token, logout, user } = useAuthWeb();

  const [view, setView] = useState<View>(viewFromHash);

  // 👇 sub-vista interna para Maestros
  const [mastersView, setMastersView] = useState<MastersView>("drivers");

  const [mode] = useState<TrackerMode>("machine");
  const [activeSessions, setActiveSessions] = useState<ActiveSession[]>([]);
  const [selectedLiveSessionId, setSelectedLiveSessionId] = useState<string | null>(null);
  const [fields, setFields] = useState<FieldPolygon[]>([]);
  const [timeWindowMinutes, setTimeWindowMinutes] = useState<number>(60); // 60 min default
  const [followSelected, setFollowSelected] = useState<boolean>(true);
  const [showOnlySelectedTrack, setShowOnlySelectedTrack] = useState<boolean>(true);
  const [selectedLivePoints, setSelectedLivePoints] = useState<TrackPoint[]>([]);
  const [liveAutoRefresh, setLiveAutoRefresh] = useState(false);
  const [refreshNonce, setRefreshNonce] = useState(0);
  const refreshNow = () => setRefreshNonce((n) => n + 1);
  const [trackLoadError, setTrackLoadError] = useState<string | null>(null);
  const [dateFrom, setDateFrom] = useState<string>("");
  const [dateTo, setDateTo] = useState<string>("");
  const [lastSessionsSyncAt, setLastSessionsSyncAt] = useState<number | null>(null);
  const [sessionsSyncError, setSessionsSyncError] = useState(false);
  const [statusClock, setStatusClock] = useState(() => Date.now());

  useEffect(() => {
    const syncViewFromUrl = () => setView(viewFromHash());
    window.addEventListener("hashchange", syncViewFromUrl);
    window.addEventListener("popstate", syncViewFromUrl);
    return () => {
      window.removeEventListener("hashchange", syncViewFromUrl);
      window.removeEventListener("popstate", syncViewFromUrl);
    };
  }, []);

  useEffect(() => {
    const id = window.setInterval(() => setStatusClock(Date.now()), 30_000);
    return () => window.clearInterval(id);
  }, []);

  const navigateToView = (nextView: View) => {
    setView(nextView);
    if (viewFromHash() !== nextView) {
      window.history.pushState(null, "", `#${nextView}`);
    }
  };

  type TrackApiItem = {
    ts: string; // ISO
    lat: number;
    lon: number;
    speed_mps?: number | null;
    n: number;
  };

  type TrackApiResponse = {
    items: TrackApiItem[];
    next_cursor?: string | null;
    resolution: "raw" | "10s" | "1m";
  };

  function pickResolution(rangeMs: number): "raw" | "10s" | "1m" {
    const min15 = 15 * 60_000;
    const h48 = 48 * 60 * 60_000;

    if (rangeMs <= min15) return "raw";
    if (rangeMs <= h48) return "10s";
    return "1m";
  }

  const MAX_DRAW_POINTS = 12000;

  useEffect(() => {
    if (!selectedLiveSessionId) {
      return;
    }

    let mounted = true;

    const loadPoints = async () => {
      try {
        setTrackLoadError(null);

        const now = Date.now();
        const fromMs = dateFrom ? new Date(dateFrom).getTime() : now - timeWindowMinutes * 60_000;
        const toMs = dateTo ? new Date(dateTo).getTime() : now;

        const fromIso = new Date(fromMs).toISOString();
        const toIso = new Date(toMs).toISOString();

        const rangeMs = toMs - fromMs;
        const resolution = pickResolution(rangeMs);

        const qs = new URLSearchParams();
        qs.set("from", fromIso);
        qs.set("to", toIso);
        qs.set("resolution", resolution);
        qs.set("limit", "20000");

        const resp = await apiJson<TrackApiResponse>(
          `/sessions/${selectedLiveSessionId}/track?${qs.toString()}`
        );

        const norm: TrackPoint[] = (resp.items || [])
          .map((it, idx) => {
            const t = new Date(it.ts).getTime();
            return {
              id: Number.isFinite(t) ? t * 100 + idx : idx,
              timestamp: t,
              lat: it.lat,
              lon: it.lon,
              speed_mps: it.speed_mps ?? null,
            };
          })
          .sort((a, b) => a.timestamp - b.timestamp);

        const sliced = norm.length > MAX_DRAW_POINTS ? downsampleStride(norm, MAX_DRAW_POINTS) : norm;

        if (mounted) setSelectedLivePoints(sliced);

        // 🔎 si no hay puntos, avisa (esto explica el “no se inmuta”)
        if (mounted && sliced.length === 0) {
          setTrackLoadError(
            "No hay puntos en este rango. Usa 'Sesión completa' para recuperar recorridos antiguos."
          );
        }
      } catch (err: unknown) {
        console.error("Error cargando track", err);
        if (mounted) {
          setSelectedLivePoints([]);
          setTrackLoadError(err instanceof Error ? err.message : "No fue posible cargar el recorrido.");
        }
      }
    };


    void loadPoints();

    if (!liveAutoRefresh) return () => { mounted = false; };

    const id = window.setInterval(loadPoints, 5000);
    return () => {
      mounted = false;
      window.clearInterval(id);
    };
  }, [
    selectedLiveSessionId,
    timeWindowMinutes,
    liveAutoRefresh,
    refreshNonce,
    dateFrom,
    dateTo,
  ]);

  useEffect(() => {
    setApiAuthToken(token ?? null);
  }, [token]);

  useEffect(() => {
    const onExpired = () => logout();
    window.addEventListener("auth:expired", onExpired);
    return () => window.removeEventListener("auth:expired", onExpired);
  }, [logout]);

  useEffect(() => {
    let mounted = true;

    const loadActiveSessions = async () => {
      try {
        const data = await apiJson<ActiveSession[]>("/sessions_active");
        if (!mounted) return;

        setActiveSessions(data);
        setLastSessionsSyncAt(Date.now());
        setSessionsSyncError(false);
        setSelectedLiveSessionId((prev) =>
          prev && !data.some((s) => s.id === prev) ? null : prev
        );
      } catch (err) {
        console.error("Error cargando sesiones activas", err);
        if (mounted) setSessionsSyncError(true);
      }
    };

    loadActiveSessions();
    const id = window.setInterval(loadActiveSessions, 15000);

    return () => {
      mounted = false;
      window.clearInterval(id);
    };
  }, [token]);

  useEffect(() => {
    let mounted = true;

    const loadFields = async () => {
      try {
        const data = await apiJson<FieldPolygon[]>("/fields");
        if (!mounted) return;
        setFields(data);
      } catch (err) {
        console.error("Error cargando campos", err);
        if (mounted) setFields([]);
      }
    };

    loadFields();
    return () => {
      mounted = false;
    };
  }, [token]);

  const {
    isTracking,
    points,
    error,
    sessionId,
    totalPoints,
    durationMinutes,
    lastPoint,
  } = useTracker(mode);

  const currentMeta = viewMeta[view];
  const selectedSession = activeSessions.find((session) => session.id === selectedLiveSessionId) ?? null;
  const activeMachineCount = new Set(activeSessions.map((session) => session.machine_id)).size;
  const liveDisplayPoints = selectedLiveSessionId ? selectedLivePoints : points;
  const liveDistanceMeters = liveDisplayPoints.reduce((distance, point, index) => {
    if (index === 0) return 0;
    const previous = liveDisplayPoints[index - 1];
    return distance + haversineMeters(previous.lat, previous.lon, point.lat, point.lon);
  }, 0);
  const latestLivePoint = liveDisplayPoints[liveDisplayPoints.length - 1] ?? null;
  const syncAgeSeconds = lastSessionsSyncAt
    ? Math.max(0, Math.floor((statusClock - lastSessionsSyncAt) / 1000))
    : null;
  const syncStatus = sessionsSyncError
    ? "Conexión interrumpida · mostrando últimos datos"
    : syncAgeSeconds === null
      ? "Conectando con Tracker…"
      : syncAgeSeconds < 15
        ? "Sincronizado ahora"
        : `Sincronizado hace ${syncAgeSeconds} s`;

  const navItems: { id: View; label: string; icon: IconName }[] = [
    { id: "userView", label: "Resumen", icon: "overview" },
    { id: "live", label: "Monitoreo", icon: "live" },
    { id: "routes", label: "Odómetro", icon: "route" },
    { id: "stats", label: "Indicadores", icon: "stats" },
    { id: "chartsStats", label: "Analítica", icon: "chart" },
    { id: "masters", label: "Maestros", icon: "masters" },
    { id: "sessions", label: "Historial", icon: "history" },
  ];

  return (
    <div className="app-shell app-shell--redesign">
      <aside className="app-sidebar">
        <div className="app-brand">
          <div className="app-brand__mark" aria-hidden="true"><span>S</span></div>
          <div>
            <strong>Steps Tracker</strong>
            <span>Operaciones en terreno</span>
          </div>
        </div>

        <nav className="app-sidebar__nav" aria-label="Navegación principal">
          <span className="app-sidebar__label">Workspace</span>
          {navItems.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`app-sidebar__item ${view === item.id ? "is-active" : ""}`}
              onClick={() => navigateToView(item.id)}
              aria-current={view === item.id ? "page" : undefined}
            >
              <AppIcon name={item.icon} />
              <span>{item.label}</span>
              {item.id === "live" && activeMachineCount > 0 && (
                <span className="app-sidebar__badge">{activeMachineCount}</span>
              )}
            </button>
          ))}
        </nav>

        <div className="app-sidebar__footer">
          <div className="app-user-card">
            <span className="app-user-card__avatar" aria-hidden="true">
              {(user?.full_name || user?.username || "U").slice(0, 1).toUpperCase()}
            </span>
            <span className="app-user-card__identity">
              <strong>{user?.full_name || "Usuario Tracker"}</strong>
              <small>{user?.username || "Sesión activa"}</small>
            </span>
            <button type="button" className="app-user-card__logout" onClick={logout} title="Cerrar sesión" aria-label="Cerrar sesión">
              <AppIcon name="logout" />
            </button>
          </div>
        </div>
      </aside>

      <div className="app-main">
        <header className="app-topbar">
          <div className="app-topbar__path"><span>Steps</span><b>/</b>{currentMeta.title}</div>
          <div className={`app-topbar__status ${sessionsSyncError ? "is-error" : ""}`} role="status">
            <span className="status-pulse" /> {syncStatus}
          </div>
        </header>

        <section className="app-page-heading">
          <div>
            <span className="app-page-heading__eyebrow">{currentMeta.eyebrow}</span>
            <h1>{currentMeta.title}</h1>
            <p>{currentMeta.description}</p>
          </div>
          {view === "live" && (
            <button type="button" className="button button--primary" onClick={refreshNow}>
              Actualizar datos
            </button>
          )}
        </section>

      <Suspense fallback={<ViewLoader />}>
      {view === "live" && (
        <main className="tracker-workspace tracker-workspace--live">
          <section className="tracker-kpis" aria-label="Resumen de monitoreo">
            <article><span>Máquinas con sesión</span><strong>{activeMachineCount}</strong><small><i className="kpi-dot kpi-dot--open" /> {activeSessions.length} {activeSessions.length === 1 ? "sesión abierta" : "sesiones abiertas"}</small></article>
            <article><span>Puntos en vista</span><strong>{liveDisplayPoints.length.toLocaleString("es-CL")}</strong><small>{selectedSession ? selectedSession.machine_name || `Máquina #${selectedSession.machine_id}` : "Flota completa"}</small></article>
            <article><span>Distancia visible</span><strong>{(liveDistanceMeters / 1000).toFixed(1)} <em>km</em></strong><small>según el rango seleccionado</small></article>
            <article><span>Campos cargados</span><strong>{fields.length}</strong><small>capas operacionales</small></article>
          </section>

          <div className="tracker-live-grid">
            <TrackerControl
              isTracking={isTracking} error={error} points={points} totalPoints={totalPoints}
              durationMinutes={durationMinutes} lastPoint={lastPoint} sessionId={sessionId}
              formatTime={formatTime} formatNumber={formatNumber} activeSessions={activeSessions}
              selectedSessionId={selectedLiveSessionId}
              onToggleSession={(id) => { setSelectedLiveSessionId(id); if (id) setFollowSelected(true); }}
              timeWindowMinutes={timeWindowMinutes} onTimeWindowMinutesChange={setTimeWindowMinutes}
              followSelected={followSelected} onFollowSelectedChange={setFollowSelected}
              showOnlySelectedTrack={showOnlySelectedTrack} onShowOnlySelectedTrackChange={setShowOnlySelectedTrack}
              liveAutoRefresh={liveAutoRefresh} onLiveAutoRefreshChange={setLiveAutoRefresh}
              onRefreshNow={refreshNow} dateFrom={dateFrom} dateTo={dateTo}
              onDateFromChange={setDateFrom} onDateToChange={setDateTo} selectedPoints={selectedLivePoints}
            />

            <section className="card card--map-live">
              <div className="map-stage__header">
                <div>
                  <span className="map-stage__eyebrow"><i className="kpi-dot kpi-dot--live" /> Vista operacional</span>
                  <h2>{selectedSession ? selectedSession.machine_name || `Máquina #${selectedSession.machine_id}` : "Toda la flota"}</h2>
                  <p>{selectedSession ? `${selectedSession.driver_name || "Sin chofer asignado"} · ${selectedSession.cost_center_name || "Sin centro de costo"}` : "Selecciona un vehículo para revisar su recorrido."}</p>
                </div>
                <span className="map-stage__updated">{liveAutoRefresh ? "Actualización automática" : "Actualización manual"}</span>
              </div>
              {trackLoadError && <div className="tracker-error" role="alert">{trackLoadError}</div>}
              <div className="map-container">
                <TrackerMap
                  activeSessions={activeSessions} selectedSessionId={selectedLiveSessionId}
                  fields={fields} selectedPoints={selectedLivePoints} followSelected={followSelected}
                  showOnlySelectedTrack={showOnlySelectedTrack}
                  onSelectSession={(id) => { setSelectedLiveSessionId(id); setFollowSelected(true); }}
                  onUserInteract={() => setFollowSelected(false)}
                />
              </div>
            </section>
          </div>

          <section className="card live-points-card live-points-card--redesign">
            <div className="card-header">
              <div><span className="section-kicker">Telemetría</span><div className="card-title">Últimos puntos recibidos</div><div className="card-subtitle">Coordenadas y velocidad del recorrido visible.</div></div>
              <div className="live-points-counter">{liveDisplayPoints.length.toLocaleString("es-CL")} puntos</div>
            </div>
            <div className="telemetry-grid">
              <div className="telemetry-latest">
                <span>Última posición</span>
                <strong>{latestLivePoint ? formatTime(latestLivePoint.timestamp) : "Sin datos"}</strong>
                <p>{latestLivePoint ? `${formatNumber(latestLivePoint.lat)}, ${formatNumber(latestLivePoint.lon)}` : "Selecciona una sesión con actividad."}</p>
              </div>
              <ul className="telemetry-list">
                {liveDisplayPoints.length === 0 && <li className="live-points-empty">No hay puntos en el rango actual.</li>}
                {liveDisplayPoints.slice(-8).reverse().map((point) => (
                  <li key={point.id}>
                    <time>{formatTime(point.timestamp)}</time>
                    <span>{formatNumber(point.lat, 4)}, {formatNumber(point.lon, 4)}</span>
                    <b>{point.speed_mps != null ? `${(point.speed_mps * 3.6).toFixed(1)} km/h` : "—"}</b>
                  </li>
                ))}
              </ul>
            </div>
          </section>
        </main>
      )}


      {view === "userView" && (
        <main className="app-layout app-layout--single app-content-page">
          <UserViewPage />
        </main>
      )}

      {view === "stats" && (
        <main className="app-layout app-layout--single app-content-page">
          <StatsPage />
        </main>
      )}

      {view === "chartsStats" && (
        <main className="app-layout app-layout--single app-content-page">
          <ChartsStatsPage />
        </main>
      )}

      {view === "masters" && (
        <main className="app-layout app-layout--single app-content-page">
          <MastersPage value={mastersView} onChange={setMastersView} />
        </main>
      )}

      {view === "routes" && (
        <main className="app-layout app-layout--single app-content-page">
          <RoutesPage />
        </main>
      )}

      {view === "sessions" && (
        <main className="app-layout app-layout--single app-content-page">
          <SessionsPage />
        </main>
      )}
      </Suspense>
      </div>
    </div>
  );
}
