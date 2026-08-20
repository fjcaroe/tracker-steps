import { useMemo, useState } from "react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Line, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export type RealAnalyticsSession = {
  id: string;
  machineId: number;
  machine: string;
  driver: string;
  location: string;
  labor: string;
  startedAt: string;
  status: "open" | "closed";
  hours: number;
  distanceKm: number;
  fuelLiters: number;
  avgSpeedKmh: number;
  points: number;
};

type Range = "7" | "30" | "all";
type Metric = "distance" | "hours" | "fuel";
const colors = ["#2f9e72", "#d8ff62", "#4c8ad6", "#d94835", "#a86ad8", "#e59a36"];
const sum = (values: number[]) => values.reduce((total, value) => total + value, 0);
const decimal = (value: number, digits = 1) => value.toLocaleString("es-CL", { minimumFractionDigits: digits, maximumFractionDigits: digits });
const csvCell = (value: string | number) => /[;"\n]/.test(String(value)) ? `"${String(value).replaceAll('"', '""')}"` : String(value);

export default function RealAnalyticsCharts({ sessions }: { sessions: RealAnalyticsSession[] }) {
  const [range, setRange] = useState<Range>("30");
  const [metric, setMetric] = useState<Metric>("distance");
  const filtered = useMemo(() => {
    const newest = sessions.reduce((latest, session) => Math.max(latest, new Date(session.startedAt).getTime()), 0);
    const threshold = range === "all" ? 0 : newest - Number(range) * 86_400_000;
    return sessions.filter((session) => new Date(session.startedAt).getTime() >= threshold);
  }, [range, sessions]);

  const totals = useMemo(() => ({
    distance: sum(filtered.map((item) => item.distanceKm)), hours: sum(filtered.map((item) => item.hours)),
    fuel: sum(filtered.map((item) => item.fuelLiters)), points: sum(filtered.map((item) => item.points)),
    closed: filtered.filter((item) => item.status === "closed").length,
  }), [filtered]);
  const daily = useMemo(() => {
    const rows = new Map<string, { date: string; distance: number; hours: number; fuel: number; sessions: number }>();
    filtered.forEach((item) => { const date = item.startedAt.slice(0, 10); const row = rows.get(date) ?? { date, distance: 0, hours: 0, fuel: 0, sessions: 0 }; row.distance += item.distanceKm; row.hours += item.hours; row.fuel += item.fuelLiters; row.sessions += 1; rows.set(date, row); });
    return [...rows.values()].sort((a, b) => a.date.localeCompare(b.date)).map((row) => ({ ...row, day: new Date(`${row.date}T12:00`).toLocaleDateString("es-CL", { day: "numeric", month: "short" }) }));
  }, [filtered]);
  const machines = useMemo(() => {
    const rows = new Map<string, { name: string; distance: number; hours: number; fuel: number; sessions: number }>();
    filtered.forEach((item) => { const row = rows.get(item.machine) ?? { name: item.machine, distance: 0, hours: 0, fuel: 0, sessions: 0 }; row.distance += item.distanceKm; row.hours += item.hours; row.fuel += item.fuelLiters; row.sessions += 1; rows.set(item.machine, row); });
    return [...rows.values()].map((row) => ({ ...row, fuelPerHour: row.hours ? row.fuel / row.hours : 0, kmPerHour: row.hours ? row.distance / row.hours : 0 })).sort((a, b) => b.hours - a.hours);
  }, [filtered]);
  const labors = useMemo(() => {
    const rows = new Map<string, number>(); filtered.forEach((item) => rows.set(item.labor, (rows.get(item.labor) ?? 0) + item.hours));
    return [...rows].map(([name, value]) => ({ name, value: Number(value.toFixed(2)) })).sort((a, b) => b.value - a.value);
  }, [filtered]);
  const metricInfo = metric === "distance" ? ["Distancia recorrida", "km"] : metric === "hours" ? ["Horas registradas", "h"] : ["Combustible estimado", "L"];
  const busiest = machines[0];
  const inefficient = [...machines].filter((item) => item.hours > 0).sort((a, b) => b.fuelPerHour - a.fuelPerHour)[0];

  const exportCsv = () => {
    const rows = [["Fecha", "Máquina", "Conductor", "Ubicación", "Labor", "Horas", "Distancia km", "Combustible L", "Velocidad km/h", "Puntos GPS", "Estado"], ...filtered.map((item) => [item.startedAt.slice(0, 10), item.machine, item.driver, item.location, item.labor, item.hours, item.distanceKm, item.fuelLiters, item.avgSpeedKmh, item.points, item.status === "closed" ? "Cerrada" : "Abierta"] )];
    const url = URL.createObjectURL(new Blob([`\uFEFF${rows.map((row) => row.map(csvCell).join(";")).join("\n")}`], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a"); link.href = url; link.download = `analitica-tracker-real-${new Date().toISOString().slice(0, 10)}.csv`; link.click(); URL.revokeObjectURL(url);
  };

  return <section className="analytics-center">
    <header className="analytics-hero"><div><span className="section-kicker">Centro de reportes · Fuente productiva</span><h2>Analítica basada en sesiones reales</h2><p>Las cifras provienen de Tracker. No se mezclan datos del laboratorio demostrativo.</p></div><div className="analytics-hero__actions"><label><span>Período</span><select value={range} onChange={(event) => setRange(event.target.value as Range)}><option value="7">Últimos 7 días</option><option value="30">Últimos 30 días</option><option value="all">Todo el histórico cargado</option></select></label><button type="button" onClick={exportCsv}>Descargar datos</button></div></header>
    <div className="analytics-kpis"><article><span>Sesiones</span><b>{filtered.length}</b><small>{totals.closed} cerradas · {filtered.length - totals.closed} abiertas</small></article><article><span>Horas registradas</span><b>{decimal(totals.hours)} h</b><small>{decimal(totals.hours ? totals.distance / totals.hours : 0, 2)} km por hora</small></article><article><span>Distancia GPS</span><b>{decimal(totals.distance)} km</b><small>{totals.points.toLocaleString("es-CL")} puntos almacenados</small></article><article><span>Combustible estimado</span><b>{decimal(totals.fuel)} L</b><small>{decimal(totals.hours ? totals.fuel / totals.hours : 0, 2)} L por hora</small></article></div>
    <div className="analytics-insights"><article className="is-positive"><span>Mayor utilización</span><b>{busiest?.name ?? "Sin datos"}</b><p>{busiest ? `${decimal(busiest.hours)} horas en ${busiest.sessions} sesiones.` : "No hay sesiones para el período."}</p></article><article className="is-caution"><span>Revisar consumo horario</span><b>{inefficient?.name ?? "Sin datos"}</b><p>{inefficient ? `${decimal(inefficient.fuelPerHour, 2)} L/h estimados; conviene comparar labor y terreno.` : "Aún no hay consumo calculable."}</p></article><article className={filtered.some((item) => item.status === "open") ? "is-caution" : "is-positive"}><span>Control operacional</span><b>{filtered.filter((item) => item.status === "open").length} sesiones abiertas</b><p>Revise cierres pendientes para consolidar duración y distancia.</p></article></div>
    <div className="ops-charts-grid analytics-grid"><section className="ops-panel ops-chart-main"><header><div><span className="section-kicker">Evolución diaria</span><h2>{metricInfo[0]}</h2></div><div className="analytics-metric-switch">{(["distance", "hours", "fuel"] as Metric[]).map((item) => <button type="button" key={item} className={metric === item ? "is-active" : ""} onClick={() => setMetric(item)}>{item === "distance" ? "Distancia" : item === "hours" ? "Horas" : "Combustible"}</button>)}</div></header><ResponsiveContainer width="100%" height={300}><AreaChart data={daily}><CartesianGrid vertical={false} stroke="rgba(20,37,31,.09)"/><XAxis dataKey="day" axisLine={false} tickLine={false}/><YAxis axisLine={false} tickLine={false}/><Tooltip formatter={(value) => [`${decimal(Number(value))} ${metricInfo[1]}`, metricInfo[0]]}/><Area type="monotone" dataKey={metric} stroke="#2f9e72" strokeWidth={3} fill="#2f9e7240"/></AreaChart></ResponsiveContainer></section><section className="ops-panel"><header><span className="section-kicker">Uso de flota</span><h2>Horas por máquina</h2></header><ResponsiveContainer width="100%" height={300}><BarChart data={machines.slice(0, 8)} layout="vertical"><XAxis type="number" hide/><YAxis type="category" dataKey="name" width={110} axisLine={false} tickLine={false}/><Tooltip formatter={(value) => [`${decimal(Number(value))} h`, "Horas"]}/><Bar dataKey="hours" fill="#d8ff62" stroke="#123c33" radius={[0, 8, 8, 0]}/></BarChart></ResponsiveContainer></section></div>
    <div className="analytics-grid-two"><section className="ops-panel analytics-wide"><header><span className="section-kicker">Eficiencia comparada</span><h2>Distancia, combustible y horas por equipo</h2></header><ResponsiveContainer width="100%" height={330}><BarChart data={machines}><CartesianGrid vertical={false} stroke="rgba(20,37,31,.08)"/><XAxis dataKey="name" axisLine={false} tickLine={false}/><YAxis axisLine={false} tickLine={false}/><Tooltip/><Legend/><Bar dataKey="distance" name="Distancia km" fill="#4c8ad6"/><Bar dataKey="fuel" name="Combustible L" fill="#e59a36"/><Line type="monotone" dataKey="hours" name="Horas" stroke="#123c33" strokeWidth={3}/></BarChart></ResponsiveContainer></section><section className="ops-panel"><header><span className="section-kicker">Distribución</span><h2>Horas por labor</h2></header><ResponsiveContainer width="100%" height={245}><PieChart><Pie data={labors} dataKey="value" nameKey="name" innerRadius={58} outerRadius={92}>{labors.map((item, index) => <Cell key={item.name} fill={colors[index % colors.length]}/>)}</Pie><Tooltip formatter={(value) => [`${decimal(Number(value))} h`, "Horas"]}/></PieChart></ResponsiveContainer><div className="ops-chart-legend">{labors.slice(0, 6).map((item, index) => <span key={item.name}><i style={{ background: colors[index % colors.length] }}/>{item.name}<b>{decimal(item.value)} h</b></span>)}</div></section></div>
    <section className="ops-panel analytics-detail"><header><div><span className="section-kicker">Auditoría</span><h2>Sesiones incluidas en el reporte</h2></div><button type="button" onClick={exportCsv}>Exportar CSV</button></header><div><table><thead><tr><th>Fecha</th><th>Máquina / operador</th><th>Ubicación / labor</th><th>Horas</th><th>Distancia</th><th>Combustible</th><th>Puntos GPS</th><th>Estado</th></tr></thead><tbody>{filtered.map((item) => <tr key={item.id}><td>{new Date(item.startedAt).toLocaleDateString("es-CL")}</td><td><b>{item.machine}</b><small>{item.driver}</small></td><td><b>{item.location}</b><small>{item.labor}</small></td><td>{decimal(item.hours)} h</td><td>{decimal(item.distanceKm)} km</td><td>{decimal(item.fuelLiters)} L</td><td>{item.points.toLocaleString("es-CL")}</td><td><span className={`analytics-status is-${item.status === "closed" ? "completed" : "active"}`}>{item.status === "closed" ? "Cerrada" : "Abierta"}</span></td></tr>)}</tbody></table>{!filtered.length && <div className="ops-empty">No hay sesiones reales para el período seleccionado.</div>}</div></section>
    <footer className="analytics-footnote">Fuente: sesiones, telemetría GPS, máquinas, labores y centros de costo sincronizados por la API de Tracker.</footer>
  </section>;
}
