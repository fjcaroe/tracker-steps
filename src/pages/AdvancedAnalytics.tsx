import { useMemo, useState } from "react";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend,
  Line, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

export type AdvancedAnalyticsSession = {
  id: string;
  machineId?: string | number;
  machine: string;
  driver: string;
  location: string;
  labor: string;
  startedAt: string;
  status: "open" | "closed";
  hours: number;
  distanceKm: number;
  areaHa: number;
  fuelLiters: number;
  avgSpeedKmh: number;
  points: number;
  stale?: boolean;
};

type Report = "executive" | "trends" | "comparison" | "alerts" | "detail";
type Range = "7" | "30" | "90" | "all";
type Metric = "hours" | "distanceKm" | "areaHa" | "fuelLiters" | "sessions";
type AlertTone = "high" | "medium" | "info";
type AlertRow = { id: string; sessionId: string; tone: AlertTone; title: string; detail: string; machine: string; date: string };
type MachineRow = {
  key: string; name: string; hours: number; distanceKm: number; areaHa: number; fuelLiters: number;
  sessions: number; closed: number; points: number; speedWeighted: number; fuelPerHour: number; areaPerHour: number;
  kmPerHour: number; closurePct: number; gpsPct: number;
};

const DAY = 86_400_000;
const colors = ["#2f9e72", "#d8ff62", "#4c8ad6", "#d94835", "#a86ad8", "#e59a36"];
const reportOptions: { id: Report; label: string; helper: string }[] = [
  { id: "executive", label: "Resumen", helper: "Resultado y variación" },
  { id: "trends", label: "Tendencias", helper: "Evolución y período anterior" },
  { id: "comparison", label: "Comparación", helper: "Equipos, labores y ubicaciones" },
  { id: "alerts", label: "Oportunidades", helper: "Anomalías que requieren revisión" },
  { id: "detail", label: "Detalle", helper: "Sesiones y respaldo" },
];

const sum = (values: number[]) => values.reduce((total, value) => total + value, 0);
const decimal = (value: number, digits = 1) => value.toLocaleString("es-CL", { minimumFractionDigits: digits, maximumFractionDigits: digits });
const localDay = (iso: string) => new Date(iso).toLocaleDateString("sv-SE", { timeZone: "America/Santiago" });
const shortDay = (date: string) => new Date(`${date}T12:00:00`).toLocaleDateString("es-CL", { day: "numeric", month: "short" });
const safe = (value: number | null | undefined) => Number.isFinite(value) ? Math.max(0, Number(value)) : 0;
const median = (values: number[]) => {
  const sorted = values.filter((value) => Number.isFinite(value)).sort((a, b) => a - b);
  if (!sorted.length) return 0;
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
};
const metricMeta: Record<Metric, { label: string; short: string; unit: string }> = {
  hours: { label: "Horas productivas", short: "Horas", unit: "h" },
  distanceKm: { label: "Distancia GPS", short: "Distancia", unit: "km" },
  areaHa: { label: "Superficie cubierta", short: "Superficie", unit: "ha" },
  fuelLiters: { label: "Combustible estimado", short: "Combustible", unit: "L" },
  sessions: { label: "Sesiones registradas", short: "Sesiones", unit: "" },
};

function summarize(rows: AdvancedAnalyticsSession[]) {
  const hours = sum(rows.map((row) => safe(row.hours)));
  const distanceKm = sum(rows.map((row) => safe(row.distanceKm)));
  const areaHa = sum(rows.map((row) => safe(row.areaHa)));
  const fuelLiters = sum(rows.map((row) => safe(row.fuelLiters)));
  const closed = rows.filter((row) => row.status === "closed").length;
  const withGps = rows.filter((row) => row.points > 0).length;
  return {
    sessions: rows.length, hours, distanceKm, areaHa, fuelLiters, closed,
    closurePct: rows.length ? closed / rows.length * 100 : 0,
    gpsPct: rows.length ? withGps / rows.length * 100 : 0,
    fuelPerHour: hours ? fuelLiters / hours : 0,
    areaPerHour: hours ? areaHa / hours : 0,
    kmPerHour: hours ? distanceKm / hours : 0,
  };
}

function groupMachines(rows: AdvancedAnalyticsSession[]): MachineRow[] {
  const grouped = new Map<string, Omit<MachineRow, "fuelPerHour" | "areaPerHour" | "kmPerHour" | "closurePct" | "gpsPct">>();
  rows.forEach((row) => {
    const key = String(row.machineId ?? row.machine);
    const current = grouped.get(key) ?? { key, name: row.machine, hours: 0, distanceKm: 0, areaHa: 0, fuelLiters: 0, sessions: 0, closed: 0, points: 0, speedWeighted: 0 };
    current.hours += safe(row.hours); current.distanceKm += safe(row.distanceKm); current.areaHa += safe(row.areaHa);
    current.fuelLiters += safe(row.fuelLiters); current.sessions += 1; current.closed += row.status === "closed" ? 1 : 0;
    current.points += safe(row.points); current.speedWeighted += safe(row.avgSpeedKmh) * Math.max(safe(row.hours), 0.1);
    grouped.set(key, current);
  });
  return [...grouped.values()].map((row) => ({
    ...row,
    fuelPerHour: row.hours ? row.fuelLiters / row.hours : 0,
    areaPerHour: row.hours ? row.areaHa / row.hours : 0,
    kmPerHour: row.hours ? row.distanceKm / row.hours : 0,
    closurePct: row.sessions ? row.closed / row.sessions * 100 : 0,
    gpsPct: row.sessions ? Math.min(100, row.points > 0 ? 100 : 0) : 0,
  })).sort((a, b) => b.hours - a.hours);
}

function change(current: number, previous: number) {
  if (!previous) return null;
  return (current - previous) / Math.abs(previous) * 100;
}

function Delta({ current, previous, inverse = false }: { current: number; previous: number; inverse?: boolean }) {
  const value = change(current, previous);
  if (value == null) return <small className="analytics-delta is-neutral">Sin base comparable</small>;
  const good = inverse ? value <= 0 : value >= 0;
  return <small className={`analytics-delta ${good ? "is-good" : "is-bad"}`}>{value >= 0 ? "▲" : "▼"} {decimal(Math.abs(value), 0)}% vs. período anterior</small>;
}

export default function AdvancedAnalytics({ sessions, source, onOpenSession }: {
  sessions: AdvancedAnalyticsSession[];
  source: "demo" | "real";
  onOpenSession?: (id: string) => void;
}) {
  const [report, setReport] = useState<Report>("executive");
  const [range, setRange] = useState<Range>("30");
  const [metric, setMetric] = useState<Metric>(source === "demo" ? "areaHa" : "hours");
  const [machine, setMachine] = useState("all");
  const [location, setLocation] = useState("all");
  const [labor, setLabor] = useState("all");
  const [status, setStatus] = useState<"all" | "open" | "closed">("all");
  const [detailQuery, setDetailQuery] = useState("");

  const machineOptions = useMemo(() => [...new Set(sessions.map((row) => row.machine))].sort(), [sessions]);
  const locationOptions = useMemo(() => [...new Set(sessions.map((row) => row.location))].sort(), [sessions]);
  const laborOptions = useMemo(() => [...new Set(sessions.map((row) => row.labor))].sort(), [sessions]);
  const dimensionFiltered = useMemo(() => sessions.filter((row) =>
    (machine === "all" || row.machine === machine) && (location === "all" || row.location === location) &&
    (labor === "all" || row.labor === labor) && (status === "all" || row.status === status)), [labor, location, machine, sessions, status]);

  const newest = useMemo(() => dimensionFiltered.reduce((latest, row) => Math.max(latest, new Date(row.startedAt).getTime()), 0), [dimensionFiltered]);
  const periodDays = range === "all" ? null : Number(range);
  const currentStart = periodDays == null ? 0 : newest - periodDays * DAY;
  const previousStart = periodDays == null ? 0 : currentStart - periodDays * DAY;
  const currentRows = useMemo(() => dimensionFiltered.filter((row) => range === "all" || new Date(row.startedAt).getTime() > currentStart), [currentStart, dimensionFiltered, range]);
  const previousRows = useMemo(() => periodDays == null ? [] : dimensionFiltered.filter((row) => {
    const time = new Date(row.startedAt).getTime(); return time > previousStart && time <= currentStart;
  }), [currentStart, dimensionFiltered, periodDays, previousStart]);
  const current = useMemo(() => summarize(currentRows), [currentRows]);
  const previous = useMemo(() => summarize(previousRows), [previousRows]);
  const machines = useMemo(() => groupMachines(currentRows), [currentRows]);
  const previousMachines = useMemo(() => new Map(groupMachines(previousRows).map((row) => [row.key, row])), [previousRows]);
  const hasArea = currentRows.some((row) => row.areaHa > 0);
  const selectedMetric: Metric = !hasArea && metric === "areaHa" ? "hours" : metric;

  const daily = useMemo(() => {
    const group = (rows: AdvancedAnalyticsSession[]) => {
      const values = new Map<string, { date: string; hours: number; distanceKm: number; areaHa: number; fuelLiters: number; sessions: number }>();
      rows.forEach((row) => {
        const date = localDay(row.startedAt); const value = values.get(date) ?? { date, hours: 0, distanceKm: 0, areaHa: 0, fuelLiters: 0, sessions: 0 };
        value.hours += safe(row.hours); value.distanceKm += safe(row.distanceKm); value.areaHa += safe(row.areaHa); value.fuelLiters += safe(row.fuelLiters); value.sessions += 1; values.set(date, value);
      });
      return [...values.values()].sort((a, b) => a.date.localeCompare(b.date));
    };
    const currentDays = group(currentRows); const previousDays = group(previousRows);
    return currentDays.map((row, index) => ({ ...row, day: shortDay(row.date), previous: previousDays[index]?.[selectedMetric] ?? null }));
  }, [currentRows, previousRows, selectedMetric]);

  const locations = useMemo(() => {
    const grouped = new Map<string, AdvancedAnalyticsSession[]>();
    currentRows.forEach((row) => grouped.set(row.location, [...(grouped.get(row.location) ?? []), row]));
    return [...grouped].map(([name, rows]) => ({ name, ...summarize(rows) })).sort((a, b) => b.hours - a.hours);
  }, [currentRows]);
  const labors = useMemo(() => {
    const grouped = new Map<string, number>(); currentRows.forEach((row) => grouped.set(row.labor, (grouped.get(row.labor) ?? 0) + (source === "demo" ? row.areaHa : row.hours)));
    return [...grouped].map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value);
  }, [currentRows, source]);

  const alerts = useMemo<AlertRow[]>(() => {
    const fuelRates = currentRows.filter((row) => row.hours >= .5 && row.fuelLiters > 0).map((row) => row.fuelLiters / row.hours);
    const fuelBenchmark = median(fuelRates);
    const rows: AlertRow[] = [];
    currentRows.forEach((row) => {
      const date = new Date(row.startedAt).toLocaleDateString("es-CL");
      if (row.stale) rows.push({ id: `${row.id}-stale`, sessionId: row.id, tone: "high", title: "Sesión pendiente de cierre", detail: "Supera 24 horas abierta y fue excluida de horas y combustible.", machine: row.machine, date });
      else if (row.status === "open") rows.push({ id: `${row.id}-open`, sessionId: row.id, tone: "medium", title: "Sesión aún abierta", detail: "Confirme que la operación siga activa o cierre el registro.", machine: row.machine, date });
      if (row.points === 0) rows.push({ id: `${row.id}-gps`, sessionId: row.id, tone: "high", title: "Sin respaldo GPS", detail: "La sesión no tiene puntos almacenados; distancia y recorrido no son auditables.", machine: row.machine, date });
      if (row.status === "closed" && row.hours === 0) rows.push({ id: `${row.id}-hours`, sessionId: row.id, tone: "medium", title: "Duración no calculable", detail: "La sesión está cerrada, pero no registra horas válidas.", machine: row.machine, date });
      const fuelRate = row.hours ? row.fuelLiters / row.hours : 0;
      if (fuelBenchmark > 0 && row.hours >= .5 && fuelRate > fuelBenchmark * 1.35) rows.push({ id: `${row.id}-fuel`, sessionId: row.id, tone: "medium", title: "Consumo horario sobre referencia", detail: `${decimal(fuelRate, 2)} L/h frente a una mediana de ${decimal(fuelBenchmark, 2)} L/h. Compare labor y terreno.`, machine: row.machine, date });
      if (row.avgSpeedKmh > 60) rows.push({ id: `${row.id}-speed`, sessionId: row.id, tone: "high", title: "Velocidad atípica", detail: `${decimal(row.avgSpeedKmh)} km/h promedio; revise la calidad de la telemetría.`, machine: row.machine, date });
    });
    const priority: Record<AlertTone, number> = { high: 0, medium: 1, info: 2 };
    return rows.sort((a, b) => priority[a.tone] - priority[b.tone]);
  }, [currentRows]);

  const filteredDetail = useMemo(() => {
    const query = detailQuery.trim().toLowerCase();
    return currentRows.filter((row) => !query || `${row.id} ${row.machine} ${row.driver} ${row.location} ${row.labor}`.toLowerCase().includes(query));
  }, [currentRows, detailQuery]);

  const resetFilters = () => { setMachine("all"); setLocation("all"); setLabor("all"); setStatus("all"); setDetailQuery(""); };
  const focusMachine = (row: MachineRow) => { setMachine(row.name); setReport("detail"); };
  const exportWorkbook = async () => {
    const XLSX = await import("xlsx");
    const workbook = XLSX.utils.book_new();
    const summary = [
      ["Reporte", "Analítica avanzada Steps Tracker"], ["Fuente", source === "real" ? "Datos productivos" : "Laboratorio demo"], ["Período", range === "all" ? "Todo el histórico" : `Últimos ${range} días`],
      ["Sesiones", current.sessions], ["Horas", current.hours], ["Distancia km", current.distanceKm], ["Superficie ha", current.areaHa], ["Combustible L", current.fuelLiters], ["Cierre %", current.closurePct], ["Cobertura GPS %", current.gpsPct],
    ];
    XLSX.utils.book_append_sheet(workbook, XLSX.utils.aoa_to_sheet(summary), "Resumen");
    XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(filteredDetail.map((row) => ({ Fecha: localDay(row.startedAt), Sesion: row.id, Maquina: row.machine, Conductor: row.driver, Ubicacion: row.location, Labor: row.labor, Horas: row.hours, Distancia_km: row.distanceKm, Superficie_ha: row.areaHa, Combustible_L: row.fuelLiters, Velocidad_kmh: row.avgSpeedKmh, Puntos_GPS: row.points, Estado: row.status === "closed" ? "Cerrada" : "Abierta" }))), "Sesiones");
    XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(machines.map((row) => ({ Maquina: row.name, Sesiones: row.sessions, Horas: row.hours, Distancia_km: row.distanceKm, Superficie_ha: row.areaHa, Combustible_L: row.fuelLiters, Litros_hora: row.fuelPerHour, Cierre_pct: row.closurePct }))), "Equipos");
    XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(alerts.map((row) => ({ Prioridad: row.tone, Fecha: row.date, Maquina: row.machine, Alerta: row.title, Detalle: row.detail, Sesion: row.sessionId }))), "Oportunidades");
    XLSX.writeFile(workbook, `analitica-steps-${source}-${new Date().toISOString().slice(0, 10)}.xlsx`);
  };

  const metricInfo = metricMeta[selectedMetric];
  const maxMachineHours = Math.max(...machines.map((row) => row.hours), 1);
  const activeFilters = [machine, location, labor, status].filter((value) => value !== "all").length;

  return <section className="analytics-center analytics-advanced">
    <header className="analytics-hero"><div><span className="section-kicker">Centro de inteligencia · {source === "real" ? "Fuente productiva" : "Laboratorio demo"}</span><h2>Analítica avanzada para decidir</h2><p>Compare períodos, detecte desviaciones y llegue desde el indicador hasta las sesiones que explican el resultado.</p></div><div className="analytics-hero__actions"><button type="button" className="is-secondary" onClick={() => window.print()}>Imprimir / PDF</button><button type="button" onClick={() => void exportWorkbook()}>Exportar Excel</button></div></header>

    <section className="analytics-filter-panel" aria-label="Filtros del reporte"><label><span>Período</span><select value={range} onChange={(event) => setRange(event.target.value as Range)}><option value="7">Últimos 7 días</option><option value="30">Últimos 30 días</option><option value="90">Últimos 90 días</option><option value="all">Todo el histórico cargado</option></select></label><label><span>Máquina</span><select value={machine} onChange={(event) => setMachine(event.target.value)}><option value="all">Todas las máquinas</option>{machineOptions.map((value) => <option key={value}>{value}</option>)}</select></label><label><span>Ubicación</span><select value={location} onChange={(event) => setLocation(event.target.value)}><option value="all">Todas las ubicaciones</option>{locationOptions.map((value) => <option key={value}>{value}</option>)}</select></label><label><span>Labor</span><select value={labor} onChange={(event) => setLabor(event.target.value)}><option value="all">Todas las labores</option>{laborOptions.map((value) => <option key={value}>{value}</option>)}</select></label><label><span>Estado</span><select value={status} onChange={(event) => setStatus(event.target.value as typeof status)}><option value="all">Todos los estados</option><option value="closed">Cerradas</option><option value="open">Abiertas</option></select></label><button type="button" onClick={resetFilters} disabled={!activeFilters}>Limpiar {activeFilters ? `(${activeFilters})` : ""}</button></section>

    <nav className="analytics-report-tabs" aria-label="Tipos de reporte">{reportOptions.map((option) => <button type="button" key={option.id} className={report === option.id ? "is-active" : ""} onClick={() => setReport(option.id)}><b>{option.label}</b><small>{option.helper}</small></button>)}</nav>

    <div className="analytics-kpis analytics-kpis--six"><article><span>Sesiones</span><b>{current.sessions}</b><Delta current={current.sessions} previous={previous.sessions}/></article><article><span>Horas productivas</span><b>{decimal(current.hours)} h</b><Delta current={current.hours} previous={previous.hours}/></article><article><span>Distancia GPS</span><b>{decimal(current.distanceKm)} km</b><Delta current={current.distanceKm} previous={previous.distanceKm}/></article><article><span>{hasArea ? "Superficie" : "Cobertura GPS"}</span><b>{hasArea ? `${decimal(current.areaHa)} ha` : `${decimal(current.gpsPct, 0)}%`}</b><Delta current={hasArea ? current.areaHa : current.gpsPct} previous={hasArea ? previous.areaHa : previous.gpsPct}/></article><article><span>Combustible</span><b>{decimal(current.fuelLiters)} L</b><Delta current={current.fuelLiters} previous={previous.fuelLiters} inverse/></article><article><span>Cierre de sesiones</span><b>{decimal(current.closurePct, 0)}%</b><Delta current={current.closurePct} previous={previous.closurePct}/></article></div>

    {report === "executive" && <><div className="analytics-insights"><article className={alerts.some((row) => row.tone === "high") ? "is-risk" : "is-positive"}><span>Atención prioritaria</span><b>{alerts.filter((row) => row.tone === "high").length} alertas críticas</b><p>{alerts[0]?.detail ?? "No se detectaron anomalías críticas en el período."}</p></article><article className="is-positive"><span>Equipo con mayor utilización</span><b>{machines[0]?.name ?? "Sin datos"}</b><p>{machines[0] ? `${decimal(machines[0].hours)} h · ${machines[0].sessions} sesiones.` : "No hay sesiones con los filtros actuales."}</p></article><article className={current.closurePct < 85 ? "is-caution" : "is-positive"}><span>Calidad operacional</span><b>{decimal(current.closurePct, 0)}% cerradas · {decimal(current.gpsPct, 0)}% con GPS</b><p>La calidad condiciona qué tan confiables son las comparaciones y tendencias.</p></article></div><div className="ops-charts-grid analytics-grid"><section className="ops-panel ops-chart-main"><header><div><span className="section-kicker">Evolución diaria</span><h2>{metricInfo.label}</h2></div><div className="analytics-metric-switch">{(["hours", "distanceKm", ...(hasArea ? ["areaHa" as Metric] : []), "fuelLiters"] as Metric[]).map((item) => <button type="button" key={item} className={selectedMetric === item ? "is-active" : ""} onClick={() => setMetric(item)}>{metricMeta[item].short}</button>)}</div></header><ResponsiveContainer width="100%" height={300}><AreaChart data={daily}><CartesianGrid vertical={false} stroke="rgba(20,37,31,.09)"/><XAxis dataKey="day" axisLine={false} tickLine={false}/><YAxis axisLine={false} tickLine={false}/><Tooltip formatter={(value) => [`${decimal(Number(value))} ${metricInfo.unit}`, metricInfo.label]}/><Area type="monotone" dataKey={selectedMetric} stroke="#2f9e72" strokeWidth={3} fill="#2f9e7240"/></AreaChart></ResponsiveContainer></section><section className="ops-panel"><header><span className="section-kicker">Distribución</span><h2>{source === "demo" ? "Superficie por labor" : "Horas por labor"}</h2></header><ResponsiveContainer width="100%" height={245}><PieChart><Pie data={labors} dataKey="value" nameKey="name" innerRadius={58} outerRadius={92}>{labors.map((row, index) => <Cell key={row.name} fill={colors[index % colors.length]}/>)}</Pie><Tooltip formatter={(value) => [`${decimal(Number(value))} ${source === "demo" ? "ha" : "h"}`, "Participación"]}/></PieChart></ResponsiveContainer><div className="ops-chart-legend">{labors.slice(0, 6).map((row, index) => <span key={row.name}><i style={{ background: colors[index % colors.length] }}/>{row.name}<b>{decimal(row.value)}</b></span>)}</div></section></div></>}

    {report === "trends" && <div className="analytics-grid-two"><section className="ops-panel analytics-wide"><header><div><span className="section-kicker">Tendencia comparada</span><h2>{metricInfo.label}: período actual vs. anterior</h2></div><div className="analytics-metric-switch">{(["hours", "distanceKm", ...(hasArea ? ["areaHa" as Metric] : []), "fuelLiters", "sessions"] as Metric[]).map((item) => <button type="button" key={item} className={selectedMetric === item ? "is-active" : ""} onClick={() => setMetric(item)}>{metricMeta[item].short}</button>)}</div></header><ResponsiveContainer width="100%" height={340}><ComposedChart data={daily}><CartesianGrid vertical={false} stroke="rgba(20,37,31,.08)"/><XAxis dataKey="day" axisLine={false} tickLine={false}/><YAxis axisLine={false} tickLine={false}/><Tooltip/><Legend/><Area type="monotone" dataKey={selectedMetric} name="Período actual" stroke="#2f9e72" fill="#2f9e7233" strokeWidth={3}/><Line type="monotone" dataKey="previous" name="Período anterior" stroke="#4c8ad6" strokeWidth={2} strokeDasharray="6 4" dot={false}/></ComposedChart></ResponsiveContainer></section><section className="ops-panel"><header><span className="section-kicker">Ratios operativos</span><h2>Eficiencia del período</h2></header><dl className="analytics-ratio-list"><div><dt>Consumo por hora</dt><dd>{decimal(current.fuelPerHour, 2)} L/h</dd><Delta current={current.fuelPerHour} previous={previous.fuelPerHour} inverse/></div><div><dt>Distancia por hora</dt><dd>{decimal(current.kmPerHour, 2)} km/h</dd><Delta current={current.kmPerHour} previous={previous.kmPerHour}/></div>{hasArea && <div><dt>Productividad</dt><dd>{decimal(current.areaPerHour, 2)} ha/h</dd><Delta current={current.areaPerHour} previous={previous.areaPerHour}/></div>}<div><dt>Cobertura GPS</dt><dd>{decimal(current.gpsPct, 0)}%</dd><Delta current={current.gpsPct} previous={previous.gpsPct}/></div></dl></section><section className="ops-panel"><header><span className="section-kicker">Cómo leerlo</span><h2>Una variación necesita contexto</h2></header><ul className="analytics-explain"><li><b>Compare universos equivalentes.</b><span>Los filtros activos se aplican tanto al período actual como al anterior.</span></li><li><b>No confunda menos consumo con mejor resultado.</b><span>Revise junto a horas, distancia, superficie y tipo de labor.</span></li><li><b>Valide el registro.</b><span>Una baja cobertura GPS o sesiones abiertas puede distorsionar la tendencia.</span></li></ul></section></div>}

    {report === "comparison" && <div className="analytics-grid-two"><section className="ops-panel analytics-wide"><header><span className="section-kicker">Comparación de equipos</span><h2>Horas actuales y período anterior</h2></header><ResponsiveContainer width="100%" height={340}><BarChart data={machines.slice(0, 12).map((row) => ({ ...row, previousHours: previousMachines.get(row.key)?.hours ?? 0 }))}><CartesianGrid vertical={false} stroke="rgba(20,37,31,.08)"/><XAxis dataKey="name" axisLine={false} tickLine={false}/><YAxis axisLine={false} tickLine={false}/><Tooltip/><Legend/><Bar dataKey="hours" name="Horas actuales" fill="#2f9e72" radius={[6,6,0,0]}/><Bar dataKey="previousHours" name="Horas anteriores" fill="#b9cae2" radius={[6,6,0,0]}/></BarChart></ResponsiveContainer></section><section className="ops-panel analytics-wide"><header><span className="section-kicker">Matriz de desempeño</span><h2>Indicadores comparables por máquina</h2></header><div className="analytics-machine-matrix">{machines.map((row) => <button type="button" key={row.key} onClick={() => focusMachine(row)}><span><b>{row.name}</b><small>{row.sessions} sesiones · ver detalle</small></span><strong>{decimal(row.hours)} h</strong><em>{decimal(row.fuelPerHour, 2)} L/h</em><em>{decimal(row.kmPerHour, 2)} km/h</em><em>{decimal(row.closurePct, 0)}% cierre</em><i><u style={{ width: `${row.hours / maxMachineHours * 100}%` }}/></i></button>)}</div></section><section className="ops-panel analytics-wide"><header><span className="section-kicker">Ubicaciones</span><h2>Carga y calidad por centro o predio</h2></header><div className="analytics-location-grid">{locations.map((row) => <article key={row.name}><span>{row.name}</span><b>{decimal(row.hours)} h</b><small>{row.sessions} sesiones · {decimal(row.closurePct, 0)}% cierre · {decimal(row.fuelPerHour, 2)} L/h</small></article>)}</div></section></div>}

    {report === "alerts" && <div className="analytics-opportunity-layout"><section className="analytics-opportunity-summary"><article className="is-high"><span>Críticas</span><b>{alerts.filter((row) => row.tone === "high").length}</b><small>GPS, sesiones antiguas o valores atípicos</small></article><article className="is-medium"><span>Revisar</span><b>{alerts.filter((row) => row.tone === "medium").length}</b><small>Cierres y consumo sobre referencia</small></article><article><span>Sesiones limpias</span><b>{Math.max(0, current.sessions - new Set(alerts.map((row) => row.sessionId)).size)}</b><small>Sin reglas de excepción activadas</small></article></section><section className="ops-panel analytics-alert-list"><header><div><span className="section-kicker">Control por excepción</span><h2>Situaciones que merecen revisión humana</h2><p>Son señales para investigar, no conclusiones automáticas.</p></div></header>{alerts.map((row) => <button type="button" key={row.id} onClick={() => { setDetailQuery(row.sessionId); setReport("detail"); }}><i className={`is-${row.tone}`}/><span><b>{row.title}</b><small>{row.machine} · {row.date}</small></span><p>{row.detail}</p><em>Ver sesión</em></button>)}{!alerts.length && <div className="ops-empty">No se detectaron oportunidades con las reglas actuales.</div>}</section></div>}

    {report === "detail" && <section className="ops-panel analytics-detail"><header><div><span className="section-kicker">Auditoría y respaldo</span><h2>Sesiones que explican el reporte</h2><p>La tabla conserva exactamente el mismo período y filtros de los indicadores.</p></div><div className="analytics-detail-actions"><input type="search" aria-label="Buscar sesiones del reporte" placeholder="Buscar sesión, máquina, operador o labor…" value={detailQuery} onChange={(event) => setDetailQuery(event.target.value)}/><button type="button" onClick={() => void exportWorkbook()}>Exportar Excel</button></div></header><div><table><thead><tr><th>Fecha</th><th>Máquina / operador</th><th>Ubicación / labor</th><th>Horas</th><th>Distancia</th>{hasArea && <th>Superficie</th>}<th>Combustible</th><th>GPS</th><th>Estado</th><th/></tr></thead><tbody>{filteredDetail.map((row) => <tr key={row.id}><td>{new Date(row.startedAt).toLocaleDateString("es-CL")}</td><td><b>{row.machine}</b><small>{row.driver}</small></td><td><b>{row.location}</b><small>{row.labor}</small></td><td>{decimal(row.hours)} h</td><td>{decimal(row.distanceKm)} km</td>{hasArea && <td>{decimal(row.areaHa)} ha</td>}<td>{decimal(row.fuelLiters)} L</td><td>{row.points.toLocaleString("es-CL")}</td><td><span className={`analytics-status is-${row.status === "closed" ? "completed" : "active"}`}>{row.stale ? "Pendiente cierre" : row.status === "closed" ? "Cerrada" : "Abierta"}</span></td><td>{onOpenSession && <button type="button" className="analytics-row-action" onClick={() => onOpenSession(row.id)}>Abrir recorrido</button>}</td></tr>)}</tbody></table>{!filteredDetail.length && <div className="ops-empty">No hay sesiones que coincidan con la búsqueda y los filtros.</div>}</div></section>}

    <section className="analytics-definitions" aria-label="Definiciones del reporte"><b>Definiciones</b><span><strong>Horas:</strong> duración efectiva; excluye sesiones abiertas por más de 24 h.</span><span><strong>Distancia:</strong> suma del GPS persistido.</span><span><strong>Combustible:</strong> estimación según máquina, labor y duración/distancia disponibles.</span><span><strong>Comparación:</strong> período inmediatamente anterior con los mismos filtros.</span></section>
    <footer className="analytics-footnote">{source === "real" ? "Fuente: sesiones, telemetría GPS, máquinas, labores y centros de costo autorizados por Tracker." : "Laboratorio demo: datos sintéticos aislados de producción, preparados para explicar tendencias y decisiones."}</footer>
  </section>;
}
