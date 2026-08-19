import { useState } from "react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { DEMO_DAILY, type DemoVehicle } from "../demo/scenario";

const chartColors = ["#2f9e72", "#d8ff62", "#d94835", "#4c8ad6"];

export default function AnalyticsCharts({ vehicles }: { vehicles: DemoVehicle[] }) {
  const [metric, setMetric] = useState<"hectares" | "distance" | "fuel">("hectares");
  const pieData = vehicles.map((vehicle) => ({ name: vehicle.name, value: Number(vehicle.coveredHa.toFixed(1)) }));
  const title = metric === "hectares" ? "Superficie cubierta" : metric === "distance" ? "Distancia recorrida" : "Consumo de combustible";
  return (
    <>
      <section className="ops-chart-toolbar"><div><span className="section-kicker">Explorador</span><h2>Tendencias de la operación</h2></div><div>{(["hectares", "distance", "fuel"] as const).map((item) => <button type="button" key={item} className={metric === item ? "is-active" : ""} onClick={() => setMetric(item)}>{item === "hectares" ? "Hectáreas" : item === "distance" ? "Distancia" : "Combustible"}</button>)}</div></section>
      <div className="ops-charts-grid">
        <section className="ops-panel ops-chart-main"><header><span className="section-kicker">Últimos 7 días</span><h2>{title}</h2></header><ResponsiveContainer width="100%" height={320}><AreaChart data={DEMO_DAILY}><defs><linearGradient id="opsArea" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#2f9e72" stopOpacity={.35}/><stop offset="95%" stopColor="#2f9e72" stopOpacity={0}/></linearGradient></defs><CartesianGrid vertical={false} stroke="rgba(20,37,31,.09)"/><XAxis dataKey="day" axisLine={false} tickLine={false}/><YAxis axisLine={false} tickLine={false}/><Tooltip/><Area type="monotone" dataKey={metric} stroke="#2f9e72" strokeWidth={3} fill="url(#opsArea)"/></AreaChart></ResponsiveContainer></section>
        <section className="ops-panel"><header><span className="section-kicker">Distribución</span><h2>Cobertura por máquina</h2></header><ResponsiveContainer width="100%" height={250}><PieChart><Pie data={pieData} dataKey="value" nameKey="name" innerRadius={62} outerRadius={92} paddingAngle={3}>{pieData.map((entry, index) => <Cell key={entry.name} fill={chartColors[index % chartColors.length]}/>)}</Pie><Tooltip/></PieChart></ResponsiveContainer><div className="ops-chart-legend">{pieData.map((item, index) => <span key={item.name}><i style={{ background: chartColors[index] }}/>{item.name}<b>{item.value} ha</b></span>)}</div></section>
        <section className="ops-panel ops-chart-wide"><header><span className="section-kicker">Productividad</span><h2>Eficiencia diaria</h2></header><ResponsiveContainer width="100%" height={240}><BarChart data={DEMO_DAILY}><CartesianGrid vertical={false} stroke="rgba(20,37,31,.09)"/><XAxis dataKey="day" axisLine={false} tickLine={false}/><YAxis domain={[0,100]} axisLine={false} tickLine={false}/><Tooltip/><Bar dataKey="efficiency" fill="#d8ff62" stroke="#123c33" radius={[8,8,0,0]}/></BarChart></ResponsiveContainer></section>
      </div>
    </>
  );
}
