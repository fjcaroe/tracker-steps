// src/App.tsx
import { useEffect, useState } from "react";
import AppHeader from "./components/AppHeader";
import TrackerControl from "./components/TrackerControl";
import TrackerMap from "./components/TrackerMap";
import SessionsPage from "./pages/SessionsPage";
import DriversPage from "./pages/DriversPage";
import MachinesPage from "./pages/MachinesPage";
import CostCentersPage from "./pages/CostCentersPage";
import FieldsPage from "./pages/FieldsPage";
import RoutesPage from "./pages/RoutesPage";
import UserViewPage from "./pages/UserViewPage";
import StatsPage from "./pages/StatsPage";
import ChartsStatsPage from "./pages/ChartsStatsPage";
import { useTracker, type TrackerMode } from "./hooks/useTracker";
import LoginPage from "./pages/LoginPage";
import { useAuthWeb } from "./services/AuthContext";
import { apiJson, setApiAuthToken } from "./services/http";

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
  | "drivers"
  | "machines"
  | "costCenters"
  | "fields"
  | "userView"
  | "stats"
  | "chartsStats";

function formatTime(ts: number) {
  const d = new Date(ts);
  return d.toLocaleTimeString("es-CL", { hour12: false });
}

function formatNumber(n: number | null | undefined, decimals = 5) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return n.toFixed(decimals);
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

  const [view, setView] = useState<View>("userView");
  const [mode] = useState<TrackerMode>("machine");
  const [activeSessions, setActiveSessions] = useState<ActiveSession[]>([]);
  const [selectedLiveSessionId, setSelectedLiveSessionId] = useState<string | null>(null);
  const [fields, setFields] = useState<FieldPolygon[]>([]);

  type LivePoint = { lat: number; lon: number; ts: string };

  const [selectedLivePoints, setSelectedLivePoints] = useState<LivePoint[]>([]);

  useEffect(() => {
    if (!selectedLiveSessionId) {
      setSelectedLivePoints([]);
      return;
    }

    let mounted = true;

    const loadPoints = async () => {
      try {
        // 👇 AJUSTA el endpoint al tuyo real
        const pts = await apiJson<LivePoint[]>(
          `/sessions/${selectedLiveSessionId}/points`
        );
        if (mounted) setSelectedLivePoints(pts);
      } catch {
        if (mounted) setSelectedLivePoints([]);
      }
    };


    loadPoints();
    const id = window.setInterval(loadPoints, 5000);

    return () => {
      mounted = false;
      window.clearInterval(id);
    };
  }, [selectedLiveSessionId]);

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
        setSelectedLiveSessionId((prev) =>
          prev && !data.some((s) => s.id === prev) ? null : prev
        );
      } catch (err) {
        console.error("Error cargando sesiones activas", err);
        if (mounted) setActiveSessions([]);
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

  return (
    <div className="app-shell">
      <AppHeader />

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "8px 14px",
        }}
      >
        <div style={{ fontWeight: 800 }}>
          {user?.full_name ? `Sesión: ${user.full_name}` : "Sesión activa"}
        </div>
        <button type="button" className="app-nav-button" onClick={logout}>
          Cerrar sesión
        </button>
      </div>

      <nav className="app-nav">
        <div className="app-nav-primary">
          <button
            type="button"
            className={`app-nav-button ${view === "userView" ? "active" : ""}`}
            onClick={() => setView("userView")}
          >
            Vista usuario
          </button>

          <button
            type="button"
            className={`app-nav-button ${view === "live" ? "active" : ""}`}
            onClick={() => setView("live")}
          >
            Seguimiento en vivo
          </button>

          <button
            type="button"
            className={`app-nav-button ${view === "routes" ? "active" : ""}`}
            onClick={() => setView("routes")}
          >
            Odómetro
          </button>

          <button
            type="button"
            className={`app-nav-button ${view === "stats" ? "active" : ""}`}
            onClick={() => setView("stats")}
          >
            Estadísticas
          </button>

          <button
            type="button"
            className={`app-nav-button ${view === "chartsStats" ? "active" : ""}`}
            onClick={() => setView("chartsStats")}
          >
            Gráficos
          </button>
        </div>

        <div className="app-nav-secondary">
          <label className="app-nav-secondary-label">Administración</label>
          <select
            className="app-nav-select"
            value={
              ["sessions", "drivers", "machines", "costCenters", "fields", "chartsStats"].includes(view)
                ? view
                : ""
            }
            onChange={(e) => {
              const next = e.target.value as View;
              if (next) setView(next);
            }}
          >
            <option value="">Seleccionar módulo…</option>
            <option value="sessions">Sesiones históricas</option>
            <option value="drivers">Choferes</option>
            <option value="machines">Máquinas</option>
            <option value="costCenters">Centros de costo</option>
            <option value="fields">Campos / Polígonos</option>
            <option value="chartsStats">Dashboards (Gráficos)</option>
          </select>
        </div>
      </nav>

      {view === "live" && (
        <main className="app-layout app-layout--live">
          <TrackerControl
            isTracking={isTracking}
            error={error}
            points={points}
            totalPoints={totalPoints}
            durationMinutes={durationMinutes}
            lastPoint={lastPoint}
            sessionId={sessionId}
            formatTime={formatTime}
            formatNumber={formatNumber}
            activeSessions={activeSessions}
            selectedSessionId={selectedLiveSessionId}
            onToggleSession={(id: string | null) =>
              setSelectedLiveSessionId((prev) => (prev === id ? null : id))
            }
          />

          <section className="card card--map-live">
            <div className="card-header">
              <div>
                <div className="card-title">Mapa en tiempo real</div>
                <div className="card-subtitle">
                  Recorridos de todas las máquinas activas, con polígonos de campos.
                </div>
              </div>
            </div>
            <TrackerMap
              activeSessions={activeSessions}
              selectedSessionId={selectedLiveSessionId}
              fields={fields}
              selectedPoints={selectedLivePoints}   // ✅ nuevo
            />

          </section>
        </main>
      )}

      {view === "userView" && (
        <main className="app-layout app-layout--single">
          <UserViewPage />
        </main>
      )}

      {view === "stats" && (
        <main className="app-layout app-layout--single">
          <StatsPage />
        </main>
      )}

      {view === "chartsStats" && (
        <main className="app-layout app-layout--single">
          <ChartsStatsPage />
        </main>
      )}
      {view === "routes" && (
        <main className="app-layout app-layout--single">
          <RoutesPage />
        </main>
      )}

      {view === "sessions" && (
        <main className="app-layout app-layout--single">
          <SessionsPage />
        </main>
      )}

      {view === "drivers" && (
        <main className="app-layout app-layout--single">
          <DriversPage />
        </main>
      )}

      {view === "machines" && (
        <main className="app-layout app-layout--single">
          <MachinesPage />
        </main>
      )}

      {view === "costCenters" && (
        <main className="app-layout app-layout--single">
          <CostCentersPage />
        </main>
      )}

      {view === "fields" && (
        <main className="app-layout app-layout--single">
          <FieldsPage />
        </main>
      )}
    </div>
  );
}
