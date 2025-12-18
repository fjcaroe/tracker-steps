/* eslint-disable @typescript-eslint/no-unused-vars */
// src/components/TrackerControl.tsx
/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useState, useMemo } from "react";
import type { TrackPoint } from "../types";

type CostCenter = { id: number; name: string };

export type ActiveSession = {
  id: string;
  machine_id: number;
  machine_name?: string | null;
  driver_name?: string | null;
  cost_center_name?: string | null;
  started_at: string;
  points_count: number;
};

type TrackerControlProps = {
  isTracking: boolean; // solo lo recibimos, pero esta vista es de monitoreo
  error: string | null;
  points: TrackPoint[];
  totalPoints: number;
  durationMinutes: number | null;
  lastPoint?: TrackPoint | null;
  sessionId: string | null;
  formatTime: (ts: number) => string;
  formatNumber: (n: number | null | undefined, decimals?: number) => string;
  activeSessions: ActiveSession[];
  selectedSessionId: string | null;
  onToggleSession: (id: string) => void;
};

function toRad(deg: number): number {
  return (deg * Math.PI) / 180;
}

function haversineMeters(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number
): number {
  const R = 6371000; // metros
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

const apiBaseUrl =
  ((import.meta.env.VITE_API_BASE_URL as string | undefined) ||
    "http://localhost:8000").replace(/\/+$/, "");

const TrackerControl: React.FC<TrackerControlProps> = ({
  isTracking: _isTracking, // no lo usamos, pero lo dejamos para compat TS
  error,
  points,
  totalPoints,
  durationMinutes,
  sessionId,
  formatTime,
  formatNumber,
  activeSessions,
  selectedSessionId,
  onToggleSession,
}) => {
  const [costCenters, setCostCenters] = useState<CostCenter[]>([]);
  const [filterSearch, setFilterSearch] = useState<string>("");
  const [filterCostCenterId, setFilterCostCenterId] = useState<string>("");

  // Cargar centros de costo para el filtro
  useEffect(() => {
    const loadCostCenters = async () => {
      try {
        const ccRes = await fetch(`${apiBaseUrl}/cost_centers`);
        if (ccRes.ok) setCostCenters(await ccRes.json());
      } catch (err) {
        console.error("Error cargando centros de costo", err);
      }
    };

    loadCostCenters();
  }, []);

  // ---- stats básicos de esta unidad (para el pie) ----
  const totalDistanceM = useMemo(() => {
    if (!points || points.length < 2) return 0;
    let dist = 0;
    for (let i = 1; i < points.length; i++) {
      const p1 = points[i - 1];
      const p2 = points[i];
      dist += haversineMeters(p1.lat, p1.lon, p2.lat, p2.lon);
    }
    return dist;
  }, [points]);

  const avgSpeedKmh =
    durationMinutes && durationMinutes > 0
      ? (totalDistanceM / 1000) / (durationMinutes / 60)
      : 0;

  // ---- filtro de sesiones activas (flota completa) ----
  const filteredActiveSessions = useMemo(() => {
    const q = filterSearch.trim().toLowerCase();

    return activeSessions.filter((s) => {
      // filtro por centro de costo (select)
      if (filterCostCenterId && s.cost_center_name) {
        const cc = costCenters.find(
          (c) => c.id === Number(filterCostCenterId)
        );
        if (cc && s.cost_center_name !== cc.name) {
          return false;
        }
      }

      if (!q) return true;

      const haystack = [
        s.machine_name || `Máquina #${s.machine_id}`,
        s.driver_name || "",
        s.cost_center_name || "",
      ]
        .join(" ")
        .toLowerCase();

      return haystack.includes(q);
    });
  }, [activeSessions, filterSearch, filterCostCenterId, costCenters]);

  const hasActive = filteredActiveSessions.length > 0;

  return (
    <section className="card">
      <div className="card-header">
        <div>
          <div className="card-title">Seguimiento en vivo</div>
          <div className="card-subtitle">
            Monitorea en tiempo real las máquinas activas. Filtra por centro de
            costo o chofer y toca un vehículo para enfocarlo en el mapa.
          </div>
        </div>
        <div className="tracker-status">
          <div
            className={`status-dot ${hasActive ? "on" : ""}`}
            aria-hidden="true"
          />
          <div className="tracker-status-text">
            {hasActive ? (
              <span className="tracker-status-main">
                {filteredActiveSessions.length} vehículo
                {filteredActiveSessions.length > 1 ? "s" : ""} en seguimiento
              </span>
            ) : (
              <span className="tracker-status-main">
                Sin máquinas en seguimiento
              </span>
            )}
          </div>
        </div>
      </div>

      {error && (
        <div className="tracker-error" style={{ marginBottom: 8 }}>
          ⚠️ {error}
        </div>
      )}

      {/* SOLO flota en tiempo real: usamos todo el ancho para la lista */}
      <div className="live-config-grid live-config-grid--single">
        <div className="live-config-column">
          <div className="live-active-sessions">
            <div className="live-active-header">
              <div className="live-active-title">
                Vehículos en circulación ({filteredActiveSessions.length})
              </div>
              <div className="live-active-filters">
                <input
                  type="search"
                  className="form-input live-active-search"
                  placeholder="Filtrar por máquina, chofer o centro…"
                  value={filterSearch}
                  onChange={(e) => setFilterSearch(e.target.value)}
                />
                <select
                  className="form-select live-active-cc-filter"
                  value={filterCostCenterId}
                  onChange={(e) => setFilterCostCenterId(e.target.value)}
                >
                  <option value="">Todos los centros</option>
                  {costCenters.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {filteredActiveSessions.length === 0 ? (
              <div className="live-active-empty">
                No hay máquinas con sesiones abiertas que coincidan con el
                filtro.
              </div>
            ) : (
              <ul className="live-active-list">
                {filteredActiveSessions.map((s) => {
                  const isSelected = selectedSessionId === s.id;
                  return (
                    <li
                      key={s.id}
                      className={
                        "live-active-item" +
                        (isSelected ? " live-active-item--selected" : "")
                      }
                      onClick={() => onToggleSession(s.id)}
                    >
                      <div className="live-active-main">
                        <span className="live-active-machine">
                          {s.machine_name || `Máquina #${s.machine_id}`}
                        </span>
                        <span className="live-active-badge">
                          {s.points_count} pts
                        </span>
                      </div>
                      <div className="live-active-meta">
                        <span>{s.driver_name || "Chofer no asignado"}</span>
                        <span>
                          {s.cost_center_name ||
                            "Centro de costo no asignado"}
                        </span>
                      </div>
                      <div className="live-active-meta2">
                        Inicio:{" "}
                        {new Date(s.started_at).toLocaleTimeString("es-CL", {
                          hour12: false,
                        })}
                      </div>
                      {isSelected && (
                        <div className="live-active-selected-hint">
                          Enfocado en el mapa
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      </div>

      {/* Lista de puntos en vivo (solo de esta unidad, para debug fino) */}
      <div className="live-points-panel">
        <div className="live-points-header">
          Puntos recientes de esta unidad
          <span className="live-points-counter">
            {points.length} en total · mostrando últimos{" "}
            {Math.min(points.length, 50)}
          </span>
        </div>

        <div className="live-points-list">
          <ul>
            {points.length === 0 && (
              <li className="live-points-empty">
                Esta unidad no tiene puntos recientes.
              </li>
            )}

            {points
              .slice(-50)
              .slice()
              .reverse()
              .map((p) => (
                <li key={p.id} className="live-points-item">
                  <span className="live-points-time">
                    {formatTime(p.timestamp)}
                  </span>
                  <span className="live-points-coords">
                    lat {formatNumber(p.lat)}, lon {formatNumber(p.lon)}
                  </span>
                  {p.speed != null && !Number.isNaN(p.speed) && (
                    <span className="live-points-speed">
                      {(p.speed * 3.6).toFixed(1)} km/h
                    </span>
                  )}
                </li>
              ))}
          </ul>
        </div>

        {/* mini resumen al pie (no ocupa otra columna) */}
        {sessionId && (
          <div className="live-points-footer">
            <span>
              Sesión local: <strong>{sessionId}</strong> ·{" "}
              {totalPoints ?? points.length} pts ·{" "}
              {(totalDistanceM / 1000).toFixed(2)} km ·{" "}
              {avgSpeedKmh ? `${avgSpeedKmh.toFixed(1)} km/h` : "—"} prom.
            </span>
          </div>
        )}
      </div>
    </section>
  );
};

export default TrackerControl;
