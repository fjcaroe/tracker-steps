import { useEffect, useMemo, useRef, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fleetRequest, type FleetAsset, type FleetContext } from "../services/fleetApi";
import { operationsCsv, operationsMetrics } from "../services/operationsMetrics";
import type { TrailPoint } from "../services/fleetTrail";
import "./FleetComparison.css";

type LoadResult = {
  rows: TrailPoint[];
  cursor: string | null;
  error: string;
  loading: boolean;
  round: number;
};
type Period = { from: number; to: number };
const format = (value: number, digits = 1) => value.toLocaleString("es-CL", { maximumFractionDigits: digits });
const palette = ["#2563eb", "#b45309", "#7c3aed", "#0f766e", "#be185d", "#15803d", "#c2410c", "#475569"];

export default function FleetComparison({ assets, context, period, initialAssetId }: {
  assets: FleetAsset[];
  context: FleetContext;
  period: Period;
  initialAssetId: string;
}) {
  const [selectedIds, setSelectedIds] = useState([initialAssetId]);
  const [round, setRound] = useState(0);
  const scope = [context.tenant_key, context.company_id, context.user_id, period.from, period.to].join(":");
  const cache = useRef<{ scope: string; items: Record<string, LoadResult> }>({ scope, items: {} });
  const [data, setData] = useState<{ scope: string; items: Record<string, LoadResult> }>({ scope, items: {} });
  const selected = assets.filter(asset => selectedIds.includes(asset.asset_id));
  const selectionKey = JSON.stringify(selected.map(asset => asset.asset_id).sort());
  const colorIds = assets.map(asset => asset.asset_id).sort();

  useEffect(() => {
    let active = true;
    if (cache.current.scope !== scope) cache.current = { scope, items: {} };
    const publish = () => {
      if (active) setData({ scope, items: { ...cache.current.items } });
    };
    const pending = (JSON.parse(selectionKey) as string[]).filter(id => {
      const result = cache.current.items[id];
      return !result || result.loading || (result.round < round && (!!result.cursor || !!result.error));
    });
    publish();
    async function worker() {
      while (pending.length && active) {
        const id = pending.shift()!;
        const previous = cache.current.items[id];
        const rows = [...(previous?.rows || [])];
        let cursor = previous?.cursor || null;
        cache.current.items[id] = { rows: [...rows], cursor, loading: true, error: "", round };
        publish();
        try {
          for (let page = 0; page < 20; page++) {
            const result = await fleetRequest<{ items: TrailPoint[]; next_cursor: string | null }>(
              `assets/${id}/positions?limit=500&since=${encodeURIComponent(new Date(period.from).toISOString())}${cursor ? "&before=" + encodeURIComponent(cursor) : ""}`, context);
            if (!active) return;
            rows.push(...result.items);
            cursor = result.next_cursor;
            if (!cursor) break;
          }
          cache.current.items[id] = { rows, cursor, loading: false, error: "", round };
        } catch (error) {
          if (!active) return;
          cache.current.items[id] = {
            rows: previous?.rows || [], cursor: previous?.cursor || null,
            loading: false, error: (error as Error).message, round,
          };
        }
        publish();
      }
    }
    void Promise.all(Array.from({ length: Math.min(3, pending.length) }, () => worker()));
    return () => { active = false; };
  }, [scope, selectionKey, round, context, period.from]);

  const items = useMemo(() => assets.filter(asset => selectedIds.includes(asset.asset_id)).map(asset => {
    const result = data.scope === scope ? data.items[asset.asset_id] : undefined;
    const metrics = operationsMetrics(result && !result.error ? result.rows : [], period.from, period.to);
    return { asset, result, metrics };
  }), [assets, selectedIds, data, scope, period]);
  const loading = items.some(({ result }) => !result || result.loading ||
    (result.round < round && (!!result.cursor || !!result.error)));
  const incomplete = items.some(item => item.result?.cursor || item.result?.error || item.metrics.points.length < 2);
  const usable = items.filter(item => !item.result?.error && item.metrics.points.length > 1);
  const total = {
    distanceKm: usable.reduce((sum, item) => sum + item.metrics.distanceM / 1000, 0),
    movingMinutes: usable.reduce((sum, item) => sum + item.metrics.movingSeconds / 60, 0),
    points: items.reduce((sum, item) => sum + item.metrics.points.length, 0),
    stops: items.reduce((sum, item) => sum + item.metrics.stops.length, 0),
  };
  const colorFor = (id: string) => {
    const index = colorIds.indexOf(id);
    return palette[index] || `hsl(${(index * 137.508) % 360} 65% 36%)`;
  };
  const daily = useMemo(() => {
    const days = [...new Set(items.flatMap(item => item.metrics.daily.map(row => row.day)))].sort();
    if (!days.length) return [];
    const rows: Record<string, string | number | null>[] = [];
    const last = Date.parse(days.at(-1)! + "T12:00:00Z");
    for (let time = Date.parse(days[0] + "T12:00:00Z"); time <= last; time += 86400000) {
      const day = new Date(time).toISOString().slice(0, 10);
      const row: Record<string, string | number | null> = { day };
      for (const item of items) {
        row[item.asset.asset_id] = item.metrics.points.length > 1 ?
          item.metrics.daily.find(value => value.day === day)?.km ?? null : null;
      }
      rows.push(row);
    }
    return rows;
  }, [items]);
  const toggle = (id: string) => setSelectedIds(ids => ids.includes(id) ? ids.filter(value => value !== id) : [...ids, id]);
  const exportComparison = () => {
    const csv = operationsCsv([
      ["Vehículo", "Patente", "Desde UTC", "Hasta UTC", "Distancia GPS aproximada km",
        "Intervalos con desplazamiento min", "Muestras", "Paradas probables", "Estado"],
      ...items.map(({ asset, result, metrics }) => [
        asset.name, asset.plate, new Date(period.from).toISOString(), new Date(period.to).toISOString(),
        metrics.points.length > 1 ? metrics.distanceM / 1000 : "",
        metrics.points.length > 1 ? metrics.movingSeconds / 60 : "", metrics.points.length, metrics.stops.length,
        result?.error || (result?.cursor ? "Historial parcial" : metrics.points.length < 2 ? "Muestras insuficientes" : "Consultado"),
      ]),
      ["TOTAL DISPONIBLE", "", "", "", usable.length ? total.distanceKm : "",
        usable.length ? total.movingMinutes : "", total.points, total.stops, incomplete ? "Cobertura incompleta" : "Consultado"],
      [],
      ["Día en Chile", "Vehículo", "Patente", "Distancia GPS aproximada km", "Intervalos con desplazamiento min"],
      ...items.flatMap(({ asset, metrics }) => metrics.daily.map(row => [
        row.day, asset.name, asset.plate, row.km, row.movingMinutes,
      ])),
    ]);
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "tracker-comparacion-vehiculos.csv";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  return <section className="real-ops-panel fleet-comparison">
    <header><div><span className="fleet-eyebrow">Analítica de la selección</span><h2>Comparar vehículos</h2></div>
      <button disabled={loading || !total.points} onClick={exportComparison}>Exportar comparación CSV</button></header>
    <fieldset className="fleet-comparison-select">
      <legend>Vehículos a comparar</legend>
      <div className="fleet-comparison-actions">
        <button onClick={() => setSelectedIds(assets.map(asset => asset.asset_id))}>Seleccionar todos</button>
        <button onClick={() => setSelectedIds([])}>Limpiar selección</button>
        <span>{selected.length} de {assets.length} seleccionados</span>
      </div>
      <div className="fleet-comparison-options">{assets.map(asset => <label key={asset.asset_id}>
        <input type="checkbox" checked={selectedIds.includes(asset.asset_id)} onChange={() => toggle(asset.asset_id)}
          aria-label={`Comparar ${asset.plate || asset.name}`} />
        <i style={{ background: colorFor(asset.asset_id) }} />
        <span><strong>{asset.plate || asset.name}</strong><small>{asset.name}</small></span>
      </label>)}</div>
    </fieldset>
    {!selected.length ? <p role="status">Selecciona uno o más vehículos para calcular sus estadísticas.</p> : <>
      {loading && <p role="status">Calculando estadísticas de los vehículos seleccionados…</p>}
      {!loading && incomplete && <p className="fleet-notice" role="status">
        Cobertura incompleta. El total disponible suma las muestras consultadas. Revisa los vehículos sin datos, con error o con historial parcial.
      </p>}
      {items.some(item => item.result?.cursor || item.result?.error) &&
        <button disabled={loading} onClick={() => setRound(value => value + 1)}>Cargar pendientes o reintentar</button>}
      <div className="real-ops-table-scroll"><table className="fleet-comparison-table">
        <thead><tr><th>Vehículo</th><th>Distancia GPS</th><th>Desplazamiento</th><th>Muestras</th><th>Paradas probables</th><th>Estado</th></tr></thead>
        <tbody>{items.map(({ asset, result, metrics }) => <tr key={asset.asset_id}>
          <th scope="row"><i style={{ background: colorFor(asset.asset_id) }} />{asset.plate || asset.name}<small>{asset.name}</small></th>
          <td>{metrics.points.length > 1 ? format(metrics.distanceM / 1000, 3) + " km" : "—"}</td>
          <td>{metrics.points.length > 1 ? format(metrics.movingSeconds / 60) + " min" : "—"}</td>
          <td>{format(metrics.points.length, 0)}</td><td>{metrics.points.length ? metrics.stops.length : "—"}</td>
          <td>{!result || result.loading ? "Cargando…" : result.error ? <span role="alert">{result.error}</span> :
            result.cursor ? "Historial parcial" : metrics.points.length < 2 ? "Muestras insuficientes" : "Consultado"}</td>
        </tr>)}</tbody>
        <tfoot><tr><th scope="row">Total disponible · {selected.length} vehículos</th>
          <td>{!loading && usable.length ? format(total.distanceKm, 3) + " km" : "—"}</td>
          <td>{!loading && usable.length ? format(total.movingMinutes) + " min" : "—"}</td>
          <td>{loading ? "—" : format(total.points, 0)}</td><td>{!loading && total.points ? total.stops : "—"}</td>
          <td>{loading ? "Calculando…" : `${usable.length} con al menos dos muestras`}</td>
        </tr></tfoot>
      </table></div>
      <p className="fleet-note">Distancia aproximada y tiempos sumados por vehículo en el período GPS elegido.
        Los minutos de vehículos que trabajan simultáneamente se suman. Los días sin muestras quedan sin valor en el gráfico.</p>
      <h3>Distancia GPS por día y vehículo</h3>
      <p className="fleet-note">Días en hora de Chile · kilómetros aproximados</p>
      {!loading && daily.length > 0 ? <>
        <div className="fleet-comparison-chart" aria-label="Gráfico de distancia diaria por vehículo">
          <ResponsiveContainer width="100%" height={320}><LineChart data={daily} margin={{ top: 12, right: 20, bottom: 12, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="day" minTickGap={30} tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} width={55} />
            <Tooltip formatter={(value) => value == null ? "Sin muestras" : `${format(Number(value), 3)} km`} />
            {items.map(({ asset }) => <Line key={asset.asset_id} dataKey={asset.asset_id}
              name={asset.plate ? `${asset.plate} · ${asset.name}` : asset.name}
              stroke={colorFor(asset.asset_id)} strokeWidth={2.5} type="linear" connectNulls={false}
              dot={{ r: 3 }} isAnimationActive={false} />)}
          </LineChart></ResponsiveContainer>
        </div>
        <div className="fleet-comparison-legend">{items.map(({ asset }) => <span key={asset.asset_id}>
          <i style={{ background: colorFor(asset.asset_id) }} />{asset.plate || asset.name}
        </span>)}</div>
      </> : !loading && <p>Sin muestras en el período seleccionado.</p>}
    </>}
  </section>;
}
