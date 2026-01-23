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
  onToggleSession: (id: string | null) => void; 
  timeWindowMinutes: number;
  onTimeWindowMinutesChange: (v: number) => void;
  maxPoints: number;
  onMaxPointsChange: (v: number) => void;
  followSelected: boolean;
  onFollowSelectedChange: (v: boolean) => void;
  showOnlySelectedTrack: boolean;
  onShowOnlySelectedTrackChange: (v: boolean) => void;
  liveAutoRefresh: boolean;
  onLiveAutoRefreshChange: (v: boolean) => void;
  onRefreshNow: () => void;

  dateFrom: string;
  dateTo: string;
  onDateFromChange: (v: string) => void;
  onDateToChange: (v: string) => void;
  selectedPoints: TrackPoint[]; 
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
  timeWindowMinutes,
  onTimeWindowMinutesChange,
  maxPoints,
  onMaxPointsChange,
  followSelected,
  onFollowSelectedChange,
  showOnlySelectedTrack,
  onShowOnlySelectedTrackChange,
  liveAutoRefresh,
  onLiveAutoRefreshChange,
  onRefreshNow,
  dateFrom,
  dateTo,
  onDateFromChange,
  onDateToChange,
  selectedPoints,
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

  function pad2(n: number) {
  return String(n).padStart(2, "0");
}

function toDatetimeLocalValue(d: Date) {
  // datetime-local necesita "YYYY-MM-DDTHH:mm"
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}T${pad2(
    d.getHours()
  )}:${pad2(d.getMinutes())}`;
}

function startOfDay(d: Date) {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
}

const hasCustomRange = Boolean(dateFrom || dateTo);

const effectivePoints = useMemo(() => {
  // En LIVE, si hay sesión seleccionada, queremos ver lo filtrado del backend
  if (selectedSessionId) return selectedPoints ?? [];
  // Si no hay seleccionado, puedes mostrar points (local) o nada
  return points ?? [];
}, [selectedSessionId, selectedPoints, points]);

const applyPreset = (
  preset: "1h" | "6h" | "24h" | "168h" | "today" | "yesterday"
) => {
  const now = new Date();

  if (preset === "today") {
    onDateFromChange(toDatetimeLocalValue(startOfDay(now)));
    onDateToChange(""); // hasta ahora
    return;
  }

  if (preset === "yesterday") {
    const sToday = startOfDay(now);
    const sYesterday = new Date(sToday);
    sYesterday.setDate(sYesterday.getDate() - 1);

    onDateFromChange(toDatetimeLocalValue(sYesterday));
    onDateToChange(toDatetimeLocalValue(sToday));
    return;
  }

  const mins =
    preset === "1h" ? 60 :
    preset === "6h" ? 360 :
    preset === "24h" ? 1440 :
    10080; // "168h" = 7 días

  const from = new Date(now.getTime() - mins * 60_000);
  onDateFromChange(toDatetimeLocalValue(from));
  onDateToChange(""); // hasta ahora
};


const clearRange = () => {
  onDateFromChange("");
  onDateToChange("");
};

  // ---- stats básicos de esta unidad (para el pie) ----
  const totalDistanceM = useMemo(() => {
    if (!effectivePoints || effectivePoints.length < 2) return 0;
    let dist = 0;
    for (let i = 1; i < effectivePoints.length; i++) {
      const p1 = effectivePoints[i - 1];
      const p2 = effectivePoints[i];
      dist += haversineMeters(p1.lat, p1.lon, p2.lat, p2.lon);
    }
    return dist;
  }, [effectivePoints]);

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
            <span className="tracker-status-main">Sin máquinas en seguimiento</span>
          )}
        </div>
      </div>
    </div>

    {error && (
      <div className="tracker-error" style={{ marginBottom: 8 }}>
        ⚠️ {error}
      </div>
    )}

    {/* Controles de visualización (anti-maraña) */}
  <div className="live-toolbar">
  <div className="live-toolbar__row">
    <button
      type="button"
      className={`app-nav-button ${liveAutoRefresh ? "active" : ""}`}
      onClick={() => onLiveAutoRefreshChange(!liveAutoRefresh)}
      title="Si está ON, el mapa/puntos se actualizan automáticamente"
    >
      {liveAutoRefresh ? "En tiempo real: ON" : "En tiempo real: OFF"}
    </button>

    <button type="button" className="app-nav-button" onClick={onRefreshNow}>
      Actualizar
    </button>

    <div className="live-toolbar__spacer" />

    <div className="live-presets">

      <button type="button" className="app-nav-button" onClick={() => applyPreset("1h")}>
        Últ. 1h
      </button>
      <button type="button" className="app-nav-button" onClick={() => applyPreset("6h")}>
        Últ. 6h
      </button>
      <button type="button" className="app-nav-button" onClick={() => applyPreset("24h")}>
        Últ. 24h
      </button>
      <button type="button" className="app-nav-button" onClick={() => applyPreset("168h")}>
        Últ. 7 días
      </button>
      <button type="button" className="app-nav-button" onClick={() => applyPreset("today")}>
        Hoy
      </button>
      <button type="button" className="app-nav-button" onClick={() => applyPreset("yesterday")}>
        Ayer
      </button>
      <button
        type="button"
        className="app-nav-button"
        onClick={clearRange}
        disabled={!hasCustomRange}
        title="Vuelve al modo ventana (sin rango definido)"
      >
        Limpiar rango
      </button>
    </div>


  <div className="live-toolbar__grid">
    <div className="form-field">
      <div className="form-label">Desde</div>
      <input
        type="datetime-local"
        className="form-input"
        value={dateFrom}
        onChange={(e) => onDateFromChange(e.target.value)}
      />
    </div>

    <div className="form-field">
      <div className="form-label">Hasta</div>
      <input
        type="datetime-local"
        className="form-input"
        value={dateTo}
        onChange={(e) => onDateToChange(e.target.value)}
        placeholder="(vacío = ahora)"
      />
      <div className="form-hint">
        Si “Hasta” está vacío, se considera “Ahora”.
      </div>
    </div>

    <div className="form-field">
      <div className="form-label">Ventana rápida</div>
      <select
        className="form-select"
        value={timeWindowMinutes}
        onChange={(e) => onTimeWindowMinutesChange(Number(e.target.value))}
        disabled={hasCustomRange}  // ✅ coherencia: si hay rango, la ventana no aplica
        title={hasCustomRange ? "Limpia el rango para usar ventana rápida" : ""}
      >
        <option value={60}>Últ. 1 hora</option>
        <option value={360}>Últ. 6 horas</option>
        <option value={1440}>Últ. 24 horas</option>
        <option value={1080}>Últ. 7 días</option>
      </select>
    </div>

    <div className="form-field">
      <div className="form-label">Máximo de puntos</div>
      <select
        className="form-select"
        value={maxPoints}
        onChange={(e) => onMaxPointsChange(Number(e.target.value))}
      >
        <option value={2000}>2000</option>
        <option value={5000}>5000</option>
        <option value={10000}>10000</option>
        <option value={15000}>15000</option>
      </select>
    </div>
  </div>

  <div className="live-toolbar__toggles">
    <label className="live-toggle">
      <input
        type="checkbox"
        checked={followSelected}
        onChange={(e) => onFollowSelectedChange(e.target.checked)}
        disabled={!selectedSessionId}
      />
      Seguir seleccionado
    </label>

    <label className="live-toggle">
      <input
        type="checkbox"
        checked={showOnlySelectedTrack}
        onChange={(e) => onShowOnlySelectedTrackChange(e.target.checked)}
        disabled={!selectedSessionId}
      />
      Mostrar solo seleccionado
    </label>

    {!selectedSessionId && (
      <div className="live-toolbar__hint">
        Selecciona un vehículo para habilitar seguimiento y vista exclusiva.
      </div>
    )}
  </div>
</div>


      <div className="live-visual-row" style={{ display: "grid", gap: 8 }}>
        
        <div className="form-field">
          
          <div className="form-label">Ventana de tiempo</div>
          <select
            className="form-select"
            value={timeWindowMinutes}
            onChange={(e) => onTimeWindowMinutesChange(Number(e.target.value))}
          >
            <option value={2000}>2000</option>
            <option value={5000}>5000</option>
            <option value={10000}>10000</option>
            <option value={15000}>15000</option>
          </select>
        </div>

        <div className="form-field">
          <div className="form-label">Máximo de puntos</div>
          <select
            className="form-select"
            value={maxPoints}
            onChange={(e) => onMaxPointsChange(Number(e.target.value))}
          >
              <option value={2000}>2000</option>
              <option value={5000}>5000</option>
              <option value={10000}>10000</option>
              <option value={15000}>15000</option>
          </select>
        </div>
      </div>

      <div
        className="live-visual-toggles"
        style={{
          display: "flex",
          gap: 12,
          flexWrap: "wrap",
          marginTop: 8,
          fontSize: "0.8rem",
          color: "#374151",
        }}
      >
        <label style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
          <input
            type="checkbox"
            checked={followSelected}
            onChange={(e) => onFollowSelectedChange(e.target.checked)}
          />
          Seguir seleccionado
        </label>

        <label style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
          <input
            type="checkbox"
            checked={showOnlySelectedTrack}
            onChange={(e) => onShowOnlySelectedTrackChange(e.target.checked)}
          />
          Mostrar solo seleccionado
        </label>
      </div>
    </div>

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
              No hay máquinas con sesiones abiertas que coincidan con el filtro.
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
                      <span className="live-active-badge">{s.points_count} pts</span>
                    </div>

                    <div className="live-active-meta">
                      <span>{s.driver_name || "Chofer no asignado"}</span>
                      <span>
                        {s.cost_center_name || "Centro de costo no asignado"}
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
          {points.length} en total · mostrando últimos {Math.min(points.length, 50)}
        </span>
      </div>

      <div className="live-points-list">
        <ul>
          {points.length === 0 && (
            <li className="live-points-empty">Esta unidad no tiene puntos recientes.</li>
          )}

          {effectivePoints
            .slice(-50)
            .slice()
            .reverse()
            .map((p) => (
              <li key={p.id} className="live-points-item">
                <span className="live-points-time">{formatTime(p.timestamp)}</span>
                <span className="live-points-coords">
                  lat {formatNumber(p.lat)}, lon {formatNumber(p.lon)}
                </span>
                {p.speed_mps != null && !Number.isNaN(p.speed_mps) && (
                  <span className="live-points-speed">
                    {(p.speed_mps * 3.6).toFixed(1)} km/h
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
