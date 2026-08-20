import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import OperationsMap from "../components/OperationsMap";
import {
  DEMO_EVENTS,
  DEMO_FIELDS,
  DEMO_SESSIONS,
  REGIONS,
  getDemoVehicles,
  type DemoSession,
  type DemoVehicle,
} from "../demo/scenario";
import { apiJson } from "../services/http";
import "./OperationsWorkspace.css";

const AnalyticsCharts = lazy(() => import("./AnalyticsCharts"));
const RegistrationPage = lazy(() => import("./RegistrationPage"));

export type OperationsView = "live" | "routes" | "sessions" | "userView" | "stats" | "chartsStats" | "masters" | "registro";

type ApiEntity = { id: number; name: string };
type ApiField = ApiEntity & { color?: string | null; polygon?: { lat: number; lon: number }[] };
type ApiSession = {
  id: string;
  machine_id: number;
  machine_name?: string | null;
  driver_name?: string | null;
  cost_center_name?: string | null;
  started_at: string;
  ended_at?: string | null;
  status: "open" | "closed";
  points_count: number;
  labor_id?: number | null;
  total_distance_m?: number | null;
  avg_speed_kmh?: number | null;
};

type ApiLabor = { id: number; name: string };

type RealData = {
  machines: ApiEntity[];
  drivers: ApiEntity[];
  costCenters: ApiEntity[];
  fields: ApiField[];
  sessions: ApiSession[];
};

const emptyRealData: RealData = { machines: [], drivers: [], costCenters: [], fields: [], sessions: [] };

// Fila normalizada para el historial: la misma tabla sirve tanto para sesiones demo como reales.
type HistoryRow = {
  id: string;
  startedAtLabel: string;
  startedAtIso: string;
  machine: string;
  driver: string;
  field: string;
  labor: string;
  durationHours: number | null;
  distanceKm: number | null;
  coveredHa: number | null;
  fuelLiters: number | null;
  statusTone: "active" | "completed" | "paused";
  statusText: string;
};

function formatSessionDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("es-CL", { dateStyle: "short", timeStyle: "short" });
}

// Día calendario en hora LOCAL (America/Santiago), no UTC: a las 21:00 en Chile
// (UTC-4) el día en UTC ya es "mañana", así que rebanar el ISO a lo bruto
// desalinea "hoy" con las sesiones recién creadas.
function localDateKey(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function number(value: number, digits = 1) {
  return value.toLocaleString("es-CL", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function statusLabel(status: DemoSession["status"]) {
  if (status === "active") return "En curso";
  if (status === "paused") return "Pausada";
  return "Completada";
}

function vehicleStatusLabel(status: DemoVehicle["status"]) {
  if (status === "working") return "Trabajando";
  if (status === "turning") return "Girando";
  if (status === "returning") return "Regresando";
  return "Detenido";
}

const HISTORY_PAGE_SIZE = 10;
const FLEET_STATUS_OPTIONS: { value: "all" | DemoVehicle["status"]; label: string }[] = [
  { value: "all", label: "Todos los estados" },
  { value: "working", label: "Trabajando" },
  { value: "turning", label: "Girando" },
  { value: "paused", label: "Detenidos" },
  { value: "returning", label: "Regresando" },
];

function DemoControl({
  demoMode,
  onDemoModeChange,
  running,
  onRunningChange,
  speed,
  onSpeedChange,
  regionId,
  onRegionChange,
}: {
  demoMode: boolean;
  onDemoModeChange: (value: boolean) => void;
  running: boolean;
  onRunningChange: (value: boolean) => void;
  speed: number;
  onSpeedChange: (value: number) => void;
  regionId: string;
  onRegionChange: (value: string) => void;
}) {
  return (
    <section className={`demo-console ${demoMode ? "is-active" : ""}`} aria-label="Laboratorio de demostración">
      <div className="demo-console__identity">
        <span className="demo-console__icon">D</span>
        <div><b>Laboratorio demo</b><small>Datos sintéticos · no escribe en producción</small></div>
      </div>
      <label className="ops-switch">
        <input type="checkbox" checked={demoMode} onChange={(event) => onDemoModeChange(event.target.checked)} />
        <span />
        {demoMode ? "Dataset activo" : "Usar datos reales"}
      </label>
      {demoMode && (
        <>
          <label className="demo-region" aria-label="Ubicación / fundo">
            <select value={regionId} onChange={(event) => onRegionChange(event.target.value)}>
              {REGIONS.map((region) => <option key={region.id} value={region.id}>{region.name}</option>)}
            </select>
          </label>
          <button type="button" className="ops-action ops-action--dark" onClick={() => onRunningChange(!running)}>{running ? "Pausar" : "Iniciar"}</button>
          <label className="demo-speed">Velocidad
            <select value={speed} onChange={(event) => onSpeedChange(Number(event.target.value))}>
              <option value={0.5}>0,5×</option><option value={1}>1×</option><option value={3}>3×</option><option value={8}>8×</option>
            </select>
          </label>
        </>
      )}
    </section>
  );
}

function KpiGrid({ sessions, fields }: { sessions: DemoSession[]; fields: typeof DEMO_FIELDS }) {
  const totalDistance = sessions.reduce((sum, session) => sum + session.distanceKm, 0);
  const totalHours = sessions.reduce((sum, session) => sum + session.durationHours, 0);
  const totalArea = sessions.reduce((sum, session) => sum + session.coveredHa, 0);
  const totalFuel = sessions.reduce((sum, session) => sum + session.fuelLiters, 0);
  const hectaresPerHour = totalHours > 0 ? totalArea / totalHours : 0;
  const litersPerHectare = totalArea > 0 ? totalFuel / totalArea : 0;
  return (
    <section className="ops-kpi-grid" aria-label="Indicadores principales">
      <article><span>Máquinas trabajando</span><strong>{sessions.filter((item) => item.status === "active").length}</strong><small><i className="ops-dot is-green" /> escenario operacional</small></article>
      <article><span>Superficie cubierta</span><strong>{number(totalArea)} <em>ha</em></strong><small>{number(hectaresPerHour, 2)} ha por hora</small></article>
      <article><span>Distancia operacional</span><strong>{number(totalDistance)} <em>km</em></strong><small>GPS filtrado y ordenado</small></article>
      <article><span>Consumo específico</span><strong>{number(litersPerHectare, 2)} <em>L/ha</em></strong><small>{fields.length} lotes en seguimiento</small></article>
    </section>
  );
}

export default function OperationsWorkspace({ view }: { view: OperationsView }) {
  const [demoMode, setDemoMode] = useState(true);
  const [running, setRunning] = useState(true);
  const [speed, setSpeed] = useState(1);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [selectedRegionId, setSelectedRegionId] = useState<string>(REGIONS[0].id);
  const [selectedVehicleId, setSelectedVehicleId] = useState<string | null>(null);
  const [followVehicle, setFollowVehicle] = useState(true);
  const [showRows, setShowRows] = useState(true);
  const [showRoadRoute, setShowRoadRoute] = useState(false);
  const [roadRouteStatus, setRoadRouteStatus] = useState<string | null>(null);
  const [fleetQuery, setFleetQuery] = useState("");
  const [fleetStatusFilter, setFleetStatusFilter] = useState<"all" | DemoVehicle["status"]>("all");
  const [historyQuery, setHistoryQuery] = useState("");
  const [historyStatus, setHistoryStatus] = useState<"all" | DemoSession["status"]>("all");
  const [historyPage, setHistoryPage] = useState(1);
  const todayIso = useMemo(() => localDateKey(new Date().toISOString()), []);
  const [historyDateFrom, setHistoryDateFrom] = useState(todayIso);
  const [historyDateTo, setHistoryDateTo] = useState(todayIso);
  const [openMasterCard, setOpenMasterCard] = useState<string | null>(null);
  const [realData, setRealData] = useState<RealData>(emptyRealData);
  const [realStatus, setRealStatus] = useState<"loading" | "ready" | "error">("loading");
  const [realSessions, setRealSessions] = useState<ApiSession[]>([]);
  const [laborsById, setLaborsById] = useState<Record<number, string>>({});
  const [realHistoryStatus, setRealHistoryStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const realHistoryRequestedRef = useRef(false);

  useEffect(() => {
    if (!running || !demoMode) return;
    const id = window.setInterval(() => setElapsedSeconds((value) => value + 1), 1000);
    return () => window.clearInterval(id);
  }, [demoMode, running]);

  useEffect(() => {
    if (!showRoadRoute) return;
    const id = window.setTimeout(() => {
      setRoadRouteStatus((current) => current === "Calculando ruta por caminos…"
        ? "Google Directions no respondió. La capa de pasadas agrícolas continúa disponible."
        : current);
    }, 8000);
    return () => window.clearTimeout(id);
  }, [showRoadRoute]);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setRealStatus("loading");
      try {
        const [machines, drivers, costCenters, fields, sessions] = await Promise.all([
          apiJson<ApiEntity[]>("/machines"),
          apiJson<ApiEntity[]>("/drivers"),
          apiJson<ApiEntity[]>("/cost_centers"),
          apiJson<ApiField[]>("/fields"),
          apiJson<ApiSession[]>("/sessions"),
        ]);
        if (!active) return;
        setRealData({ machines, drivers, costCenters, fields, sessions });
        setRealStatus("ready");
      } catch {
        if (active) setRealStatus("error");
      }
    };
    void load();
    return () => { active = false; };
  }, []);

  // Historial real (sesiones + labores): solo se pide cuando el usuario mira Historial fuera del modo demo.
  useEffect(() => {
    // Carga única (guardada por ref, no por estado) para que el doble-render de
    // React.StrictMode en desarrollo no descarte la respuesta de la primera llamada.
    if (view !== "sessions" || demoMode || realHistoryRequestedRef.current) return;
    realHistoryRequestedRef.current = true;
    const load = async () => {
      setRealHistoryStatus("loading");
      try {
        const [sessionsData, laborsData] = await Promise.all([
          apiJson<ApiSession[]>("/sessions_recent?limit=300"),
          apiJson<ApiLabor[]>("/labors"),
        ]);
        setRealSessions(sessionsData);
        setLaborsById(Object.fromEntries(laborsData.map((l) => [l.id, l.name])));
        setRealHistoryStatus("ready");
      } catch {
        setRealHistoryStatus("error");
        realHistoryRequestedRef.current = false;
      }
    };
    void load();
  }, [view, demoMode]);

  const allVehicles = useMemo(() => getDemoVehicles(elapsedSeconds, speed), [elapsedSeconds, speed]);
  const currentRegion = REGIONS.find((region) => region.id === selectedRegionId) ?? REGIONS[0];
  const regionFields = useMemo(() => DEMO_FIELDS.filter((field) => field.regionId === selectedRegionId), [selectedRegionId]);
  const vehicles = useMemo(() => allVehicles.filter((vehicle) => vehicle.regionId === selectedRegionId), [allVehicles, selectedRegionId]);
  // Sin selección = toda la flota de la región, sin centrar el mapa en ninguna máquina en particular.
  const selectedVehicle = selectedVehicleId ? allVehicles.find((vehicle) => vehicle.id === selectedVehicleId) : undefined;
  const selectedField = selectedVehicle ? DEMO_FIELDS.find((field) => field.id === selectedVehicle.fieldId) : undefined;
  const sessions = DEMO_SESSIONS;

  const handleRegionChange = (nextRegionId: string) => {
    setSelectedRegionId(nextRegionId);
    setSelectedVehicleId(null);
    setFleetQuery("");
    setFleetStatusFilter("all");
  };

  // Seleccionar un vehículo nuevo siempre reactiva "seguir vehículo"; deseleccionar
  // no toca el encuadre del mapa (eso lo maneja OperationsMap por su cuenta).
  const selectVehicle = (id: string | null) => {
    setSelectedVehicleId(id);
    if (id) setFollowVehicle(true);
  };

  const filteredFleet = useMemo(() => vehicles.filter((vehicle) => {
    const query = fleetQuery.trim().toLowerCase();
    const matchesQuery = !query || `${vehicle.name} ${vehicle.driver} ${vehicle.plate}`.toLowerCase().includes(query);
    const matchesStatus = fleetStatusFilter === "all" || vehicle.status === fleetStatusFilter;
    return matchesQuery && matchesStatus;
  }), [vehicles, fleetQuery, fleetStatusFilter]);

  const historyRows: HistoryRow[] = useMemo(() => {
    if (demoMode) {
      return DEMO_SESSIONS.map((s) => ({
        id: s.id, startedAtLabel: s.startedAt, startedAtIso: s.startedAtIso, machine: s.machine, driver: s.driver,
        field: s.field, labor: s.labor, durationHours: s.durationHours, distanceKm: s.distanceKm, coveredHa: s.coveredHa,
        fuelLiters: s.fuelLiters, statusTone: s.status, statusText: statusLabel(s.status),
      }));
    }
    return realSessions.map((s) => {
      const start = new Date(s.started_at).getTime();
      const end = s.ended_at ? new Date(s.ended_at).getTime() : null;
      const durationHours = end && !Number.isNaN(start) ? (end - start) / 3_600_000 : null;
      const distanceKm = s.total_distance_m != null ? s.total_distance_m / 1000 : null;
      return {
        id: s.id, startedAtLabel: formatSessionDateTime(s.started_at), startedAtIso: s.started_at,
        machine: s.machine_name || `Máquina #${s.machine_id}`, driver: s.driver_name || "—",
        field: s.cost_center_name || "—", labor: (s.labor_id != null && laborsById[s.labor_id]) || "—",
        durationHours, distanceKm, coveredHa: null, fuelLiters: null,
        statusTone: s.status === "open" ? "active" : "completed",
        statusText: s.status === "open" ? "En curso" : "Completada",
      };
    });
  }, [demoMode, realSessions, laborsById]);

  const filteredSessions = useMemo(() => historyRows.filter((row) => {
    const query = historyQuery.trim().toLowerCase();
    const matchesQuery = !query || `${row.id} ${row.machine} ${row.driver} ${row.field} ${row.labor}`.toLowerCase().includes(query);
    const matchesStatus = historyStatus === "all" || row.statusTone === historyStatus;
    const dayIso = localDateKey(row.startedAtIso);
    const matchesDate = (!historyDateFrom || dayIso >= historyDateFrom) && (!historyDateTo || dayIso <= historyDateTo);
    return matchesQuery && matchesStatus && matchesDate;
  }), [historyRows, historyQuery, historyStatus, historyDateFrom, historyDateTo]);

  const historyPageCount = Math.max(1, Math.ceil(filteredSessions.length / HISTORY_PAGE_SIZE));
  const clampedHistoryPage = Math.min(historyPage, historyPageCount);
  const pagedSessions = filteredSessions.slice((clampedHistoryPage - 1) * HISTORY_PAGE_SIZE, clampedHistoryPage * HISTORY_PAGE_SIZE);

  const historyFilterKey = `${historyQuery}|${historyStatus}|${historyDateFrom}|${historyDateTo}|${demoMode}`;
  const [prevHistoryFilterKey, setPrevHistoryFilterKey] = useState(historyFilterKey);
  if (prevHistoryFilterKey !== historyFilterKey) {
    setPrevHistoryFilterKey(historyFilterKey);
    if (historyPage !== 1) setHistoryPage(1);
  }

  const control = (
    <DemoControl demoMode={demoMode} onDemoModeChange={setDemoMode} running={running} onRunningChange={setRunning} speed={speed} onSpeedChange={setSpeed} regionId={selectedRegionId} onRegionChange={handleRegionChange} />
  );

  if (view === "registro") {
    return (
      <main className="ops-workspace">
        <Suspense fallback={<div className="view-loader"><span className="view-loader__spinner" />Cargando registro…</div>}>
          <RegistrationPage />
        </Suspense>
      </main>
    );
  }

  if (!demoMode && view !== "sessions" && view !== "masters") {
    return (
      <main className="ops-workspace">
        {control}
        <section className="ops-real-panel">
          <div><span className="section-kicker">Fuente productiva</span><h2>Datos reales de Tracker</h2><p>El modo real permanece separado del laboratorio. No se mezclan sesiones sintéticas con información productiva.</p></div>
          <div className="ops-real-stats">
            <article><b>{realData.machines.length}</b><span>máquinas</span></article>
            <article><b>{realData.drivers.length}</b><span>conductores</span></article>
            <article><b>{realData.fields.length}</b><span>polígonos</span></article>
            <article><b>{realData.sessions.length}</b><span>sesiones</span></article>
          </div>
          <p className={`ops-source-state is-${realStatus}`} role="status" aria-live="polite">{realStatus === "ready" ? "API sincronizada" : realStatus === "loading" ? "Sincronizando API…" : "No fue posible sincronizar; intenta nuevamente."}</p>
        </section>
      </main>
    );
  }

  const mapCard = (compact = false) => (
    <section className={`ops-map-card ${compact ? "is-compact" : ""}`}>
      <header>
        <div>
          <span className="section-kicker">Cartografía operacional · {currentRegion.name}</span>
          <h2>{selectedVehicle && selectedField ? selectedField.name : "Toda la flota"}</h2>
          <p>{selectedVehicle && selectedField ? `${selectedVehicle.driver} · ${selectedField.crop}` : `${vehicles.length} vehículos en esta ubicación · ninguno seleccionado`}</p>
        </div>
        <div className="ops-layer-controls">
          {selectedVehicleId && (
            <button type="button" className={followVehicle ? "is-active" : ""} onClick={() => setFollowVehicle(!followVehicle)} title="Si lo apagas, el mapa deja de recentrarse en el vehículo aunque siga seleccionado (útil para revisar su ruta con calma)">
              {followVehicle ? "Siguiendo vehículo" : "Seguimiento pausado"}
            </button>
          )}
          {selectedVehicleId && <button type="button" onClick={() => selectVehicle(null)}>Toda la flota</button>}
          <button type="button" className={showRows ? "is-active" : ""} onClick={() => setShowRows(!showRows)}>Pasadas</button>
          <button type="button" className={showRoadRoute ? "is-active" : ""} disabled={!selectedField} title={!selectedField ? "Selecciona un vehículo para calcular su ruta" : undefined} onClick={() => { const next = !showRoadRoute; setShowRoadRoute(next); if (!next) setRoadRouteStatus(null); }}>Ruta por caminos</button>
        </div>
      </header>
      {selectedVehicleId && !showRoadRoute && (
        <p className="ops-map-hint">Tip: usa "Ruta por caminos" para ver cómo llegó desde el depósito, y apaga "Siguiendo vehículo" si quieres mirar el recorrido sin que la cámara se mueva.</p>
      )}
      {roadRouteStatus && <div className="ops-map-notice" role="status" aria-live="polite">{roadRouteStatus}</div>}
      <div className="ops-map-frame">
        <OperationsMap fields={regionFields} vehicles={vehicles} selectedVehicleId={selectedVehicleId} onSelectVehicle={selectVehicle} showRows={showRows} showRoadRoute={showRoadRoute} onRoadRouteStatus={setRoadRouteStatus} compact={compact} depot={currentRegion.depot} followVehicle={followVehicle} onUserInteracted={() => setFollowVehicle(false)} />
      </div>
      <footer><span><i className="ops-dot is-lime" /> Pasadas dentro del lote</span><span><i className="ops-line-sample" /> Caminos calculados por Google</span><b>Dataset demostrativo</b></footer>
    </section>
  );

  if (view === "userView") {
    const fieldProgress = regionFields.map((_, index) => 58 + ((index * 11) % 35));
    const completion = Math.round(fieldProgress.reduce((sum, value) => sum + value, 0) / fieldProgress.length);
    return (
      <main className="ops-workspace">
        {control}
        <p className="ops-view-intro">Lectura ejecutiva de toda la operación (las {REGIONS.length} ubicaciones). El mapa y la flota de abajo muestran solo <b>{currentRegion.name}</b>; cambia de ubicación arriba para ver otro fundo.</p>
        <KpiGrid sessions={sessions} fields={DEMO_FIELDS} />
        {(() => {
          const attention = allVehicles
            .filter((v) => v.fuelPct < 35 || v.status === "paused" || v.status === "returning")
            .map((v) => ({
              vehicle: v,
              reason: v.fuelPct < 35 ? `Combustible bajo · ${v.fuelPct.toFixed(0)}%` : v.status === "paused" ? "Detenida" : "Regresando a base",
            }))
            .slice(0, 5);
          if (attention.length === 0) return null;
          return (
            <section className="ops-attention-panel" aria-label="Atención requerida">
              <header><span className="section-kicker">Atención requerida</span><h2>{attention.length} máquina{attention.length === 1 ? "" : "s"} para revisar hoy, en toda la empresa</h2></header>
              <div className="ops-attention-list">
                {attention.map(({ vehicle, reason }) => {
                  const region = REGIONS.find((r) => r.id === vehicle.regionId);
                  return (
                    <button type="button" key={vehicle.id} onClick={() => { if (region) handleRegionChange(region.id); selectVehicle(vehicle.id); }}>
                      <i className="ops-dot is-warning" />
                      <span><b>{vehicle.name}</b><small>{vehicle.driver} · {region?.name}</small></span>
                      <em>{reason}</em>
                    </button>
                  );
                })}
              </div>
            </section>
          );
        })()}
        <section className="ops-region-strip" aria-label="Ubicaciones de la empresa">
          {REGIONS.map((region) => {
            const regionVehicleCount = allVehicles.filter((v) => v.regionId === region.id).length;
            const regionFieldCount = DEMO_FIELDS.filter((f) => f.regionId === region.id).length;
            return (
              <button type="button" key={region.id} className={region.id === selectedRegionId ? "is-active" : ""} onClick={() => handleRegionChange(region.id)}>
                <b>{region.name}</b>
                <span>{regionVehicleCount} máquinas · {regionFieldCount} predios</span>
              </button>
            );
          })}
        </section>
        <div className="ops-summary-grid">
          {mapCard(true)}
          <section className="ops-side-card"><header><span className="section-kicker">Jornada</span><h2>Avance operacional</h2></header>
            <div className="ops-progress-ring" style={{ "--progress": `${Math.min(100, completion)}%` } as React.CSSProperties}><strong>{completion}%</strong><span>cobertura planificada</span></div>
            <div className="ops-progress-list">{regionFields.map((field, index) => <div key={field.id}><span>{field.name}</span><b>{fieldProgress[index]}%</b><i><em style={{ width: `${fieldProgress[index]}%` }} /></i></div>)}</div>
          </section>
        </div>
        <div className="ops-lower-grid">
          <section className="ops-panel"><header><span className="section-kicker">Flota · {currentRegion.name}</span><h2>Actividad por máquina</h2></header><div className="ops-fleet-rows">{vehicles.map((vehicle) => <button key={vehicle.id} type="button" className={selectedVehicleId === vehicle.id ? "is-selected" : ""} onClick={() => selectVehicle(selectedVehicleId === vehicle.id ? null : vehicle.id)}><i className="ops-vehicle-avatar">T</i><span><b>{vehicle.name}</b><small>{DEMO_FIELDS.find((field) => field.id === vehicle.fieldId)?.name}</small></span><em>{vehicle.speedKmh.toFixed(1)} km/h</em><strong>{vehicle.coveredHa.toFixed(1)} ha</strong></button>)}</div></section>
          <section className="ops-panel"><header><span className="section-kicker">Eventos</span><h2>Actividad reciente</h2></header><ol className="ops-event-list">{DEMO_EVENTS.map((event) => <li key={`${event.time}-${event.title}`}><time>{event.time}</time><i className={`is-${event.tone}`} /><span><b>{event.title}</b><small>{event.detail}</small></span></li>)}</ol></section>
        </div>
      </main>
    );
  }

  if (view === "live") {
    const fleetAvgSpeed = vehicles.length ? vehicles.reduce((sum, v) => sum + v.speedKmh, 0) / vehicles.length : 0;
    const fleetAvgFuel = vehicles.length ? vehicles.reduce((sum, v) => sum + v.fuelPct, 0) / vehicles.length : 0;
    const fleetTotalHa = vehicles.reduce((sum, v) => sum + v.coveredHa, 0);
    const workingCount = vehicles.filter((v) => v.status === "working").length;
    return (
      <main className="ops-workspace">{control}<KpiGrid sessions={sessions} fields={DEMO_FIELDS} />
        <div className="ops-live-layout">
          <aside className="ops-fleet-panel">
            <header><span className="section-kicker">Flota · {currentRegion.name}</span><h2>{vehicles.length} máquinas en terreno</h2></header>
            <div className="ops-fleet-filters">
              <input type="search" aria-label="Buscar en la flota" placeholder="Buscar máquina, operador o patente…" value={fleetQuery} onChange={(event) => setFleetQuery(event.target.value)} />
              <select aria-label="Filtrar por estado" value={fleetStatusFilter} onChange={(event) => setFleetStatusFilter(event.target.value as typeof fleetStatusFilter)}>
                {FLEET_STATUS_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </div>
            {selectedVehicleId && <button type="button" className="ops-fleet-clear" onClick={() => selectVehicle(null)}>✕ Quitar selección · ver toda la flota</button>}
            {filteredFleet.map((vehicle) => <button key={vehicle.id} type="button" className={selectedVehicleId === vehicle.id ? "is-selected" : ""} onClick={() => selectVehicle(selectedVehicleId === vehicle.id ? null : vehicle.id)} aria-pressed={selectedVehicleId === vehicle.id}><span className="ops-vehicle-avatar">T</span><span><b>{vehicle.name}</b><small>{vehicle.driver}</small></span><em><i className="ops-dot is-green" /> {vehicleStatusLabel(vehicle.status)}</em></button>)}
            {filteredFleet.length === 0 && <div className="ops-empty">Ninguna máquina coincide con el filtro.</div>}
          </aside>
          {mapCard(false)}
        </div>
        {selectedVehicle ? (
          <section className="ops-telemetry-strip"><article><span>Velocidad</span><b>{selectedVehicle.speedKmh.toFixed(1)} km/h</b></article><article><span>Combustible</span><b>{selectedVehicle.fuelPct.toFixed(0)}%</b></article><article><span>Horómetro</span><b>{number(selectedVehicle.engineHours)} h</b></article><article><span>Cobertura</span><b>{number(selectedVehicle.coveredHa)} ha</b></article><article><span>Progreso lote</span><b>{Math.round(selectedVehicle.progress * 100)}%</b></article></section>
        ) : (
          <section className="ops-telemetry-strip"><article><span>Velocidad media</span><b>{fleetAvgSpeed.toFixed(1)} km/h</b></article><article><span>Combustible medio</span><b>{fleetAvgFuel.toFixed(0)}%</b></article><article><span>Trabajando</span><b>{workingCount} / {vehicles.length}</b></article><article><span>Cobertura total</span><b>{number(fleetTotalHa)} ha</b></article><article><span>Selección</span><b>Toda la flota</b></article></section>
        )}
      </main>
    );
  }

  if (view === "routes") {
    return <main className="ops-workspace">{control}<section className="ops-panel ops-table-panel"><header><div><span className="section-kicker">Rendimiento acumulado · {currentRegion.name}</span><h2>Odómetro y utilización</h2><p>La distancia se suma sobre puntos GPS ordenados; no se usa la diagonal entre inicio y fin.</p></div><button className="ops-action">Exportar resumen</button></header><div className="ops-machine-metrics">{vehicles.map((vehicle, index) => <article key={vehicle.id}><div><span className="ops-vehicle-avatar">T</span><span><b>{vehicle.name}</b><small>{vehicle.plate}</small></span><em>{88 - index * 4}% disponibilidad</em></div><dl><div><dt>Odómetro jornada</dt><dd>{number(vehicle.distanceKm)} km</dd></div><div><dt>Horómetro</dt><dd>{number(vehicle.engineHours)} h</dd></div><div><dt>Superficie</dt><dd>{number(vehicle.coveredHa)} ha</dd></div><div><dt>Rendimiento</dt><dd>{number(vehicle.coveredHa / (4.2 + index * .35), 2)} ha/h</dd></div></dl><span className="ops-meter"><i style={{ width: `${72 + index * 6}%` }} /></span></article>)}</div></section>{mapCard(true)}</main>;
  }

  if (view === "stats") {
    const totalArea = sessions.reduce((sum, item) => sum + item.coveredHa, 0);
    const totalFuel = sessions.reduce((sum, item) => sum + item.fuelLiters, 0);
    return <main className="ops-workspace">{control}<section className="ops-insight-hero"><div><span className="section-kicker">Índice de jornada</span><strong>92</strong><em>/100</em><p>Buen desempeño general. La oportunidad principal está en reducir tiempos de giro del Lote Sur 2.</p></div><div className="ops-score-bars"><div><span>Cobertura</span><i><em style={{ width: "94%" }} /></i><b>94</b></div><div><span>Uso de combustible</span><i><em style={{ width: "86%" }} /></i><b>86</b></div><div><span>Tiempo productivo</span><i><em style={{ width: "91%" }} /></i><b>91</b></div></div></section><KpiGrid sessions={sessions} fields={DEMO_FIELDS} /><div className="ops-indicator-grid"><section className="ops-panel"><header><span className="section-kicker">Comparación</span><h2>Eficiencia por máquina</h2></header>{vehicles.map((vehicle, index) => <div className="ops-ranking-row" key={vehicle.id}><b>0{index + 1}</b><span>{vehicle.name}<small>{number(vehicle.coveredHa / (4.2 + index * .35), 2)} ha/h</small></span><i><em style={{ width: `${92 - index * 7}%` }} /></i><strong>{92 - index * 7}</strong></div>)}</section><section className="ops-panel"><header><span className="section-kicker">Calidad del cálculo</span><h2>Cómo se obtuvo</h2></header><ul className="ops-method-list"><li><b>Distancia</b><span>Suma Haversine de puntos consecutivos válidos.</span></li><li><b>Duración</b><span>Intervalos efectivos dentro del rango consultado.</span></li><li><b>Rendimiento</b><span>{number(totalArea, 1)} ha / horas productivas, ponderado por sesión.</span></li><li><b>Consumo</b><span>{number(totalFuel / totalArea, 2)} L/ha sobre superficie cubierta.</span></li></ul></section></div></main>;
  }

  if (view === "chartsStats") {
    return <main className="ops-workspace">{control}<Suspense fallback={<div className="view-loader"><span className="view-loader__spinner"/>Cargando analítica…</div>}><AnalyticsCharts vehicles={vehicles}/></Suspense></main>;
  }

  if (view === "masters") {
    const masterCards = [
      { key: "machines", label: "Máquinas", value: demoMode ? allVehicles.length : realData.machines.length, detail: `${REGIONS.length} ubicaciones`, icon: "T", items: demoMode ? allVehicles.map((v) => v.name) : realData.machines.map((m) => m.name) },
      { key: "drivers", label: "Conductores", value: demoMode ? new Set(allVehicles.map((v) => v.driver)).size : realData.drivers.length, detail: "licencias al día", icon: "C", items: demoMode ? Array.from(new Set(allVehicles.map((v) => v.driver))) : realData.drivers.map((d) => d.name) },
      { key: "costCenters", label: "Centros de costo", value: demoMode ? new Set(DEMO_FIELDS.map((f) => f.costCenter)).size : realData.costCenters.length, detail: "estructura activa", icon: "$", items: demoMode ? Array.from(new Set(DEMO_FIELDS.map((f) => f.costCenter))) : realData.costCenters.map((c) => c.name) },
      { key: "fields", label: "Polígonos", value: demoMode ? DEMO_FIELDS.length : realData.fields.length, detail: "geometría validada", icon: "P", items: demoMode ? DEMO_FIELDS.map((f) => f.name) : realData.fields.map((f) => f.name) },
    ];
    const activeMasterCard = masterCards.find((card) => card.key === openMasterCard) ?? null;
    return <main className="ops-workspace">{control}<div className="ops-master-grid">{masterCards.map((card) => <article key={card.label}><span>{card.icon}</span><div><b>{card.value}</b><h3>{card.label}</h3><p>{card.detail}</p></div><button type="button" onClick={() => setOpenMasterCard(card.key)}>Administrar</button></article>)}</div>
      {demoMode ? (
        <div className="ops-catalog-grid"><section className="ops-panel"><header><span className="section-kicker">Geometría · toda la empresa</span><h2>Predios y pasadas registradas</h2></header><div className="ops-field-catalog">{DEMO_FIELDS.map((field) => <article key={field.id}><i style={{ background: field.color }}/><span><b>{field.name}</b><small>{field.crop} · {REGIONS.find((r) => r.id === field.regionId)?.name}</small></span><em>{field.areaHa} ha</em><strong>{Math.floor(field.workPath.length / 2)} pasadas</strong></article>)}</div></section><section className="ops-panel"><header><span className="section-kicker">Salud de datos</span><h2>Controles de calidad</h2></header><ul className="ops-health-list"><li><i className="is-ok">✓</i><span><b>Polígonos cerrados</b><small>{DEMO_FIELDS.length} de {DEMO_FIELDS.length} geometrías válidas</small></span></li><li><i className="is-ok">✓</i><span><b>Pasadas contenidas</b><small>Sin puntos fuera del lote</small></span></li><li><i className="is-ok">✓</i><span><b>GPS ordenado</b><small>Timestamps crecientes</small></span></li><li><i className="is-warning">!</i><span><b>Sesiones reales antiguas</b><small>4 pendientes de cierre administrativo</small></span></li></ul></section></div>
      ) : (
        <div className="ops-catalog-grid"><section className="ops-panel"><header><span className="section-kicker">Geometría · toda la empresa</span><h2>Predios registrados</h2></header><div className="ops-field-catalog">{realData.fields.map((field) => <article key={field.id}><i style={{ background: field.color ?? "#2f7d5c" }}/><span><b>{field.name}</b></span><em>{field.polygon?.length ?? 0} puntos</em></article>)}{realData.fields.length === 0 && <div className="ops-empty">{realStatus === "loading" ? "Cargando polígonos…" : "Sin polígonos sincronizados aún."}</div>}</div></section></div>
      )}
      {activeMasterCard && (
        <div className="ops-modal-backdrop" role="dialog" aria-modal="true" onClick={() => setOpenMasterCard(null)}>
          <div className="ops-modal" onClick={(event) => event.stopPropagation()}>
            <h2>{activeMasterCard.label}</h2>
            <p>{activeMasterCard.items.length} registrados</p>
            <div className="ops-modal__body">
              {activeMasterCard.items.length === 0
                ? <span>Sin datos disponibles.</span>
                : activeMasterCard.items.map((name, index) => <div key={`${name}-${index}`}>{name}</div>)}
            </div>
            <div className="ops-modal__actions"><button type="button" className="ops-action" onClick={() => setOpenMasterCard(null)}>Cerrar</button></div>
          </div>
        </div>
      )}
    </main>;
  }

  const showingRealHistory = !demoMode;
  return <main className="ops-workspace">{control}<section className="ops-history-toolbar"><div><span className="section-kicker">Trazabilidad</span><h2>Historial de sesiones</h2>{showingRealHistory && <p>Datos reales de Tracker · no incluye el laboratorio demo.</p>}</div>
    <label className="ops-history-daterange"><span>Desde</span><input type="date" aria-label="Desde" value={historyDateFrom} onChange={(event) => setHistoryDateFrom(event.target.value)} max={historyDateTo || undefined} /></label>
    <label className="ops-history-daterange"><span>Hasta</span><input type="date" aria-label="Hasta" value={historyDateTo} onChange={(event) => setHistoryDateTo(event.target.value)} min={historyDateFrom || undefined} /></label>
    <input type="search" aria-label="Buscar por máquina, operador, lote o labor" placeholder="Buscar máquina, operador, lote o labor…" value={historyQuery} onChange={(event) => setHistoryQuery(event.target.value)}/>
    <select aria-label="Filtrar por estado" value={historyStatus} onChange={(event) => setHistoryStatus(event.target.value as typeof historyStatus)}><option value="all">Todos los estados</option><option value="active">En curso</option><option value="completed">Completadas</option><option value="paused">Pausadas</option></select>
  </section>
  {showingRealHistory && realHistoryStatus === "error" && <div className="ops-map-notice">No se pudo cargar el historial real. Intenta nuevamente.</div>}
  <section className="ops-panel ops-session-table">
    <div className="ops-session-table__head"><span>Sesión</span><span>Máquina / operador</span><span>Lote</span><span>Labor</span><span>Duración</span><span>Distancia</span><span>Superficie</span><span>Estado</span></div>
    {showingRealHistory && realHistoryStatus === "loading" && <div className="ops-empty">Cargando historial…</div>}
    {(!showingRealHistory || realHistoryStatus !== "loading") && pagedSessions.map((row) => <button type="button" key={row.id}><span><b>{row.id}</b><small>{row.startedAtLabel}</small></span><span><b>{row.machine}</b><small>{row.driver}</small></span><span>{row.field}</span><span>{row.labor}</span><span>{row.durationHours != null ? `${number(row.durationHours)} h` : "—"}</span><span>{row.distanceKm != null ? `${number(row.distanceKm)} km` : "—"}</span><span>{row.coveredHa != null ? `${number(row.coveredHa)} ha` : "—"}</span><span><em className={`ops-status is-${row.statusTone}`}>{row.statusText}</em></span></button>)}
    {(!showingRealHistory || realHistoryStatus === "ready") && filteredSessions.length === 0 && <div className="ops-empty">No hay sesiones que coincidan con los filtros.</div>}
  </section>
  {filteredSessions.length > 0 && (
    <nav className="ops-pagination" aria-label="Paginación del historial">
      <span>{filteredSessions.length} sesiones · página {clampedHistoryPage} de {historyPageCount}</span>
      <div>
        <button type="button" disabled={clampedHistoryPage <= 1} onClick={() => setHistoryPage((p) => Math.max(1, p - 1))}>‹ Anterior</button>
        <button type="button" disabled={clampedHistoryPage >= historyPageCount} onClick={() => setHistoryPage((p) => Math.min(historyPageCount, p + 1))}>Siguiente ›</button>
      </div>
    </nav>
  )}
  </main>;
}
