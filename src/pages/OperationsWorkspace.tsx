import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import OperationsMap from "../components/OperationsMap";
import SessionPlaybackModal from "../components/SessionPlaybackModal";
import RealSessionPlaybackModal from "../components/RealSessionPlaybackModal";
import MastersAdminModal, { type MasterKind } from "../components/MastersAdminModal";
import { DEMO_MASTER_CATALOGS, type DemoCatalogItem } from "../demo/catalogs";
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
const RealAnalyticsCharts = lazy(() => import("./RealAnalyticsCharts"));
const RegistrationPage = lazy(() => import("./RegistrationPage"));
const ManualEntryPage = lazy(() => import("./ManualEntryPage"));

export type OperationsView = "live" | "routes" | "sessions" | "userView" | "stats" | "chartsStats" | "masters" | "registro" | "manual";

type ApiEntity = { id: number; name: string };
type ApiMachine = ApiEntity & { plate?: string | null; cost_center_id?: number | null; tank_capacity_liters?: number | null };
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
  duration_hours?: number | null;
  effective_hours?: number | null;
  estimated_fuel_liters?: number | null;
  last_point_ts?: string | null;
  last_lat?: number | null;
  last_lon?: number | null;
  last_speed_mps?: number | null;
};

type ApiLabor = { id: number; name: string };

function normalizeAnalyticsSessions(sessions: ApiSession[], labors: ApiEntity[]) {
  const laborNames = Object.fromEntries(labors.map((labor) => [labor.id, labor.name]));
  return sessions.map((session) => {
    const start = new Date(session.started_at).getTime();
    const end = session.ended_at ? new Date(session.ended_at).getTime() : Date.now();
    const rawHours = Math.max(0, session.effective_hours ?? session.duration_hours ?? ((end - start) / 3_600_000));
    const stale = session.status === "open" && rawHours > 24;
    return {
      id: session.id,
      machineId: session.machine_id,
      machine: session.machine_name || `Máquina #${session.machine_id}`,
      driver: session.driver_name || "Sin operador",
      location: session.cost_center_name || "Sin centro de costo",
      labor: session.labor_id != null ? laborNames[session.labor_id] || `Labor #${session.labor_id}` : "Sin labor",
      startedAt: session.started_at,
      status: session.status,
      hours: stale ? 0 : rawHours,
      distanceKm: Math.max(0, (session.total_distance_m ?? 0) / 1000),
      fuelLiters: stale ? 0 : Math.max(0, session.estimated_fuel_liters ?? 0),
      avgSpeedKmh: Math.max(0, session.avg_speed_kmh ?? 0),
      points: Math.max(0, session.points_count ?? 0),
      stale,
    };
  });
}

type RealData = {
  machines: ApiMachine[];
  drivers: ApiEntity[];
  costCenters: ApiEntity[];
  fields: ApiField[];
  sessions: ApiSession[];
  activities: ApiEntity[];
  labors: ApiEntity[];
  implements: ApiEntity[];
  species: ApiEntity[];
  varieties: ApiEntity[];
  regions: ApiEntity[];
  communes: ApiEntity[];
  fundos: ApiEntity[];
  sectors: ApiEntity[];
};

const emptyRealData: RealData = { machines: [], drivers: [], costCenters: [], fields: [], sessions: [], activities: [], labors: [], implements: [], species: [], varieties: [], regions: [], communes: [], fundos: [], sectors: [] };

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

const DEMO_MASTER_TITLES: Record<MasterKind, string> = {
  machines: "Máquinas", drivers: "Conductores", activities: "Actividades", labors: "Labores", implements: "Implementos",
  costCenters: "Centros de costo", species: "Especies", varieties: "Variedades", regions: "Regiones", communes: "Comunas",
  fundos: "Fundos", sectors: "Sectores", fields: "Predios y polígonos",
};

function demoItemDetail(item: DemoCatalogItem) {
  if (item.plate) return String(item.plate);
  if (item.crop) return `${item.crop}${item.hectares ? ` · ${item.hectares} ha` : ""}`;
  if (item.code) return `Código ${item.code}`;
  if (item.hectares) return `${item.hectares} ha`;
  return "Dato sintético para práctica";
}

function DemoMastersModal({ kind, onClose }: { kind: MasterKind; onClose: () => void }) {
  const items = DEMO_MASTER_CATALOGS[kind];
  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);
  return <div className="master-admin-backdrop" role="dialog" aria-modal="true" aria-labelledby="demo-master-title"><section className="master-admin demo-master-modal">
    <header className="master-admin__head"><div><span className="section-kicker">Laboratorio demo · solo lectura</span><h2 id="demo-master-title">{DEMO_MASTER_TITLES[kind]}</h2><p>Estos registros permiten recorrer y explicar la aplicación sin modificar información productiva.</p></div><button type="button" className="master-admin__close" onClick={onClose} aria-label="Cerrar">×</button></header>
    <div className="demo-master-modal__body">{items.map((item) => <article key={item.id}><i>{String(item.name).slice(0, 1).toUpperCase()}</i><span><b>{item.name}</b><small>{demoItemDetail(item)}</small></span><em>Demo</em></article>)}</div>
  </section></div>;
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
  const [openMasterCard, setOpenMasterCard] = useState<MasterKind | null>(null);
  const [openDemoMasterCard, setOpenDemoMasterCard] = useState<MasterKind | null>(null);
  const [openSessionId, setOpenSessionId] = useState<string | null>(null);
  const [realData, setRealData] = useState<RealData>(emptyRealData);
  const [realDataVersion, setRealDataVersion] = useState(0);
  const [realStatus, setRealStatus] = useState<"loading" | "ready" | "error">("loading");
  const [realSessions, setRealSessions] = useState<ApiSession[]>([]);
  const [laborsById, setLaborsById] = useState<Record<number, string>>({});
  const [realHistoryStatus, setRealHistoryStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const realHistoryRequestedRef = useRef(false);
  const [analyticsHistory, setAnalyticsHistory] = useState<ApiSession[]>([]);
  const [analyticsHistoryStatus, setAnalyticsHistoryStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const analyticsHistoryRequestedRef = useRef(false);

  useEffect(() => {
    if (!running || !demoMode) return;
    const id = window.setInterval(() => setElapsedSeconds((value) => value + 1), 1000);
    return () => window.clearInterval(id);
  }, [demoMode, running]);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setRealStatus("loading");
      try {
        const requests = await Promise.allSettled([
          apiJson<ApiMachine[]>("/machines"), apiJson<ApiEntity[]>("/drivers"), apiJson<ApiEntity[]>("/cost_centers"), apiJson<ApiField[]>("/fields"),
          apiJson<ApiSession[]>("/sessions_recent?limit=100"), apiJson<ApiEntity[]>("/activities"), apiJson<ApiEntity[]>("/labors"), apiJson<ApiEntity[]>("/implements"),
          apiJson<ApiEntity[]>("/species"), apiJson<ApiEntity[]>("/varieties"), apiJson<ApiEntity[]>("/regions"), apiJson<ApiEntity[]>("/communes"),
          apiJson<ApiEntity[]>("/fundos"), apiJson<ApiEntity[]>("/sectors"),
        ]);
        if (!active) return;
        const value = <T,>(index: number): T[] => requests[index].status === "fulfilled" && Array.isArray(requests[index].value) ? requests[index].value as T[] : [];
        setRealData({ machines: value(0), drivers: value(1), costCenters: value(2), fields: value<ApiField>(3), sessions: value<ApiSession>(4), activities: value(5), labors: value(6), implements: value(7), species: value(8), varieties: value(9), regions: value(10), communes: value(11), fundos: value(12), sectors: value(13) });
        setRealStatus(requests.slice(0, 4).some((result) => result.status === "fulfilled") ? "ready" : "error");
      } catch {
        if (active) setRealStatus("error");
      }
    };
    void load();
    return () => { active = false; };
  }, [realDataVersion]);

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

  // Analítica real usa un histórico amplio. La consulta es diferida para no
  // penalizar el tablero operativo ni el mapa cuando el usuario no la necesita.
  useEffect(() => {
    if (view !== "chartsStats" || demoMode || analyticsHistoryRequestedRef.current) return;
    analyticsHistoryRequestedRef.current = true;
    const load = async () => {
      setAnalyticsHistoryStatus("loading");
      try {
        const dateTo = new Date(Date.now() + 86_400_000).toISOString();
        const query = new URLSearchParams({ from: "2018-01-01T00:00:00.000Z", to: dateTo, limit: "5000" });
        const data = await apiJson<ApiSession[]>(`/sessions/search?${query.toString()}`);
        setAnalyticsHistory(data);
        setAnalyticsHistoryStatus("ready");
      } catch {
        setAnalyticsHistoryStatus("error");
        analyticsHistoryRequestedRef.current = false;
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
      const durationHours = s.duration_hours ?? (end && !Number.isNaN(start) ? (end - start) / 3_600_000 : null);
      const distanceKm = s.total_distance_m != null ? s.total_distance_m / 1000 : null;
      return {
        id: s.id, startedAtLabel: formatSessionDateTime(s.started_at), startedAtIso: s.started_at,
        machine: s.machine_name || `Máquina #${s.machine_id}`, driver: s.driver_name || "—",
        field: s.cost_center_name || "—", labor: (s.labor_id != null && laborsById[s.labor_id]) || "—",
        durationHours, distanceKm, coveredHa: null, fuelLiters: s.estimated_fuel_liters ?? null,
        statusTone: s.status === "open" ? "active" : "completed",
        statusText: s.status === "open" ? "En curso" : "Completada",
      };
    });
  }, [demoMode, realSessions, laborsById]);

  const realAnalyticsSessions = useMemo(
    () => normalizeAnalyticsSessions(realData.sessions, realData.labors),
    [realData.labors, realData.sessions],
  );
  const fullRealAnalyticsSessions = useMemo(
    () => normalizeAnalyticsSessions(analyticsHistoryStatus === "ready" ? analyticsHistory : realData.sessions, realData.labors),
    [analyticsHistory, analyticsHistoryStatus, realData.labors, realData.sessions],
  );

  const realMachineMetrics = useMemo(() => realData.machines.map((machine) => {
    const machineSessions = realAnalyticsSessions.filter((session) => session.machineId === machine.id);
    const latest = [...realData.sessions].filter((session) => session.machine_id === machine.id).sort((a, b) => b.started_at.localeCompare(a.started_at))[0];
    return {
      ...machine,
      sessions: machineSessions.length,
      openSessions: machineSessions.filter((session) => session.status === "open").length,
      activeSessions: machineSessions.filter((session) => session.status === "open" && !session.stale).length,
      staleSessions: machineSessions.filter((session) => session.status === "open" && session.stale).length,
      hours: machineSessions.reduce((sum, session) => sum + session.hours, 0),
      distanceKm: machineSessions.reduce((sum, session) => sum + session.distanceKm, 0),
      fuelLiters: machineSessions.reduce((sum, session) => sum + session.fuelLiters, 0),
      points: machineSessions.reduce((sum, session) => sum + session.points, 0),
      latest,
    };
  }).sort((a, b) => b.hours - a.hours), [realAnalyticsSessions, realData.machines, realData.sessions]);

  const realMapFields = useMemo(() => realData.fields.filter((field) => (field.polygon?.length ?? 0) >= 3).map((field) => ({
    id: String(field.id), name: field.name, crop: "Dato productivo", costCenter: field.name, regionId: "real",
    color: field.color || "#2f9e72", areaHa: 0, polygon: field.polygon ?? [], workPath: [],
  })), [realData.fields]);

  const realLiveVehicles = useMemo(() => realMachineMetrics.flatMap((machine) => {
    const session = machine.latest;
    if (!session || session.status !== "open" || (session.duration_hours ?? 0) > 24 || session.last_lat == null || session.last_lon == null) return [];
    return [{
      id: String(machine.id), name: machine.name, plate: machine.plate || "Sin patente", driver: session.driver_name || "Sin operador",
      fieldId: "", regionId: "real", status: "working" as const, progress: 0, speedKmh: Math.max(0, (session.last_speed_mps ?? 0) * 3.6),
      fuelPct: 0, engineHours: machine.hours, distanceKm: machine.distanceKm, coveredHa: 0,
      position: { lat: session.last_lat, lon: session.last_lon }, bearing: 0,
    }];
  }), [realMachineMetrics]);

  const realDepot = useMemo(() => realMapFields[0]?.polygon[0] ?? realLiveVehicles[0]?.position ?? { lat: -33.4489, lon: -70.6693 }, [realLiveVehicles, realMapFields]);
  const realTotals = useMemo(() => ({
    sessions: realAnalyticsSessions.length,
    open: realAnalyticsSessions.filter((session) => session.status === "open").length,
    active: realAnalyticsSessions.filter((session) => session.status === "open" && !session.stale).length,
    hours: realAnalyticsSessions.reduce((sum, session) => sum + session.hours, 0),
    distanceKm: realAnalyticsSessions.reduce((sum, session) => sum + session.distanceKm, 0),
    fuelLiters: realAnalyticsSessions.reduce((sum, session) => sum + session.fuelLiters, 0),
    points: realAnalyticsSessions.reduce((sum, session) => sum + session.points, 0),
  }), [realAnalyticsSessions]);
  const realQuality = useMemo(() => {
    if (!realData.sessions.length) return { score: 0, closure: 0, gps: 0, classified: 0 };
    const closure = realData.sessions.filter((session) => session.status === "closed").length / realData.sessions.length * 100;
    const gps = realData.sessions.filter((session) => session.points_count > 0).length / realData.sessions.length * 100;
    const classified = realData.sessions.filter((session) => session.cost_center_name && session.labor_id != null).length / realData.sessions.length * 100;
    return { score: Math.round((closure + gps + classified) / 3), closure: Math.round(closure), gps: Math.round(gps), classified: Math.round(classified) };
  }, [realData.sessions]);
  const staleOpenSessions = realAnalyticsSessions.filter((session) => session.status === "open" && session.stale).length;

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

  // Cerrar el detalle de sesión al salir de Historial o cambiar de fuente de
  // datos evita mostrar reproducción de una sesión que ya no aplica.
  const sessionModalScopeKey = `${view}|${demoMode}`;
  const [prevSessionModalScopeKey, setPrevSessionModalScopeKey] = useState(sessionModalScopeKey);
  if (prevSessionModalScopeKey !== sessionModalScopeKey) {
    setPrevSessionModalScopeKey(sessionModalScopeKey);
    if (openSessionId !== null) setOpenSessionId(null);
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

  if (view === "manual") {
    return (
      <main className="ops-workspace">
        {control}
        <Suspense fallback={<div className="view-loader"><span className="view-loader__spinner" />Cargando ingreso manual…</div>}>
          <ManualEntryPage demoMode={demoMode} />
        </Suspense>
      </main>
    );
  }

  if (!demoMode && view === "userView") {
    const latest = realAnalyticsSessions.slice(0, 6);
    return <main className="ops-workspace">{control}
      <section className="ops-kpi-grid"><article><span>Máquinas registradas</span><strong>{realData.machines.length}</strong><small>{realTotals.open} sesiones abiertas · {staleOpenSessions} antiguas</small></article><article><span>Horas productivas</span><strong>{number(realTotals.hours)} <em>h</em></strong><small>excluye sesiones abiertas por más de 24 h</small></article><article><span>Distancia GPS</span><strong>{number(realTotals.distanceKm)} <em>km</em></strong><small>{realTotals.points.toLocaleString("es-CL")} puntos GPS</small></article><article><span>Combustible estimado</span><strong>{number(realTotals.fuelLiters)} <em>L</em></strong><small>calculado según máquina y labor</small></article></section>
      <div className="ops-summary-grid"><section className="ops-panel"><header><span className="section-kicker">Actividad productiva</span><h2>Sesiones recientes</h2><p>Información real visible para los centros de costo asignados al usuario.</p></header><div className="ops-fleet-rows">{latest.map((session) => <div className="ops-real-session-row" key={session.id}><i className={`ops-dot ${session.status === "open" && !session.stale ? "is-green" : ""}`}/><span><b>{session.machine}</b><small>{session.driver} · {session.location}</small></span><em>{session.stale ? "Revisar" : `${number(session.hours)} h`}</em><strong>{session.stale ? "Pendiente cierre" : session.status === "open" ? "En curso" : "Cerrada"}</strong></div>)}{!latest.length && <div className="ops-empty">Todavía no hay sesiones productivas visibles.</div>}</div></section>
      <section className="ops-side-card"><header><span className="section-kicker">Calidad operacional</span><h2>Preparación de los datos</h2></header><div className="ops-progress-ring" style={{ "--progress": `${realQuality.score}%` } as React.CSSProperties}><strong>{realQuality.score}%</strong><span>integridad promedio</span></div><div className="ops-progress-list"><div><span>Sesiones cerradas</span><b>{realQuality.closure}%</b><i><em style={{ width: `${realQuality.closure}%` }}/></i></div><div><span>Sesiones con GPS</span><b>{realQuality.gps}%</b><i><em style={{ width: `${realQuality.gps}%` }}/></i></div><div><span>Labor y centro asignados</span><b>{realQuality.classified}%</b><i><em style={{ width: `${realQuality.classified}%` }}/></i></div></div></section></div>
      <p className={`ops-source-state is-${realStatus}`}>{realStatus === "ready" ? "API productiva sincronizada" : realStatus === "loading" ? "Sincronizando API…" : "No fue posible sincronizar la API."}</p>
    </main>;
  }

  if (!demoMode && view === "live") {
    const selectedRealMachine = selectedVehicleId ? realMachineMetrics.find((machine) => String(machine.id) === selectedVehicleId) : null;
    return <main className="ops-workspace">{control}
      <section className="ops-kpi-grid"><article><span>Sesiones en curso</span><strong>{realTotals.active}</strong><small><i className="ops-dot is-green"/>abiertas durante las últimas 24 h</small></article><article><span>Máquinas con posición</span><strong>{realLiveVehicles.length}</strong><small>último punto GPS disponible</small></article><article><span>Polígonos cargados</span><strong>{realMapFields.length}</strong><small>predios con geometría válida</small></article><article><span>Puntos GPS</span><strong>{realTotals.points.toLocaleString("es-CL")}</strong><small>en las sesiones consultadas</small></article></section>
      <div className="ops-live-layout"><aside className="ops-fleet-panel"><header><span className="section-kicker">Flota productiva</span><h2>{realMachineMetrics.length} máquinas visibles</h2></header>{realMachineMetrics.map((machine) => <button type="button" key={machine.id} className={selectedVehicleId === String(machine.id) ? "is-selected" : ""} onClick={() => setSelectedVehicleId(selectedVehicleId === String(machine.id) ? null : String(machine.id))}><span className="ops-vehicle-avatar">T</span><span><b>{machine.name}</b><small>{machine.plate || "Sin patente"}</small></span><em><i className={`ops-dot ${machine.activeSessions ? "is-green" : ""}`}/> {machine.activeSessions ? "En operación" : machine.staleSessions ? "Cierre pendiente" : "Sin sesión abierta"}</em></button>)}{!realMachineMetrics.length && <div className="ops-empty">No hay máquinas disponibles.</div>}</aside>
      <section className="ops-map-card"><header><div><span className="section-kicker">Cartografía productiva</span><h2>{selectedRealMachine?.name || "Operación en terreno"}</h2><p>{realLiveVehicles.length ? "Posiciones reportadas por sesiones abiertas." : "No hay sesiones abiertas con posición GPS; se muestran los polígonos disponibles."}</p></div></header><div className="ops-map-frame"><OperationsMap fields={realMapFields} vehicles={realLiveVehicles} selectedVehicleId={selectedVehicleId} onSelectVehicle={setSelectedVehicleId} showRows={false} showRoadRoute={false} compact={false} depot={realDepot} followVehicle={followVehicle} onUserInteracted={() => setFollowVehicle(false)}/></div><footer><span><i className="ops-dot is-lime"/> Posición de la última telemetría</span><b>Datos reales</b></footer></section></div>
      <section className="ops-telemetry-strip"><article><span>Máquina seleccionada</span><b>{selectedRealMachine?.name || "Toda la flota"}</b></article><article><span>Horas acumuladas</span><b>{number(selectedRealMachine?.hours ?? realTotals.hours)} h</b></article><article><span>Distancia acumulada</span><b>{number(selectedRealMachine?.distanceKm ?? realTotals.distanceKm)} km</b></article><article><span>Combustible estimado</span><b>{number(selectedRealMachine?.fuelLiters ?? realTotals.fuelLiters)} L</b></article><article><span>Sesiones</span><b>{selectedRealMachine?.sessions ?? realTotals.sessions}</b></article></section>
    </main>;
  }

  if (!demoMode && view === "routes") {
    const maxHours = Math.max(...realMachineMetrics.map((machine) => machine.hours), 1);
    return <main className="ops-workspace">{control}<section className="ops-panel ops-table-panel"><header><div><span className="section-kicker">Acumulados productivos</span><h2>Odómetro y utilización reales</h2><p>La distancia corresponde a sesiones GPS; las horas excluyen sesiones abiertas por más de 24 horas.</p></div></header><div className="ops-machine-metrics">{realMachineMetrics.map((machine) => <article key={machine.id}><div><span className="ops-vehicle-avatar">T</span><span><b>{machine.name}</b><small>{machine.plate || "Sin patente"}</small></span><em>{machine.activeSessions ? "En operación" : machine.staleSessions ? "Cierre pendiente" : `${machine.sessions} sesiones`}</em></div><dl><div><dt>Odómetro GPS</dt><dd>{number(machine.distanceKm)} km</dd></div><div><dt>Horas registradas</dt><dd>{number(machine.hours)} h</dd></div><div><dt>Combustible</dt><dd>{number(machine.fuelLiters)} L</dd></div><div><dt>Puntos GPS</dt><dd>{machine.points.toLocaleString("es-CL")}</dd></div></dl><span className="ops-meter"><i style={{ width: `${machine.hours / maxHours * 100}%` }}/></span></article>)}{!realMachineMetrics.length && <div className="ops-empty">No hay máquinas productivas visibles.</div>}</div></section></main>;
  }

  if (!demoMode && view === "stats") {
    return <main className="ops-workspace">{control}<section className="ops-insight-hero"><div><span className="section-kicker">Índice de integridad</span><strong>{realQuality.score}</strong><em>/100</em><p>Promedio verificable de cierre de sesiones, presencia de GPS y clasificación por labor y centro de costo.</p></div><div className="ops-score-bars"><div><span>Cierre de sesiones</span><i><em style={{ width: `${realQuality.closure}%` }}/></i><b>{realQuality.closure}</b></div><div><span>Cobertura GPS</span><i><em style={{ width: `${realQuality.gps}%` }}/></i><b>{realQuality.gps}</b></div><div><span>Clasificación completa</span><i><em style={{ width: `${realQuality.classified}%` }}/></i><b>{realQuality.classified}</b></div></div></section>
      <section className="ops-kpi-grid"><article><span>Horas registradas</span><strong>{number(realTotals.hours)} <em>h</em></strong><small>duración efectiva</small></article><article><span>Distancia</span><strong>{number(realTotals.distanceKm)} <em>km</em></strong><small>acumulado GPS</small></article><article><span>Consumo horario</span><strong>{number(realTotals.hours ? realTotals.fuelLiters / realTotals.hours : 0, 2)} <em>L/h</em></strong><small>estimación ponderada</small></article><article><span>Sesiones abiertas</span><strong>{realTotals.open}</strong><small>requieren cierre posterior</small></article></section>
      <div className="ops-indicator-grid"><section className="ops-panel"><header><span className="section-kicker">Comparación real</span><h2>Utilización por máquina</h2></header>{realMachineMetrics.slice(0, 10).map((machine, index) => <div className="ops-ranking-row" key={machine.id}><b>{String(index + 1).padStart(2, "0")}</b><span>{machine.name}<small>{number(machine.distanceKm)} km · {machine.sessions} sesiones</small></span><i><em style={{ width: `${machine.hours / Math.max(realMachineMetrics[0]?.hours ?? 1, 1) * 100}%` }}/></i><strong>{number(machine.hours)} h</strong></div>)}{!realMachineMetrics.length && <div className="ops-empty">No hay métricas de máquinas.</div>}</section><section className="ops-panel"><header><span className="section-kicker">Lectura del indicador</span><h2>Cómo mejorar la calidad</h2></header><ul className="ops-method-list"><li><b>Cierre</b><span>Cerrar las sesiones consolida duración, distancia y velocidad media.</span></li><li><b>GPS</b><span>Una sesión sin puntos no puede respaldar recorrido ni posición.</span></li><li><b>Clasificación</b><span>Labor y centro de costo permiten comparar operaciones equivalentes.</span></li><li><b>Consumo</b><span>Se estima con la configuración de cada máquina y el esfuerzo de la labor.</span></li></ul></section></div>
    </main>;
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
      <footer><span><i className="ops-dot is-lime" /> Pasadas dentro del lote</span><span><i className="ops-line-sample" /> Caminos: OpenStreetMap vía OSRM</span><b>Dataset demostrativo</b></footer>
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
    return <main className="ops-workspace">{control}
      {!demoMode && analyticsHistoryStatus === "loading" && <div className="ops-map-notice"><b>Cargando histórico completo.</b> Mientras tanto se muestran las sesiones más recientes.</div>}
      {!demoMode && analyticsHistoryStatus === "error" && <div className="ops-map-notice"><b>No se pudo ampliar el histórico.</b> La analítica sigue disponible con las sesiones recientes y puede reintentarse al volver a esta vista.</div>}
      <Suspense fallback={<div className="view-loader"><span className="view-loader__spinner"/>Cargando analítica…</div>}>
        {demoMode
          ? <AnalyticsCharts vehicles={allVehicles} sessions={sessions} regionId={selectedRegionId} regionName={currentRegion.name} onOpenSession={setOpenSessionId}/>
          : <RealAnalyticsCharts sessions={fullRealAnalyticsSessions} onOpenSession={setOpenSessionId}/>
        }
      </Suspense>
      {demoMode && openSessionId && (() => {
        const session = DEMO_SESSIONS.find((item) => item.id === openSessionId);
        return session ? <SessionPlaybackModal key={session.id} session={session} onClose={() => setOpenSessionId(null)} /> : null;
      })()}
      {!demoMode && openSessionId && (() => {
        const session = fullRealAnalyticsSessions.find((item) => item.id === openSessionId);
        if (!session) return null;
        return <RealSessionPlaybackModal key={session.id} session={{ id: session.id, machine: session.machine, driver: session.driver, field: session.location, labor: session.labor, durationHours: session.hours, distanceKm: session.distanceKm }} onClose={() => setOpenSessionId(null)}/>;
      })()}
    </main>;
  }

  if (view === "masters") {
    const masterSource = demoMode ? DEMO_MASTER_CATALOGS : realData;
    const displayedFields = masterSource.fields as ApiField[];
    const masterGroups: { title: string; description: string; cards: { key: MasterKind; label: string; value: number; detail: string; icon: string }[] }[] = [
      { title: "Operación", description: "Recursos y clasificaciones utilizados en los partes de trabajo.", cards: [
        { key: "machines", label: "Máquinas", value: masterSource.machines.length, detail: "consumo y asignaciones", icon: "M" },
        { key: "drivers", label: "Conductores", value: masterSource.drivers.length, detail: "alta, edición y desactivación", icon: "C" },
        { key: "activities", label: "Actividades", value: masterSource.activities.length, detail: "categorías operacionales", icon: "A" },
        { key: "labors", label: "Labores", value: masterSource.labors.length, detail: "esfuerzo y velocidad objetivo", icon: "L" },
        { key: "implements", label: "Implementos", value: masterSource.implements.length, detail: "alta, edición y desactivación", icon: "I" },
      ] },
      { title: "Estructura agrícola", description: "Clasificación productiva, especies y variedades.", cards: [
        { key: "costCenters", label: "Centros de costo", value: masterSource.costCenters.length, detail: "superficie, hileras y plantas", icon: "$" },
        { key: "species", label: "Especies", value: masterSource.species.length, detail: "catálogo de cultivos", icon: "E" },
        { key: "varieties", label: "Variedades", value: masterSource.varieties.length, detail: "asociadas a especies", icon: "V" },
      ] },
      { title: "Territorio", description: "Jerarquía geográfica y delimitación visual de predios.", cards: [
        { key: "regions", label: "Regiones", value: masterSource.regions.length, detail: "división territorial", icon: "R" },
        { key: "communes", label: "Comunas", value: masterSource.communes.length, detail: "asociadas a regiones", icon: "C" },
        { key: "fundos", label: "Fundos", value: masterSource.fundos.length, detail: "dirección y superficie", icon: "F" },
        { key: "sectors", label: "Sectores", value: masterSource.sectors.length, detail: "subdivisiones de fundos", icon: "S" },
        { key: "fields", label: "Predios y polígonos", value: displayedFields.length, detail: "editor visual sobre mapa", icon: "P" },
      ] },
    ];
    return <main className="ops-workspace">{control}<section className="ops-map-notice"><b>{demoMode ? "Maestros del Laboratorio demo." : "Administración productiva."}</b> {demoMode ? "Puede revisar el catálogo sintético completo; está protegido contra escritura." : "Aquí se muestran y modifican datos reales de Tracker; cada maestro se carga de forma independiente para que un endpoint con problemas no oculte los demás."}</section>{masterGroups.map((group) => <section className="ops-master-section" key={group.title}><header><div><span className="section-kicker">Maestros</span><h2>{group.title}</h2><p>{group.description}</p></div></header><div className="ops-master-grid">{group.cards.map((card) => <article key={card.label}><span>{card.icon}</span><div><b>{!demoMode && realStatus === "loading" ? "…" : card.value}</b><h3>{card.label}</h3><p>{card.detail}</p></div><button type="button" onClick={() => demoMode ? setOpenDemoMasterCard(card.key) : setOpenMasterCard(card.key)}>{demoMode ? "Ver registros" : "Administrar"}</button></article>)}</div></section>)}
      <div className="ops-catalog-grid"><section className="ops-panel"><header><span className="section-kicker">Geometría · {demoMode ? "laboratorio" : "datos reales"}</span><h2>Predios registrados</h2><p>{displayedFields.length} polígonos {demoMode ? "disponibles para demostración" : "cargados desde Tracker"}.</p></header><div className="ops-field-catalog">{displayedFields.map((field) => <button type="button" key={field.id} onClick={() => demoMode ? setOpenDemoMasterCard("fields") : setOpenMasterCard("fields")}><i style={{ background: field.color ?? "#2f7d5c" }}/><span><b>{field.name}</b><small>{demoMode ? "Seleccione para revisar el catálogo demo" : "Seleccione para abrir el editor de polígonos"}</small></span><em>{field.polygon?.length ?? 0} vértices</em></button>)}{displayedFields.length === 0 && <div className="ops-empty">{realStatus === "loading" ? "Cargando polígonos…" : "No fue posible cargar los polígonos. Use Administrar para reintentar."}</div>}</div></section><section className="ops-panel"><header><span className="section-kicker">Cobertura funcional</span><h2>Contratos disponibles</h2></header><ul className="ops-health-list"><li><i className="is-ok">✓</i><span><b>{demoMode ? "Catálogo demostrativo completo" : "Administración completa"}</b><small>Operación, estructura agrícola y territorio</small></span></li><li><i className="is-ok">✓</i><span><b>Historial protegido</b><small>Conductores, actividades, labores e implementos se desactivan sin romper partes anteriores</small></span></li><li><i className="is-ok">✓</i><span><b>Editor cartográfico</b><small>Polígonos satelitales con vértices arrastrables</small></span></li></ul></section></div>
      {!demoMode && openMasterCard && <MastersAdminModal kind={openMasterCard} onClose={() => setOpenMasterCard(null)} onChanged={() => setRealDataVersion((version) => version + 1)} />}
      {demoMode && openDemoMasterCard && <DemoMastersModal kind={openDemoMasterCard} onClose={() => setOpenDemoMasterCard(null)} />}
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
    {(!showingRealHistory || realHistoryStatus !== "loading") && pagedSessions.map((row) => <button type="button" key={row.id} aria-haspopup="dialog" onClick={() => setOpenSessionId(row.id)}><span><b>{row.id}</b><small>{row.startedAtLabel}</small></span><span><b>{row.machine}</b><small>{row.driver}</small></span><span>{row.field}</span><span>{row.labor}</span><span>{row.durationHours != null ? `${number(row.durationHours)} h` : "—"}</span><span>{row.distanceKm != null ? `${number(row.distanceKm)} km` : "—"}</span><span>{row.coveredHa != null ? `${number(row.coveredHa)} ha` : "—"}</span><span><em className={`ops-status is-${row.statusTone}`}>{row.statusText}</em></span></button>)}
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
  {demoMode && openSessionId && (() => {
    const session = DEMO_SESSIONS.find((item) => item.id === openSessionId);
    return session ? <SessionPlaybackModal key={session.id} session={session} onClose={() => setOpenSessionId(null)} /> : null;
  })()}
  {!demoMode && openSessionId && (() => {
    const row = historyRows.find((item) => item.id === openSessionId);
    if (!row) return null;
    return <RealSessionPlaybackModal key={row.id} session={{ id: row.id, machine: row.machine, driver: row.driver, field: row.field, labor: row.labor, durationHours: row.durationHours, distanceKm: row.distanceKm }} onClose={() => setOpenSessionId(null)}/>;
  })()}
  </main>;
}
