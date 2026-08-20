import { useMemo, useState } from "react";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend,
  Line, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { DemoSession, DemoVehicle } from "../demo/scenario";

type Report = "executive" | "productivity" | "fuel" | "utilization" | "detail";
type Metric = "hectares" | "distance" | "fuel";
type Range = "7" | "30" | "all";
type MachineRow = { name: string; hectares: number; hours: number; fuel: number; distance: number; sessions: number; productivity: number; fuelPerHa: number };

const chartColors = ["#2f9e72", "#d8ff62", "#d94835", "#4c8ad6", "#a86ad8", "#e59a36"];
const reportOptions: { id: Report; label: string; helper: string }[] = [
  { id: "executive", label: "Resumen", helper: "Qué ocurrió y dónde actuar" },
  { id: "productivity", label: "Productividad", helper: "Hectáreas, horas y labores" },
  { id: "fuel", label: "Combustible", helper: "Consumo y oportunidades" },
  { id: "utilization", label: "Uso de flota", helper: "Carga y disponibilidad" },
  { id: "detail", label: "Detalle", helper: "Sesiones y exportación" },
];

function sum(values: number[]) { return values.reduce((total, value) => total + value, 0); }
function decimal(value: number, digits = 1) { return value.toLocaleString("es-CL", { minimumFractionDigits: digits, maximumFractionDigits: digits }); }
function csvCell(value: string | number) { const text = String(value); return /[;"\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text; }

export default function AnalyticsCharts({ vehicles, sessions, regionId, regionName }: { vehicles: DemoVehicle[]; sessions: DemoSession[]; regionId: string; regionName: string }) {
  const [report, setReport] = useState<Report>("executive");
  const [metric, setMetric] = useState<Metric>("hectares");
  const [range, setRange] = useState<Range>("30");
  const [scope, setScope] = useState<"region" | "all">("all");

  const scopedSessions = useMemo(() => {
    const newestTimestamp = sessions.reduce((latest, session) => Math.max(latest, new Date(session.startedAtIso).getTime()), 0);
    const threshold = range === "all" || newestTimestamp === 0 ? null : newestTimestamp - Number(range) * 86_400_000;
    return sessions.filter((session) => (scope === "all" || session.regionId === regionId) && (threshold == null || new Date(session.startedAtIso).getTime() >= threshold));
  }, [range, regionId, scope, sessions]);
  const scopedVehicles = useMemo(() => vehicles.filter((vehicle) => scope === "all" || vehicle.regionId === regionId), [regionId, scope, vehicles]);

  const totals = useMemo(() => {
    const hectares = sum(scopedSessions.map((session) => session.coveredHa));
    const hours = sum(scopedSessions.map((session) => session.durationHours));
    const fuel = sum(scopedSessions.map((session) => session.fuelLiters));
    const distance = sum(scopedSessions.map((session) => session.distanceKm));
    const completed = scopedSessions.filter((session) => session.status === "completed").length;
    return { hectares, hours, fuel, distance, productivity: hours ? hectares / hours : 0, fuelPerHa: hectares ? fuel / hectares : 0, completedPct: scopedSessions.length ? completed / scopedSessions.length * 100 : 0 };
  }, [scopedSessions]);

  const daily = useMemo(() => {
    const grouped = new Map<string, { date: string; hectares: number; distance: number; fuel: number; hours: number }>();
    scopedSessions.forEach((session) => {
      const date = session.startedAtIso.slice(0, 10);
      const row = grouped.get(date) ?? { date, hectares: 0, distance: 0, fuel: 0, hours: 0 };
      row.hectares += session.coveredHa; row.distance += session.distanceKm; row.fuel += session.fuelLiters; row.hours += session.durationHours;
      grouped.set(date, row);
    });
    return [...grouped.values()].sort((a, b) => a.date.localeCompare(b.date)).map((row) => ({ ...row, day: new Date(`${row.date}T12:00`).toLocaleDateString("es-CL", { weekday: "short", day: "numeric" }), productivity: row.hours ? row.hectares / row.hours : 0, fuelPerHa: row.hectares ? row.fuel / row.hectares : 0 }));
  }, [scopedSessions]);

  const machines = useMemo<MachineRow[]>(() => {
    const grouped = new Map<string, Omit<MachineRow, "productivity" | "fuelPerHa">>();
    scopedSessions.forEach((session) => {
      const row = grouped.get(session.machine) ?? { name: session.machine, hectares: 0, hours: 0, fuel: 0, distance: 0, sessions: 0 };
      row.hectares += session.coveredHa; row.hours += session.durationHours; row.fuel += session.fuelLiters; row.distance += session.distanceKm; row.sessions += 1;
      grouped.set(session.machine, row);
    });
    return [...grouped.values()].map((row) => ({ ...row, productivity: row.hours ? row.hectares / row.hours : 0, fuelPerHa: row.hectares ? row.fuel / row.hectares : 0 })).sort((a, b) => b.hectares - a.hectares);
  }, [scopedSessions]);

  const labors = useMemo(() => {
    const grouped = new Map<string, number>();
    scopedSessions.forEach((session) => grouped.set(session.labor, (grouped.get(session.labor) ?? 0) + session.coveredHa));
    return [...grouped].map(([name, value]) => ({ name, value: Number(value.toFixed(1)) })).sort((a, b) => b.value - a.value);
  }, [scopedSessions]);

  const fieldRanking = useMemo(() => {
    const grouped = new Map<string, { name: string; hectares: number; hours: number; fuel: number }>();
    scopedSessions.forEach((session) => {
      const row = grouped.get(session.fieldId) ?? { name: session.field, hectares: 0, hours: 0, fuel: 0 };
      row.hectares += session.coveredHa; row.hours += session.durationHours; row.fuel += session.fuelLiters;
      grouped.set(session.fieldId, row);
    });
    return [...grouped.values()].map((row) => ({ ...row, productivity: row.hours ? row.hectares / row.hours : 0 })).sort((a, b) => b.productivity - a.productivity);
  }, [scopedSessions]);

  const utilization = useMemo(() => scopedVehicles.map((vehicle) => {
    const productive = sum(scopedSessions.filter((session) => session.machine === vehicle.name).map((session) => session.durationHours));
    const capacity = Math.max(8, Math.ceil(productive / 8) * 10);
    return { name: vehicle.name, productive: Number(productive.toFixed(1)), available: Number(Math.max(0, capacity - productive).toFixed(1)), fuelPct: vehicle.fuelPct };
  }).sort((a, b) => b.productive - a.productive), [scopedSessions, scopedVehicles]);

  const statusData = [
    { name: "Trabajando", value: scopedVehicles.filter((vehicle) => vehicle.status === "working" || vehicle.status === "turning").length },
    { name: "Detenida", value: scopedVehicles.filter((vehicle) => vehicle.status === "paused").length },
    { name: "Regresando", value: scopedVehicles.filter((vehicle) => vehicle.status === "returning").length },
  ].filter((item) => item.value > 0);

  const bestMachine = [...machines].sort((a, b) => b.productivity - a.productivity)[0];
  const highFuelMachine = [...machines].sort((a, b) => b.fuelPerHa - a.fuelPerHa)[0];
  const lowFuelVehicles = scopedVehicles.filter((vehicle) => vehicle.fuelPct < 35);
  const contextLabel = scope === "all" ? "Todas las ubicaciones" : regionName;

  const exportCsv = () => {
    const header = ["Fecha", "Máquina", "Conductor", "Predio", "Labor", "Duración h", "Distancia km", "Hectáreas", "Combustible L", "Velocidad km/h", "Estado"];
    const rows = scopedSessions.map((session) => [session.startedAtIso.slice(0, 10), session.machine, session.driver, session.field, session.labor, session.durationHours, session.distanceKm, session.coveredHa, session.fuelLiters, session.avgSpeedKmh, session.status]);
    const csv = [header, ...rows].map((row) => row.map(csvCell).join(";")).join("\n");
    const url = URL.createObjectURL(new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8" }));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = `reporte-tracker-${new Date().toISOString().slice(0, 10)}.csv`; anchor.click(); URL.revokeObjectURL(url);
  };

  const metricTitle = metric === "hectares" ? "Hectáreas cubiertas" : metric === "distance" ? "Distancia recorrida" : "Combustible utilizado";
  const metricUnit = metric === "hectares" ? "ha" : metric === "distance" ? "km" : "L";

  return <section className="analytics-center">
    <header className="analytics-hero"><div><span className="section-kicker">Centro de reportes · {contextLabel}</span><h2>Analítica para decidir y explicar resultados</h2><p>Compare productividad, consumo y utilización. Cada reporte responde una pregunta distinta de la operación.</p></div><div className="analytics-hero__actions"><label><span>Alcance</span><select value={scope} onChange={(event) => setScope(event.target.value as "region" | "all")}><option value="all">Toda la empresa</option><option value="region">{regionName}</option></select></label><label><span>Período</span><select value={range} onChange={(event) => setRange(event.target.value as Range)}><option value="7">Últimos 7 días</option><option value="30">Últimos 30 días</option><option value="all">Todo el histórico</option></select></label><button type="button" onClick={exportCsv}>Descargar datos</button></div></header>

    <nav className="analytics-report-tabs" aria-label="Tipos de reporte">{reportOptions.map((option) => <button type="button" key={option.id} className={report === option.id ? "is-active" : ""} onClick={() => setReport(option.id)}><b>{option.label}</b><small>{option.helper}</small></button>)}</nav>

    <div className="analytics-kpis"><article><span>Superficie</span><b>{decimal(totals.hectares)} ha</b><small>{scopedSessions.length} sesiones consideradas</small></article><article><span>Productividad</span><b>{decimal(totals.productivity, 2)} ha/h</b><small>superficie por hora efectiva</small></article><article><span>Consumo específico</span><b>{decimal(totals.fuelPerHa, 2)} L/ha</b><small>{decimal(totals.fuel, 0)} litros utilizados</small></article><article><span>Cierre de sesiones</span><b>{decimal(totals.completedPct, 0)}%</b><small>{decimal(totals.hours)} horas registradas</small></article></div>

    {report === "executive" && <>
      <div className="analytics-insights"><article className="is-positive"><span>Mejor rendimiento</span><b>{bestMachine?.name ?? "Sin datos"}</b><p>{bestMachine ? `${decimal(bestMachine.productivity, 2)} ha/h en el período consultado.` : "No hay sesiones en el período."}</p></article><article className="is-caution"><span>Revisar consumo</span><b>{highFuelMachine?.name ?? "Sin datos"}</b><p>{highFuelMachine ? `${decimal(highFuelMachine.fuelPerHa, 2)} L/ha; compárelo con labor y terreno.` : "No hay consumo registrado."}</p></article><article className={lowFuelVehicles.length ? "is-risk" : "is-positive"}><span>Situación actual</span><b>{lowFuelVehicles.length ? `${lowFuelVehicles.length} con combustible bajo` : "Flota abastecida"}</b><p>{lowFuelVehicles.length ? lowFuelVehicles.map((vehicle) => vehicle.name).join(", ") : "Ninguna máquina está bajo el 35%."}</p></article></div>
      <div className="ops-charts-grid analytics-grid"><section className="ops-panel ops-chart-main"><header><div><span className="section-kicker">Evolución diaria</span><h2>{metricTitle}</h2></div><div className="analytics-metric-switch">{(["hectares", "distance", "fuel"] as Metric[]).map((item) => <button type="button" key={item} className={metric === item ? "is-active" : ""} onClick={() => setMetric(item)}>{item === "hectares" ? "Hectáreas" : item === "distance" ? "Distancia" : "Combustible"}</button>)}</div></header><ResponsiveContainer width="100%" height={300}><AreaChart data={daily}><defs><linearGradient id="analyticsArea" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#2f9e72" stopOpacity={.38}/><stop offset="95%" stopColor="#2f9e72" stopOpacity={0}/></linearGradient></defs><CartesianGrid vertical={false} stroke="rgba(20,37,31,.09)"/><XAxis dataKey="day" axisLine={false} tickLine={false}/><YAxis axisLine={false} tickLine={false}/><Tooltip formatter={(value) => [`${decimal(Number(value))} ${metricUnit}`, metricTitle]}/><Area type="monotone" dataKey={metric} stroke="#2f9e72" strokeWidth={3} fill="url(#analyticsArea)"/></AreaChart></ResponsiveContainer></section><section className="ops-panel"><header><span className="section-kicker">Ranking</span><h2>Superficie por máquina</h2></header><ResponsiveContainer width="100%" height={300}><BarChart data={machines.slice(0, 6)} layout="vertical" margin={{ left: 8, right: 22 }}><CartesianGrid horizontal={false} stroke="rgba(20,37,31,.08)"/><XAxis type="number" hide/><YAxis type="category" dataKey="name" width={92} axisLine={false} tickLine={false}/><Tooltip formatter={(value) => [`${decimal(Number(value))} ha`, "Superficie"]}/><Bar dataKey="hectares" fill="#d8ff62" stroke="#123c33" radius={[0, 8, 8, 0]}/></BarChart></ResponsiveContainer></section></div>
    </>}

    {report === "productivity" && <div className="analytics-grid-two"><section className="ops-panel"><header><span className="section-kicker">Comparación de equipos</span><h2>Productividad y superficie</h2></header><ResponsiveContainer width="100%" height={330}><ComposedChart data={machines}><CartesianGrid vertical={false} stroke="rgba(20,37,31,.08)"/><XAxis dataKey="name" axisLine={false} tickLine={false}/><YAxis yAxisId="left" axisLine={false} tickLine={false}/><YAxis yAxisId="right" orientation="right" axisLine={false} tickLine={false}/><Tooltip/><Legend/><Bar yAxisId="left" dataKey="hectares" name="Hectáreas" fill="#d8ff62" radius={[7,7,0,0]}/><Line yAxisId="right" dataKey="productivity" name="ha/h" stroke="#2f9e72" strokeWidth={3}/></ComposedChart></ResponsiveContainer></section><section className="ops-panel"><header><span className="section-kicker">Composición</span><h2>Superficie por labor</h2></header><ResponsiveContainer width="100%" height={245}><PieChart><Pie data={labors} dataKey="value" nameKey="name" innerRadius={58} outerRadius={92} paddingAngle={3}>{labors.map((item, index) => <Cell key={item.name} fill={chartColors[index % chartColors.length]}/>)}</Pie><Tooltip formatter={(value) => [`${decimal(Number(value))} ha`, "Superficie"]}/></PieChart></ResponsiveContainer><div className="ops-chart-legend">{labors.map((item, index) => <span key={item.name}><i style={{ background: chartColors[index % chartColors.length] }}/>{item.name}<b>{decimal(item.value)} ha</b></span>)}</div></section><section className="ops-panel analytics-wide"><header><span className="section-kicker">Predios</span><h2>Rendimiento por terreno</h2></header><div className="analytics-ranking-list">{fieldRanking.map((field, index) => <div key={field.name}><b>{index + 1}</b><span><strong>{field.name}</strong><small>{decimal(field.hectares)} ha · {decimal(field.hours)} h</small></span><i><em style={{ width: `${Math.min(100, field.productivity / Math.max(...fieldRanking.map((item) => item.productivity), 1) * 100)}%` }}/></i><strong>{decimal(field.productivity, 2)} ha/h</strong></div>)}</div></section></div>}

    {report === "fuel" && <div className="analytics-grid-two"><section className="ops-panel analytics-wide"><header><span className="section-kicker">Evolución</span><h2>Litros utilizados y consumo por hectárea</h2></header><ResponsiveContainer width="100%" height={320}><ComposedChart data={daily}><CartesianGrid vertical={false} stroke="rgba(20,37,31,.08)"/><XAxis dataKey="day" axisLine={false} tickLine={false}/><YAxis yAxisId="left" axisLine={false} tickLine={false}/><YAxis yAxisId="right" orientation="right" axisLine={false} tickLine={false}/><Tooltip/><Legend/><Bar yAxisId="left" dataKey="fuel" name="Litros" fill="#4c8ad6" radius={[7,7,0,0]}/><Line yAxisId="right" dataKey="fuelPerHa" name="L/ha" stroke="#d94835" strokeWidth={3}/></ComposedChart></ResponsiveContainer></section><section className="ops-panel"><header><span className="section-kicker">Comparación</span><h2>Consumo específico por máquina</h2></header><ResponsiveContainer width="100%" height={290}><BarChart data={[...machines].sort((a,b) => b.fuelPerHa-a.fuelPerHa)} layout="vertical"><XAxis type="number" hide/><YAxis type="category" dataKey="name" width={100} axisLine={false} tickLine={false}/><Tooltip formatter={(value) => [`${decimal(Number(value), 2)} L/ha`, "Consumo"]}/><Bar dataKey="fuelPerHa" fill="#d94835" radius={[0,8,8,0]}/></BarChart></ResponsiveContainer></section><section className="ops-panel"><header><span className="section-kicker">Lectura recomendada</span><h2>Cómo interpretar el consumo</h2></header><ul className="analytics-explain"><li><b>Compare labores semejantes.</b><span>Una aplicación y un traslado no deberían evaluarse con la misma referencia.</span></li><li><b>Observe el predio.</b><span>Pendiente, giros y accesos pueden aumentar litros por hectárea.</span></li><li><b>Revise tendencia, no un dato aislado.</b><span>Una jornada atípica necesita contexto antes de tomar una decisión.</span></li></ul></section></div>}

    {report === "utilization" && <div className="analytics-grid-two"><section className="ops-panel analytics-wide"><header><span className="section-kicker">Carga registrada</span><h2>Horas productivas y capacidad disponible</h2></header><ResponsiveContainer width="100%" height={340}><BarChart data={utilization}><CartesianGrid vertical={false} stroke="rgba(20,37,31,.08)"/><XAxis dataKey="name" axisLine={false} tickLine={false}/><YAxis axisLine={false} tickLine={false}/><Tooltip/><Legend/><Bar stackId="hours" dataKey="productive" name="Horas productivas" fill="#2f9e72"/><Bar stackId="hours" dataKey="available" name="Capacidad disponible" fill="#e8ece8" radius={[7,7,0,0]}/></BarChart></ResponsiveContainer></section><section className="ops-panel"><header><span className="section-kicker">Estado en vivo</span><h2>Situación de la flota</h2></header><ResponsiveContainer width="100%" height={240}><PieChart><Pie data={statusData} dataKey="value" nameKey="name" innerRadius={58} outerRadius={90}>{statusData.map((item,index)=><Cell key={item.name} fill={chartColors[index]}/>)}</Pie><Tooltip/></PieChart></ResponsiveContainer><div className="ops-chart-legend">{statusData.map((item,index)=><span key={item.name}><i style={{background:chartColors[index]}}/>{item.name}<b>{item.value}</b></span>)}</div></section><section className="ops-panel"><header><span className="section-kicker">Abastecimiento</span><h2>Combustible disponible</h2></header><div className="analytics-fuel-list">{utilization.map((vehicle) => <div key={vehicle.name}><span><b>{vehicle.name}</b><small>{decimal(vehicle.fuelPct,0)}% disponible</small></span><i><em className={vehicle.fuelPct < 35 ? "is-low" : ""} style={{width:`${vehicle.fuelPct}%`}}/></i></div>)}</div></section></div>}

    {report === "detail" && <section className="ops-panel analytics-detail"><header><div><span className="section-kicker">Auditoría y respaldo</span><h2>Detalle de sesiones incluidas</h2><p>La tabla usa exactamente los mismos filtros de alcance y período que los gráficos.</p></div><button type="button" onClick={exportCsv}>Exportar CSV</button></header><div><table><thead><tr><th>Fecha</th><th>Máquina / operador</th><th>Predio / labor</th><th>Duración</th><th>Distancia</th><th>Superficie</th><th>Combustible</th><th>Estado</th></tr></thead><tbody>{scopedSessions.map((session) => <tr key={session.id}><td>{new Date(session.startedAtIso).toLocaleDateString("es-CL")}</td><td><b>{session.machine}</b><small>{session.driver}</small></td><td><b>{session.field}</b><small>{session.labor}</small></td><td>{decimal(session.durationHours)} h</td><td>{decimal(session.distanceKm)} km</td><td>{decimal(session.coveredHa)} ha</td><td>{decimal(session.fuelLiters)} L</td><td><span className={`analytics-status is-${session.status}`}>{session.status === "completed" ? "Completada" : session.status === "active" ? "Activa" : "Pausada"}</span></td></tr>)}</tbody></table>{!scopedSessions.length && <div className="ops-empty">No hay sesiones para los filtros seleccionados.</div>}</div></section>}

    <footer className="analytics-footnote">Datos demostrativos mientras el modo Demo está activo. En producción, estos reportes deben alimentarse desde sesiones, partes y maestros sincronizados por la API.</footer>
  </section>;
}
