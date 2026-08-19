import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import OperationsMap from "../components/OperationsMap";
import {
  DEMO_EVENTS,
  DEMO_FIELDS,
  DEMO_SESSIONS,
  getDemoVehicles,
  type DemoSession,
} from "../demo/scenario";
import { apiJson } from "../services/http";
import "./OperationsWorkspace.css";

const AnalyticsCharts = lazy(() => import("./AnalyticsCharts"));

export type OperationsView = "live" | "routes" | "sessions" | "userView" | "stats" | "chartsStats" | "masters";

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
};

type RealData = {
  machines: ApiEntity[];
  drivers: ApiEntity[];
  costCenters: ApiEntity[];
  fields: ApiField[];
  sessions: ApiSession[];
};

const emptyRealData: RealData = { machines: [], drivers: [], costCenters: [], fields: [], sessions: [] };

function number(value: number, digits = 1) {
  return value.toLocaleString("es-CL", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function statusLabel(status: DemoSession["status"]) {
  if (status === "active") return "En curso";
  if (status === "paused") return "Pausada";
  return "Completada";
}

function DemoControl({
  demoMode,
  onDemoModeChange,
  running,
  onRunningChange,
  speed,
  onSpeedChange,
}: {
  demoMode: boolean;
  onDemoModeChange: (value: boolean) => void;
  running: boolean;
  onRunningChange: (value: boolean) => void;
  speed: number;
  onSpeedChange: (value: number) => void;
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
  const [selectedVehicleId, setSelectedVehicleId] = useState<string | null>("demo-01");
  const [showRows, setShowRows] = useState(true);
  const [showRoadRoute, setShowRoadRoute] = useState(false);
  const [roadRouteStatus, setRoadRouteStatus] = useState<string | null>(null);
  const [historyQuery, setHistoryQuery] = useState("");
  const [historyStatus, setHistoryStatus] = useState<"all" | DemoSession["status"]>("all");
  const [realData, setRealData] = useState<RealData>(emptyRealData);
  const [realStatus, setRealStatus] = useState<"loading" | "ready" | "error">("loading");

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

  const vehicles = useMemo(() => getDemoVehicles(elapsedSeconds, speed), [elapsedSeconds, speed]);
  const selectedVehicle = vehicles.find((vehicle) => vehicle.id === selectedVehicleId) ?? vehicles[0];
  const selectedField = DEMO_FIELDS.find((field) => field.id === selectedVehicle?.fieldId) ?? DEMO_FIELDS[0];
  const sessions = DEMO_SESSIONS;
  const filteredSessions = sessions.filter((session) => {
    const query = historyQuery.trim().toLowerCase();
    const matchesQuery = !query || `${session.id} ${session.machine} ${session.driver} ${session.field}`.toLowerCase().includes(query);
    return matchesQuery && (historyStatus === "all" || session.status === historyStatus);
  });

  const control = (
    <DemoControl demoMode={demoMode} onDemoModeChange={setDemoMode} running={running} onRunningChange={setRunning} speed={speed} onSpeedChange={setSpeed} />
  );

  if (!demoMode) {
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
          <p className={`ops-source-state is-${realStatus}`}>{realStatus === "ready" ? "API sincronizada" : realStatus === "loading" ? "Sincronizando API…" : "No fue posible sincronizar; intenta nuevamente."}</p>
        </section>
      </main>
    );
  }

  const mapCard = (compact = false) => (
    <section className={`ops-map-card ${compact ? "is-compact" : ""}`}>
      <header>
        <div><span className="section-kicker">Cartografía operacional</span><h2>{selectedField.name}</h2><p>{selectedVehicle.driver} · {selectedField.crop}</p></div>
        <div className="ops-layer-controls">
          <button type="button" className={showRows ? "is-active" : ""} onClick={() => setShowRows(!showRows)}>Pasadas</button>
          <button type="button" className={showRoadRoute ? "is-active" : ""} onClick={() => { const next = !showRoadRoute; setShowRoadRoute(next); if (!next) setRoadRouteStatus(null); }}>Ruta por caminos</button>
        </div>
      </header>
      {roadRouteStatus && <div className="ops-map-notice">{roadRouteStatus}</div>}
      <div className="ops-map-frame">
        <OperationsMap fields={DEMO_FIELDS} vehicles={vehicles} selectedVehicleId={selectedVehicleId} onSelectVehicle={setSelectedVehicleId} showRows={showRows} showRoadRoute={showRoadRoute} onRoadRouteStatus={setRoadRouteStatus} compact={compact} />
      </div>
      <footer><span><i className="ops-dot is-lime" /> Pasadas dentro del lote</span><span><i className="ops-line-sample" /> Caminos calculados por Google</span><b>Dataset demostrativo</b></footer>
    </section>
  );

  if (view === "userView") {
    const fieldProgress = [62, 71, 80, 89];
    const completion = Math.round(fieldProgress.reduce((sum, value) => sum + value, 0) / fieldProgress.length);
    return (
      <main className="ops-workspace">
        {control}<KpiGrid sessions={sessions} fields={DEMO_FIELDS} />
        <div className="ops-summary-grid">
          {mapCard(true)}
          <section className="ops-side-card"><header><span className="section-kicker">Jornada</span><h2>Avance operacional</h2></header>
            <div className="ops-progress-ring" style={{ "--progress": `${Math.min(100, completion)}%` } as React.CSSProperties}><strong>{completion}%</strong><span>cobertura planificada</span></div>
            <div className="ops-progress-list">{DEMO_FIELDS.map((field, index) => <div key={field.id}><span>{field.name}</span><b>{fieldProgress[index]}%</b><i><em style={{ width: `${fieldProgress[index]}%` }} /></i></div>)}</div>
          </section>
        </div>
        <div className="ops-lower-grid">
          <section className="ops-panel"><header><span className="section-kicker">Flota</span><h2>Actividad por máquina</h2></header><div className="ops-fleet-rows">{vehicles.map((vehicle) => <button key={vehicle.id} type="button" onClick={() => { setSelectedVehicleId(vehicle.id); }}><i className="ops-vehicle-avatar">T</i><span><b>{vehicle.name}</b><small>{DEMO_FIELDS.find((field) => field.id === vehicle.fieldId)?.name}</small></span><em>{vehicle.speedKmh.toFixed(1)} km/h</em><strong>{vehicle.coveredHa.toFixed(1)} ha</strong></button>)}</div></section>
          <section className="ops-panel"><header><span className="section-kicker">Eventos</span><h2>Actividad reciente</h2></header><ol className="ops-event-list">{DEMO_EVENTS.map((event) => <li key={`${event.time}-${event.title}`}><time>{event.time}</time><i className={`is-${event.tone}`} /><span><b>{event.title}</b><small>{event.detail}</small></span></li>)}</ol></section>
        </div>
      </main>
    );
  }

  if (view === "live") {
    return (
      <main className="ops-workspace">{control}<KpiGrid sessions={sessions} fields={DEMO_FIELDS} />
        <div className="ops-live-layout"><aside className="ops-fleet-panel"><header><span className="section-kicker">Flota demo</span><h2>4 máquinas en terreno</h2></header>{vehicles.map((vehicle) => <button key={vehicle.id} type="button" className={selectedVehicleId === vehicle.id ? "is-selected" : ""} onClick={() => setSelectedVehicleId(vehicle.id)}><span className="ops-vehicle-avatar">T</span><span><b>{vehicle.name}</b><small>{vehicle.driver}</small></span><em><i className="ops-dot is-green" /> {vehicle.status === "turning" ? "Girando" : "Trabajando"}</em></button>)}</aside>{mapCard(false)}</div>
        <section className="ops-telemetry-strip"><article><span>Velocidad</span><b>{selectedVehicle.speedKmh.toFixed(1)} km/h</b></article><article><span>Combustible</span><b>{selectedVehicle.fuelPct.toFixed(0)}%</b></article><article><span>Horómetro</span><b>{number(selectedVehicle.engineHours)} h</b></article><article><span>Cobertura</span><b>{number(selectedVehicle.coveredHa)} ha</b></article><article><span>Progreso lote</span><b>{Math.round(selectedVehicle.progress * 100)}%</b></article></section>
      </main>
    );
  }

  if (view === "routes") {
    return <main className="ops-workspace">{control}<section className="ops-panel ops-table-panel"><header><div><span className="section-kicker">Rendimiento acumulado</span><h2>Odómetro y utilización</h2><p>La distancia se suma sobre puntos GPS ordenados; no se usa la diagonal entre inicio y fin.</p></div><button className="ops-action">Exportar resumen</button></header><div className="ops-machine-metrics">{vehicles.map((vehicle, index) => <article key={vehicle.id}><div><span className="ops-vehicle-avatar">T</span><span><b>{vehicle.name}</b><small>{vehicle.plate}</small></span><em>{88 - index * 4}% disponibilidad</em></div><dl><div><dt>Odómetro jornada</dt><dd>{number(vehicle.distanceKm)} km</dd></div><div><dt>Horómetro</dt><dd>{number(vehicle.engineHours)} h</dd></div><div><dt>Superficie</dt><dd>{number(vehicle.coveredHa)} ha</dd></div><div><dt>Rendimiento</dt><dd>{number(vehicle.coveredHa / (4.2 + index * .35), 2)} ha/h</dd></div></dl><span className="ops-meter"><i style={{ width: `${72 + index * 6}%` }} /></span></article>)}</div></section>{mapCard(true)}</main>;
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
    const masterCards = [{ label: "Máquinas", value: demoMode ? 4 : realData.machines.length, detail: "4 operativas", icon: "T" },{ label: "Conductores", value: demoMode ? 4 : realData.drivers.length, detail: "licencias al día", icon: "C" },{ label: "Centros de costo", value: demoMode ? 2 : realData.costCenters.length, detail: "estructura activa", icon: "$" },{ label: "Polígonos", value: demoMode ? DEMO_FIELDS.length : realData.fields.length, detail: "geometría validada", icon: "P" }];
    return <main className="ops-workspace">{control}<div className="ops-master-grid">{masterCards.map((card) => <article key={card.label}><span>{card.icon}</span><div><b>{card.value}</b><h3>{card.label}</h3><p>{card.detail}</p></div><button type="button">Administrar</button></article>)}</div><div className="ops-catalog-grid"><section className="ops-panel"><header><span className="section-kicker">Geometría</span><h2>Predios y pasadas registradas</h2></header><div className="ops-field-catalog">{DEMO_FIELDS.map((field) => <article key={field.id}><i style={{ background: field.color }}/><span><b>{field.name}</b><small>{field.crop} · {field.costCenter}</small></span><em>{field.areaHa} ha</em><strong>{Math.floor(field.workPath.length / 2)} pasadas</strong></article>)}</div></section><section className="ops-panel"><header><span className="section-kicker">Salud de datos</span><h2>Controles de calidad</h2></header><ul className="ops-health-list"><li><i className="is-ok">✓</i><span><b>Polígonos cerrados</b><small>4 de 4 geometrías válidas</small></span></li><li><i className="is-ok">✓</i><span><b>Pasadas contenidas</b><small>Sin puntos fuera del lote</small></span></li><li><i className="is-ok">✓</i><span><b>GPS ordenado</b><small>Timestamps crecientes</small></span></li><li><i className="is-warning">!</i><span><b>Sesiones reales antiguas</b><small>4 pendientes de cierre administrativo</small></span></li></ul></section></div></main>;
  }

  return <main className="ops-workspace">{control}<section className="ops-history-toolbar"><div><span className="section-kicker">Trazabilidad</span><h2>Historial de sesiones</h2></div><input type="search" placeholder="Buscar máquina, operador o lote…" value={historyQuery} onChange={(event) => setHistoryQuery(event.target.value)}/><select value={historyStatus} onChange={(event) => setHistoryStatus(event.target.value as typeof historyStatus)}><option value="all">Todos los estados</option><option value="active">En curso</option><option value="completed">Completadas</option><option value="paused">Pausadas</option></select></section><section className="ops-panel ops-session-table"><div className="ops-session-table__head"><span>Sesión</span><span>Máquina / operador</span><span>Lote</span><span>Duración</span><span>Distancia</span><span>Superficie</span><span>Consumo</span><span>Estado</span></div>{filteredSessions.map((session) => <button type="button" key={session.id}><span><b>{session.id}</b><small>{session.startedAt}</small></span><span><b>{session.machine}</b><small>{session.driver}</small></span><span>{session.field}</span><span>{number(session.durationHours)} h</span><span>{number(session.distanceKm)} km</span><span>{number(session.coveredHa)} ha</span><span>{number(session.fuelLiters)} L</span><span><em className={`ops-status is-${session.status}`}>{statusLabel(session.status)}</em></span></button>)}{filteredSessions.length === 0 && <div className="ops-empty">No hay sesiones que coincidan con los filtros.</div>}</section></main>;
}
