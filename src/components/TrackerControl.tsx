/* eslint-disable @typescript-eslint/no-unused-vars */
// src/components/TrackerControl.tsx
/* eslint-disable @typescript-eslint/no-explicit-any */
import {  useState, useMemo } from "react";
import type { TrackPoint } from "../types";


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

   const [machineQuery, setMachineQuery] = useState<string>("");
  const [driverQuery, setDriverQuery] = useState<string>(""); // opcional: para filtrar por chofer
  const [selectedMachineIds, setSelectedMachineIds] = useState<number[]>([]);
  const [machineDropdownOpen, setMachineDropdownOpen] = useState<boolean>(false);


 const activeMachineOptions = useMemo(() => {
    const map = new Map<number, { machine_id: number; label: string }>();

    for (const s of activeSessions) {
      const label = s.machine_name?.trim() || `Máquina #${s.machine_id}`;
      if (!map.has(s.machine_id)) {
        map.set(s.machine_id, { machine_id: s.machine_id, label });
      }
    }

    return Array.from(map.values()).sort((a, b) => a.label.localeCompare(b.label, "es"));
  }, [activeSessions]);

     const addMachineToSelection = (machineId: number) => {
  setSelectedMachineIds((prev) => (prev.includes(machineId) ? prev : [...prev, machineId]));
  setMachineQuery("");
  setMachineDropdownOpen(false);

  const sess = activeSessions
    .filter((s) => s.machine_id === machineId)
    .sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime())[0];

  if (sess) onToggleSession(sess.id);
};


const removeMachineFromSelection = (machineId: number) => {
  setSelectedMachineIds((prev) => {
    const next = prev.filter((id) => id !== machineId);

    // Si la sesión enfocada pertenece a la máquina removida, mover foco a otra (o limpiar)
    if (selectedSessionId) {
      const selectedSess = activeSessions.find((s) => s.id === selectedSessionId);
      if (selectedSess?.machine_id === machineId) {
        const fallbackMachineId = next[next.length - 1]; // última seleccionada
        if (fallbackMachineId != null) {
          const fallbackSess = activeSessions
            .filter((s) => s.machine_id === fallbackMachineId)
            .sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime())[0];

          onToggleSession(fallbackSess ? fallbackSess.id : null);
        } else {
          onToggleSession(null);
        }
      }
    }

    return next;
  });
};


const clearMachineSelection = () => {
  setSelectedMachineIds([]);
  onToggleSession(null);
};


  const machineSuggestions = useMemo(() => {
    const q = machineQuery.trim().toLowerCase();
    const notSelected = activeMachineOptions.filter((m) => !selectedMachineIds.includes(m.machine_id));

    if (!q) return notSelected.slice(0, 12);

    return notSelected
      .filter((m) => m.label.toLowerCase().includes(q) || String(m.machine_id).includes(q))
      .slice(0, 12);
  }, [machineQuery, activeMachineOptions, selectedMachineIds]);



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
  preset === "168h" ? 10080 :
  60;

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
  // Si no hay máquinas seleccionadas, NO mostramos lista
  if (selectedMachineIds.length === 0) return [];

  const dq = driverQuery.trim().toLowerCase();

  return activeSessions.filter((s) => {
    if (!selectedMachineIds.includes(s.machine_id)) return false;

    if (dq) {
      const driver = (s.driver_name || "").toLowerCase();
      if (!driver.includes(dq)) return false;
    }

    return true;
  });
}, [activeSessions, selectedMachineIds, driverQuery]);

   const visitedCostCenters = useMemo(() => {
    const names = (effectivePoints ?? [])
      .map((p: any) => (p?.cost_center_name ? String(p.cost_center_name) : ""))
      .filter(Boolean);

    return Array.from(new Set(names));
  }, [effectivePoints]);

  const hasActive = filteredActiveSessions.length > 0;

return (
  <section className="card">
    <div className="card-header">
      <div>
        <div className="card-title">Seguimiento</div>
       <div className="card-subtitle">
  Monitorea en tiempo real las máquinas activas. Selecciona una o varias máquinas para filtrar y toca un vehículo para enfocarlo en el mapa.
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
   {/* SOLO flota en tiempo real: usamos todo el ancho para la lista */}
    <div className="live-config-grid live-config-grid--single">
      <div className="live-config-column">
        <div className="live-active-sessions">
          <div className="live-active-header">
            <div className="live-active-title">
              Vehículos en circulación ({filteredActiveSessions.length})
            </div>

           <div className="live-active-filters">
  {/* Selector de máquinas activas (autocomplete) */}
  <div className="machine-picker">
    <input
      type="search"
      className="form-input live-active-search"
      placeholder="Buscar máquina activa y presiona Enter para agregar…"
      value={machineQuery}
      onChange={(e) => {
        setMachineQuery(e.target.value);
        setMachineDropdownOpen(true);
      }}
      onFocus={() => setMachineDropdownOpen(true)}
      onBlur={() => {
        // pequeño delay para permitir click en sugerencia
        window.setTimeout(() => setMachineDropdownOpen(false), 120);
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          // si hay una sola sugerencia, agréguela
          if (machineSuggestions.length === 1) addMachineToSelection(machineSuggestions[0].machine_id);
        }
      }}
    />

    {machineDropdownOpen && machineSuggestions.length > 0 && (
      <div className="machine-suggestions">
        {machineSuggestions.map((m) => (
          <button
            key={m.machine_id}
            type="button"
            className="machine-suggestion-item"
            onMouseDown={(ev) => ev.preventDefault()}
            onClick={() => addMachineToSelection(m.machine_id)}
            title="Agregar a filtros"
          >
            {m.label}
          </button>
        ))}
      </div>
    )}
  </div>

  {/* Filtro opcional por chofer (mantiene utilidad sin ensuciar el selector) */}
  <input
    type="search"
    className="form-input live-active-search"
    placeholder="Filtrar por chofer (opcional)…"
    value={driverQuery}
    onChange={(e) => setDriverQuery(e.target.value)}
  />
</div>

{/* Chips de máquinas seleccionadas */}
{selectedMachineIds.length > 0 && (
  <div className="machine-selected-row">
    <div className="machine-selected-label">Seleccionadas:</div>

    <div className="machine-selected-chips">
      {selectedMachineIds.map((id) => {
        const label = activeMachineOptions.find((x) => x.machine_id === id)?.label || `Máquina #${id}`;
        return (
          <span key={id} className="machine-chip">
            {label}
            <button
              type="button"
              className="machine-chip-remove"
              onClick={() => removeMachineFromSelection(id)}
              aria-label={`Quitar ${label}`}
              title="Quitar"
            >
              ×
            </button>
          </span>
        );
      })}

      <button type="button" className="app-nav-button" onClick={clearMachineSelection}>
        Limpiar selección
      </button>
    </div>
  </div>
)}

          </div>

         {selectedMachineIds.length === 0 ? (
  <div className="live-active-empty">
    Selecciona una máquina en el buscador para ver su estado en vivo.
  </div>
) : filteredActiveSessions.length === 0 ? (
  <div className="live-active-empty">
    No hay máquinas en circulación que coincidan con tu selección/filtro.
  </div>
) : (
  <ul className="live-active-list">
    {filteredActiveSessions.map((s) => {
      const isSelected = selectedSessionId === s.id;
      return (
        <li
          key={s.id}
          className={"live-active-item" + (isSelected ? " live-active-item--selected" : "")}
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
{selectedSessionId && (
  <div className="live-selected-cc-card">
    <div className="live-selected-cc-title">Centros de costo recorridos (sesión seleccionada)</div>
    <div className="live-selected-cc-body">
      {visitedCostCenters.length > 0 ? visitedCostCenters.join(" · ") : "—"}
    </div>
  </div>
)}


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
        <option value={10080}>Últ. 7 días</option>
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
