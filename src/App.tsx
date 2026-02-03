// src/App.tsx
import { useEffect, useState } from "react";
import AppHeader from "./components/AppHeader";
import TrackerControl from "./components/TrackerControl";
import TrackerMap from "./components/TrackerMap";
import SessionsPage from "./pages/SessionsPage";
import RoutesPage from "./pages/RoutesPage";
import UserViewPage from "./pages/UserViewPage";
import StatsPage from "./pages/StatsPage";
import ChartsStatsPage from "./pages/ChartsStatsPage";
import MastersPage, { type MastersView } from "./pages/MastersPage";
import { useTracker, type TrackerMode } from "./hooks/useTracker";
import LoginPage from "./pages/LoginPage";
import { useAuthWeb } from "./services/AuthContext";
import { apiJson, setApiAuthToken } from "./services/http";
import type { TrackPoint } from "./types";

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

  // 👇 sub-vista interna para Maestros
  const [mastersView, setMastersView] = useState<MastersView>("drivers");

  const [mode] = useState<TrackerMode>("machine");
  const [activeSessions, setActiveSessions] = useState<ActiveSession[]>([]);
  const [selectedLiveSessionId, setSelectedLiveSessionId] = useState<string | null>(null);
  const [fields, setFields] = useState<FieldPolygon[]>([]);
  const [isMapFullscreen, setIsMapFullscreen] = useState(false);
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

  const MAX_DRAW_POINTS_NORMAL = 8000;
  const MAX_DRAW_POINTS_FULLSCREEN = 20000;

  useEffect(() => {
    if (!selectedLiveSessionId) {
      setSelectedLivePoints([]);
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
              speed: it.speed_mps ?? null,
            };
          })
          .sort((a, b) => a.timestamp - b.timestamp);

        const cap = isMapFullscreen ? MAX_DRAW_POINTS_FULLSCREEN : MAX_DRAW_POINTS_NORMAL;
        const sliced = norm.length > cap ? downsampleStride(norm, cap) : norm;

        if (mounted) setSelectedLivePoints(sliced);

        // 🔎 si no hay puntos, avisa (esto explica el “no se inmuta”)
        if (mounted && sliced.length === 0) {
          setTrackLoadError(
            "La sesión no tiene puntos en el rango actual. Prueba 'Últ. 24h' o 'Últ. 7 días'."
          );
        }
      } catch (err: any) {
        console.error("Error cargando track", err);
        if (mounted) {
          setSelectedLivePoints([]);
          setTrackLoadError(err?.message || "Error cargando track (ver consola).");
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
    isMapFullscreen,
  ]);

  function downsampleStride<T>(arr: T[], max: number): T[] {
    if (arr.length <= max) return arr;
    const step = Math.ceil(arr.length / max);
    const out: T[] = [];
    for (let i = 0; i < arr.length; i += step) out.push(arr[i]);
    return out;
  }

  useEffect(() => {
    if (!isMapFullscreen) return;

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setIsMapFullscreen(false);
    };

    window.addEventListener("keydown", onKeyDown);
    document.body.style.overflow = "hidden";

    return () => {
      window.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = "";
    };
  }, [isMapFullscreen]);

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
    <div className={`app-shell ${view === "live" ? "app-shell--wide" : ""}`}>
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
            Seguimiento
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

          {/* ✅ NUEVO: Maestros al lado de Gráficos */}
          <button
            type="button"
            className={`app-nav-button ${view === "masters" ? "active" : ""}`}
            onClick={() => setView("masters")}
          >
            Maestros
          </button>
        </div>

        <div className="app-nav-secondary">
          <label className="app-nav-secondary-label">Administración</label>
          {/* ✅ Se deja solo Sesiones históricas aquí (los maestros ya no van en este dropdown) */}
          <select
            className="app-nav-select"
            value={view === "sessions" ? "sessions" : ""}
            onChange={(e) => {
              const next = e.target.value as View;
              if (next) setView(next);
            }}
          >
            <option value="">Seleccionar módulo…</option>
            <option value="sessions">Sesiones históricas</option>
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
            onToggleSession={(id: string | null) => {
              setSelectedLiveSessionId(id);
              if (id) setFollowSelected(true);
            }}
            timeWindowMinutes={timeWindowMinutes}
            onTimeWindowMinutesChange={setTimeWindowMinutes}
            followSelected={followSelected}
            onFollowSelectedChange={setFollowSelected}
            showOnlySelectedTrack={showOnlySelectedTrack}
            onShowOnlySelectedTrackChange={setShowOnlySelectedTrack}
            liveAutoRefresh={liveAutoRefresh}
            onLiveAutoRefreshChange={setLiveAutoRefresh}
            onRefreshNow={refreshNow}
            dateFrom={dateFrom}
            dateTo={dateTo}
            onDateFromChange={setDateFrom}
            onDateToChange={setDateTo}
            selectedPoints={selectedLivePoints}
          />

          <section className={`card card--map-live ${isMapFullscreen ? "is-fullscreen" : ""}`}>
            <div className="card-header card-header--with-actions">
              <div>
                <div className="card-title">Mapa en tiempo real</div>
                <div className="card-subtitle">
                  Recorridos de todas las máquinas activas, con polígonos de campos.
                </div>
              </div>
            </div>
            {trackLoadError && (
              <div className="tracker-error" style={{ margin: "8px 14px 0" }}>
                ⚠️ {trackLoadError}
              </div>
            )}
            <div className="map-container">
              <TrackerMap
                key={`${selectedLiveSessionId ?? "all"}-${showOnlySelectedTrack ? "solo" : "all"}`}

                activeSessions={activeSessions}
                selectedSessionId={selectedLiveSessionId}
                fields={fields}
                selectedPoints={selectedLivePoints}
                followSelected={followSelected}
                showOnlySelectedTrack={showOnlySelectedTrack}
                onUserInteract={() => setFollowSelected(false)}
              />
            </div>
          </section>

          {/* ✅ Panel de puntos: debajo del mapa */}
          <section className="card live-points-card">
            {(() => {
              const hasSelected = Boolean(selectedLiveSessionId);
              const effectivePoints = hasSelected ? (selectedLivePoints ?? []) : (points ?? []);

              const totalDistanceM = (() => {
                if (effectivePoints.length < 2) return 0;
                let dist = 0;
                for (let i = 1; i < effectivePoints.length; i++) {
                  const p1 = effectivePoints[i - 1];
                  const p2 = effectivePoints[i];
                  dist += haversineMeters(p1.lat, p1.lon, p2.lat, p2.lon);
                }
                return dist;
              })();

              const avgSpeedKmh =
                durationMinutes && durationMinutes > 0
                  ? (totalDistanceM / 1000) / (durationMinutes / 60)
                  : 0;

              return (
                <>
                  <div className="card-header">
                    <div>
                      <div className="card-title">Puntos recientes</div>
                      <div className="card-subtitle">
                        {hasSelected ? "De la sesión seleccionada." : "De la sesión local (debug)."}
                      </div>
                    </div>

                    <div className="live-points-counter">
                      {effectivePoints.length} en total · mostrando últimos{" "}
                      {Math.min(effectivePoints.length, 50)}
                    </div>
                  </div>

                  <div className="live-points-panel">
                    <div className="live-points-list">
                      <ul>
                        {effectivePoints.length === 0 && (
                          <li className="live-points-empty">No hay puntos para mostrar.</li>
                        )}

                        {effectivePoints
                          .slice(-50)
                          .slice()
                          .reverse()
                          .map((p: any) => {
                            const speedMps = (p.speed ?? p.speed_mps) as number | null | undefined;

                            return (
                              <li key={p.id} className="live-points-item">
                                <span className="live-points-time">{formatTime(p.timestamp)}</span>
                                <span className="live-points-coords">
                                  lat {formatNumber(p.lat)}, lon {formatNumber(p.lon)}
                                </span>

                                {speedMps != null && Number.isFinite(speedMps) && (
                                  <span className="live-points-speed">
                                    {(speedMps * 3.6).toFixed(1)} km/h
                                  </span>
                                )}
                              </li>
                            );
                          })}
                      </ul>
                    </div>

                    {(sessionId || selectedLiveSessionId) && (
                      <div className="live-points-footer">
                        <span>
                          {hasSelected ? (
                            <>
                              Sesión seleccionada: <strong>{selectedLiveSessionId}</strong>
                            </>
                          ) : (
                            <>
                              Sesión local: <strong>{sessionId}</strong>
                            </>
                          )}{" "}
                          · {totalPoints ?? points.length} pts · {(totalDistanceM / 1000).toFixed(2)} km ·{" "}
                          {avgSpeedKmh ? `${avgSpeedKmh.toFixed(1)} km/h` : "—"} prom.
                        </span>
                      </div>
                    )}
                  </div>
                </>
              );
            })()}
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

      {view === "masters" && (
        <main className="app-layout app-layout--single">
          <MastersPage value={mastersView} onChange={setMastersView} />
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
    </div>
  );
}
