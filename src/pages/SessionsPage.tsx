// src/pages/SessionsPage.tsx
/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useMemo, useState } from "react";
import TrackerMap from "../components/TrackerMap";
import type { TrackPoint } from "../types";
import { apiJson } from "../services/http";
import { useAuthWeb } from "../services/AuthContext";
type SessionSummary = {
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

type HistoricalPoint = {
  id: number;
  ts: string;
  lat: number;
  lon: number;
  speed_mps?: number | null;
  accuracy_m?: number | null;
  extra?: any;
};

type FieldPolygon = {
  id: number;
  name: string;
  cost_center_id: number | null;
  cost_center_name?: string | null;
  color?: string | null;
  polygon: { lat: number; lon: number }[];
};

type FieldStat = {
  fieldId: number;
  fieldName: string;
  costCenterName?: string | null;
  totalDistanceM: number;
  totalTimeMs: number;
};

type FieldTransitionRow = {
  index: number;
  fromFieldName: string;
  toFieldName: string;
  startTs: string;
  endTs: string;
  durationMs: number;
  distanceM: number;
};

type SessionStats = {
  distanceKm: number;
  distanceMeters: number;
  durationMinutes: number | null;
  durationHours: number | null;
  avgSpeedKmh: number | null;
};

type Machine = {
  id: number;
  name: string;
  plate?: string | null;
  tank_capacity_liters?: number | null;
  fuel_consumption_lph?: number | null;
  fuel_consumption_lpkm?: number | null;
};

// ---- helpers de formato ----

function formatDateTime(value: string | null | undefined) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("es-CL", {
    dateStyle: "short",
    timeStyle: "medium",
  });
}

function formatTime(value: string | null | undefined) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleTimeString("es-CL", { hour12: false });
}

function haversineMeters(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number
): number {
  const R = 6371000; // radio tierra en metros
  const toRad = (deg: number) => (deg * Math.PI) / 180;

  const φ1 = toRad(lat1);
  const φ2 = toRad(lat2);
  const Δφ = toRad(lat2 - lat1);
  const Δλ = toRad(lon2 - lon1);

  const a =
    Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
    Math.cos(φ1) * Math.cos(φ2) * Math.sin(Δλ / 2) * Math.sin(Δλ / 2);

  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

// point-in-polygon (ray casting)
function isPointInPolygon(
  point: { lat: number; lon: number },
  polygon: { lat: number; lon: number }[]
): boolean {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const xi = polygon[i].lon;
    const yi = polygon[i].lat;
    const xj = polygon[j].lon;
    const yj = polygon[j].lat;

    const intersect =
      yi > point.lat !== yj > point.lat &&
      point.lon <
        ((xj - xi) * (point.lat - yi)) / (yj - yi + 1e-12) + xi;

    if (intersect) inside = !inside;
  }
  return inside;
}

function findFieldForPoint(
  pt: { lat: number; lon: number },
  fields: FieldPolygon[]
): FieldPolygon | null {
  for (const f of fields) {
    if (f.polygon.length < 3) continue;
    if (isPointInPolygon(pt, f.polygon)) return f;
  }
  return null;
}

// ms → string tipo "12:34 min" o "1h 02m"
function formatDurationMs(ms: number): string {
  if (!ms || ms <= 0) return "0:00";
  const totalSec = Math.floor(ms / 1000);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  if (h > 0) {
    return `${h}h ${m.toString().padStart(2, "0")}m`;
  }
  return `${m}:${s.toString().padStart(2, "0")} min`;
}

// velocidad dinámica m/s o km/h desde m/s
function formatSpeedDynamicFromMps(
  speedMps: number | null | undefined
): string {
  if (speedMps == null || Number.isNaN(speedMps)) return "—";
  const kmh = speedMps * 3.6;
  if (kmh < 5) {
    return `${speedMps.toFixed(2)} m/s`;
  }
  return `${kmh.toFixed(1)} km/h`;
}

// resumen por campo/cuartel para una sesión
function computeFieldStatsForSession(
  points: HistoricalPoint[],
  fields: FieldPolygon[]
): FieldStat[] {
  if (points.length < 2 || fields.length === 0) return [];

  const sorted = [...points].sort(
    (a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime()
  );

  const statsMap = new Map<number, FieldStat>();

  for (let i = 1; i < sorted.length; i++) {
    const prev = sorted[i - 1];
    const curr = sorted[i];

    const t1 = new Date(prev.ts).getTime();
    const t2 = new Date(curr.ts).getTime();
    const dtMs = t2 - t1;
    if (dtMs <= 0) continue;

    const dM = haversineMeters(prev.lat, prev.lon, curr.lat, curr.lon);

    // punto medio del segmento
    const midPoint = {
      lat: (prev.lat + curr.lat) / 2,
      lon: (prev.lon + curr.lon) / 2,
    };

    const field = findFieldForPoint(midPoint, fields);
    if (!field) continue;

    const existing = statsMap.get(field.id) ?? {
      fieldId: field.id,
      fieldName: field.name,
      costCenterName: field.cost_center_name ?? null,
      totalDistanceM: 0,
      totalTimeMs: 0,
    };
    existing.totalDistanceM += dM;
    existing.totalTimeMs += dtMs;
    statsMap.set(field.id, existing);
  }

  return Array.from(statsMap.values()).sort(
    (a, b) => b.totalTimeMs - a.totalTimeMs
  );
}

// transiciones entre campos (cuando pasa de un polígono a otro)
function computeFieldTransitionsForSession(
  points: HistoricalPoint[],
  fields: FieldPolygon[]
): FieldTransitionRow[] {
  if (points.length < 2 || fields.length === 0) return [];

  const sorted = [...points].sort(
    (a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime()
  );

  const rows: FieldTransitionRow[] = [];
  let prevField: FieldPolygon | null = null;

  for (let i = 1; i < sorted.length; i++) {
    const p1 = sorted[i - 1];
    const p2 = sorted[i];

    const midPoint = {
      lat: (p1.lat + p2.lat) / 2,
      lon: (p1.lon + p2.lon) / 2,
    };
    const currField = findFieldForPoint(midPoint, fields);

    if (prevField === null) {
      prevField = currField;
      continue;
    }

    const prevId = prevField ? prevField.id : null;
    const currId = currField ? currField.id : null;

    if (prevId !== currId) {
      const startTs = p1.ts;
      const endTs = p2.ts;
      const dtMs = Math.max(
        0,
        new Date(endTs).getTime() - new Date(startTs).getTime()
      );
      const distM = haversineMeters(p1.lat, p1.lon, p2.lat, p2.lon);

      rows.push({
        index: rows.length + 1,
        fromFieldName: prevField ? prevField.name : "Fuera de campos",
        toFieldName: currField ? currField.name : "Fuera de campos",
        startTs,
        endTs,
        durationMs: dtMs,
        distanceM: distM,
      });
    }

    prevField = currField;
  }

  return rows;
}

function formatDurationHHMM(minutes: number): string {
  if (minutes == null || Number.isNaN(minutes)) return "—";

  const totalMin = Math.floor(minutes);
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;

  return `${h.toString().padStart(2,"0")}:${m.toString().padStart(2,"0")}`;
}


function computeStats(points: HistoricalPoint[]): SessionStats {
  if (points.length < 2) {
    return {
      distanceKm: 0,
      distanceMeters: 0,
      durationMinutes: null,
      durationHours: null,
      avgSpeedKmh: null,
    };
  }

  const sorted = [...points].sort(
    (a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime()
  );

  let distanceMeters = 0;
  for (let i = 1; i < sorted.length; i++) {
    const p1 = sorted[i - 1];
    const p2 = sorted[i];
    distanceMeters += haversineMeters(p1.lat, p1.lon, p2.lat, p2.lon);
  }

  const start = new Date(sorted[0].ts).getTime();
  const end = new Date(sorted[sorted.length - 1].ts).getTime();
  const durationMinutes = (end - start) / 1000 / 60;
  const durationHours = durationMinutes > 0 ? durationMinutes / 60 : null;

  const distanceKm = distanceMeters / 1000;
  const avgSpeedKmh =
    durationMinutes > 0 ? distanceKm / (durationMinutes / 60) : null;

  return {
    distanceKm,
    distanceMeters,
    durationMinutes,
    durationHours,
    avgSpeedKmh,
  };
}


const SessionsPage = () => {
  const { token, logout } = useAuthWeb();
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [machines, setMachines] = useState<Machine[]>([]);
  const [fields, setFields] = useState<FieldPolygon[]>([]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedSession, setSelectedSession] =
    useState<SessionSummary | null>(null);
  const [points, setPoints] = useState<HistoricalPoint[]>([]);
  const [pointsLoading, setPointsLoading] = useState(false);
  const [pointsError, setPointsError] = useState<string | null>(null);
  const [stats, setStats] = useState<SessionStats | null>(null);


  const [fieldStats, setFieldStats] = useState<FieldStat[]>([]);
  const [fieldTransitions, setFieldTransitions] = useState<
    FieldTransitionRow[]
  >([]);

  
  // carga inicial: sesiones + campos + máquinas
useEffect(() => {
  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);

      const [sessionsData, fieldsData, machinesData] = await Promise.all([
        // ✅ recomendado (requiere auth)
        apiJson<SessionSummary[]>("/sessions_recent?limit=50"),

        // (aunque sean públicos, no pasa nada con enviar Bearer)
        apiJson<FieldPolygon[]>("/fields"),
        apiJson<Machine[]>("/machines"),
      ]);

      setSessions(sessionsData);
      setFields(fieldsData);
      setMachines(machinesData);

    } catch (e: any) {
      console.error(e);

      // ✅ si tu apiJson lanza Error con “401”
     const msg = String(e?.message || "");

    if (msg.includes("401")) {
      logout();
      return;
    }

    if (msg.includes("403")) {
      setError("No tienes permisos para ver sesiones globales (admin).");
      return;
    }

      setError(e?.message || "No se pudieron cargar las sesiones.");
    } finally {
      setLoading(false);
    }
  };

  fetchData();
}, [token, logout]);

const handleSelectSession = async (session: SessionSummary) => {
  setSelectedSession(session);
  setPoints([]);
  setStats(null);
  setFieldStats([]);
  setFieldTransitions([]);
  setPointsError(null);
  setPointsLoading(true);

  try {
    const data = await apiJson<HistoricalPoint[]>(`/sessions/${session.id}/points`);
    setPoints(data);
    setStats(computeStats(data));
  } catch (e: any) {
    console.error(e);

    if (String(e?.message || "").includes("401")) {
      logout();
      return;
    }

    setPointsError(e?.message || "No se pudieron cargar los puntos de la sesión.");
  } finally {
    setPointsLoading(false);
  }
};


  // recalcular resumen por campo y transiciones cuando cambian puntos o campos
  useEffect(() => {
    if (points.length === 0 || fields.length === 0) {
      setFieldStats([]);
      setFieldTransitions([]);
      return;
    }
    setFieldStats(computeFieldStatsForSession(points, fields));
    setFieldTransitions(computeFieldTransitionsForSession(points, fields));
  }, [points, fields]);

  // Adaptamos HistoricalPoint -> TrackPoint para reutilizar TrackerMap
  const mapPoints: TrackPoint[] = points.map((p) => ({
    id: p.id,
    timestamp: new Date(p.ts).getTime(),
    lat: p.lat,
    lon: p.lon,
    accuracy: p.accuracy_m ?? undefined,
    speed: p.speed_mps ?? undefined,
  }));

  // puntos + delta de tiempo y campo asociado (para ver mejor movimiento)
  const pointsWithDelta = useMemo(() => {
    const sorted = [...points].sort(
      (a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime()
    );
    let prevTs: number | null = null;
    let lastFieldId: number | null = null;

    return sorted.map((p) => {
      const tsNum = new Date(p.ts).getTime();
      let deltaSec: number | null = null;
      if (prevTs != null) {
        deltaSec = (tsNum - prevTs) / 1000;
      }
      prevTs = tsNum;

      const field = findFieldForPoint(
        { lat: p.lat, lon: p.lon },
        fields
      );

      const currentFieldId = field?.id ?? null;
      const fieldChanged =
        lastFieldId !== null && currentFieldId !== lastFieldId;
      lastFieldId = currentFieldId;

      return {
        ...p,
        deltaSec,
        fieldName: field?.name ?? null,
        fieldCostCenterName: field?.cost_center_name ?? null,
        fieldChanged,
      };
    });
  }, [points, fields]);

  // máquina asociada a la sesión
  const selectedMachine: Machine | null = useMemo(() => {
    if (!selectedSession) return null;
    return machines.find((m) => m.id === selectedSession.machine_id) ?? null;
  }, [selectedSession, machines]);

  // comparación consumo teórico (maestro) vs recorrido real
  const fuelComparison = useMemo(() => {
    if (!stats || !selectedMachine) return null;

    const tankCapacity =
      selectedMachine.tank_capacity_liters ?? null;
    const consLpkm = selectedMachine.fuel_consumption_lpkm ?? null;
    const consLph = selectedMachine.fuel_consumption_lph ?? null;

    const distanceKm = stats.distanceKm;
    const durationHours = stats.durationHours ?? null;

    let expectedByKm: number | null = null;
    let expectedByHour: number | null = null;
    let maxLitrosUsados: number | null = null;

      if (consLpkm != null && distanceKm != null) {
        expectedByKm = distanceKm * consLpkm;
      }

      if (consLph != null && durationHours != null) {
        expectedByHour = durationHours * consLph;
      }

      maxLitrosUsados = Math.max(expectedByKm ?? 0, expectedByHour ?? 0);


    return {
      tankCapacity,
      expectedByKm,
      expectedByHour,
      maxLitrosUsados
    };
  }, [stats, selectedMachine]);

  return (
    <div className="sessions-layout">
      {/* Panel izquierdo: lista de sesiones */}
      <section className="card">
        <div className="card-header">
          <div>
            <div className="card-title">Sesiones de rastreo</div>
            <div className="card-subtitle">
              Últimas sesiones registradas en la base de datos (máquinas, chofer, puntos).
            </div>
          </div>
        </div>

        {error && <div className="tracker-error">⚠️ {error}</div>}

        {loading ? (
          <div className="sessions-loading">Cargando sesiones…</div>
        ) : (
          <div className="sessions-table-wrapper">
            {sessions.length === 0 ? (
              <div className="sessions-empty">
                No hay sesiones registradas aún. Realiza un recorrido para ver datos aquí.
              </div>
            ) : (
              <table className="sessions-table">
                <thead>
                  <tr>
                    <th>Estado</th>
                    <th>Máquina</th>
                    <th>Chofer</th>
                    <th>Centro costo</th>
                    <th>Inicio</th>
                    <th>Término</th>
                    <th>Puntos</th>
                  </tr>
                </thead>
                <tbody>
                  {sessions.map((s) => (
                    <tr
                      key={s.id}
                      className={
                        "sessions-row " +
                        (selectedSession?.id === s.id
                          ? "sessions-row--active"
                          : "")
                      }
                      onClick={() => handleSelectSession(s)}
                    >
                      <td>
                        <span
                          className={
                            "status-pill " +
                            (s.status === "open"
                              ? "status-pill--open"
                              : "status-pill--closed")
                          }
                        >
                          {s.status === "open" ? "Abierta" : "Cerrada"}
                        </span>
                      </td>
                      <td>
                        <div className="sessions-machine">
                          <span className="sessions-machine__name">
                            {s.machine_name || `Máquina ${s.machine_id}`}
                          </span>
                          <span className="sessions-machine__id">
                            ID #{s.machine_id}
                          </span>
                        </div>
                      </td>
                      <td>{s.driver_name || "—"}</td>
                      <td>{s.cost_center_name || "—"}</td>
                      <td>{formatDateTime(s.started_at)}</td>
                      <td>{formatDateTime(s.ended_at || null)}</td>
                      <td style={{ textAlign: "right" }}>
                        {s.points_count}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </section>

      {/* Panel derecho: detalle de una sesión + mapa */}
      <section className="card">
        <div className="card-header">
          <div>
            <div className="card-title">Detalle de sesión</div>
            <div className="card-subtitle">
              Recorrido, tiempos, distancia, consumo estimado y movimiento entre campos del trayecto seleccionado.
            </div>
          </div>
        </div>

        {!selectedSession ? (
          <div className="sessions-empty">
            Selecciona una sesión en la tabla para ver el recorrido en el mapa y sus detalles.
          </div>
        ) : (
          <>
            <div className="session-detail-header">
              <div className="session-detail-main">
                <div className="session-detail-title">
                  {selectedSession.machine_name ||
                    `Máquina ${selectedSession.machine_id}`}
                </div>
                <div className="session-detail-subtitle">
                  Inicio: {formatDateTime(selectedSession.started_at)} · Término:{" "}
                  {formatDateTime(selectedSession.ended_at || null)}
                </div>
                <div className="session-detail-meta">
                  <span>
                    Chofer: {selectedSession.driver_name || "—"}
                  </span>
                  <span>
                    Centro costo: {selectedSession.cost_center_name || "—"}
                  </span>
                </div>
                {selectedMachine && (
                  <div className="session-detail-meta">
                    <span>
                      Estanque:{" "}
                      {selectedMachine.tank_capacity_liters != null
                        ? `${selectedMachine.tank_capacity_liters.toFixed(1)} L`
                        : "—"}
                    </span>
                    <span>
                      Consumo ref.:{" "}
                      {selectedMachine.fuel_consumption_lph != null
                        ? `${selectedMachine.fuel_consumption_lph.toFixed(2)} L/h`
                        : "—"}
                      {" · "}
                      {selectedMachine.fuel_consumption_lpkm != null
                        ? `${selectedMachine.fuel_consumption_lpkm.toFixed(
                            3
                          )} L/km`
                        : "—"}
                    </span>
                  </div>
                )}
              </div>
            </div>

            {pointsError && (
              <div className="tracker-error">⚠️ {pointsError}</div>
            )}

            {pointsLoading ? (
              <div className="sessions-loading">Cargando recorrido…</div>
            ) : points.length === 0 ? (
              <div className="sessions-empty">
                Esta sesión no tiene puntos registrados aún.
              </div>
            ) : (
              <>
                {/* Mapa con el trazo histórico */}
                <div style={{ marginBottom: 12 }}>
                  <TrackerMap points={mapPoints} fields={fields} />
                </div>

                {/* Stats principales de la sesión */}
                {stats && (
                  <>
                    <div className="session-stats">
                      <div className="session-stat">
                        <div className="session-stat__label">
                          Distancia total
                        </div>
                        <div className="session-stat__value">
                          {stats.distanceKm.toFixed(2)} km
                        </div>
                      </div>
                      <div className="session-stat">
                      <div className="session-stat__label">Duración</div>
                    <div className="session-stat__value">
                        {stats.durationMinutes != null
                          ? formatDurationHHMM(stats.durationMinutes)
                          : "—"}
                      </div>


                      </div>
                      <div className="session-stat">
                        <div className="session-stat__label">
                          Velocidad media
                        </div>
                        <div className="session-stat__value">
                          {stats.avgSpeedKmh != null
                            ? `${stats.avgSpeedKmh.toFixed(1)} km/h`
                            : "—"}
                        </div>
                      </div>
                      <div className="session-stat">
                        <div className="session-stat__label">Puntos</div>
                        <div className="session-stat__value">
                          {points.length}
                        </div>
                      </div>
                    </div>

                    {/* Comparación con maestro de máquina (consumos) */}
                    {selectedMachine && fuelComparison && (
                      <div
                        className="session-stats"
                        style={{ marginTop: 8 }}
                      >
                               <div className="session-stat">
                          <div className="session-stat__label">
                            Consumo estimado (por km)
                          </div>
                          <div className="session-stat__value">
                            {fuelComparison.expectedByKm != null
                              ? `${fuelComparison.expectedByKm.toFixed(3)} L`
                              : "—"}
                          </div>

                        </div>

                            <div className="session-stat">
                          <div className="session-stat__label">
                            Consumo estimado (por hrs)
                          </div>
                          <div className="session-stat__value">
                            {fuelComparison.expectedByHour != null
                              ? `${fuelComparison.expectedByHour.toFixed(
                                  3
                                )} L`
                              : "—"}
                          </div>
                        </div>
                        <div className="session-stat">
                          <div className="session-stat__label">
                            Estanque (L)
                          </div>
                          <div className="session-stat__value">
                            {fuelComparison.tankCapacity != null
                              ? fuelComparison.tankCapacity.toFixed(1)
                              : "—"}
                          </div>
                        </div>
                 
                    
                        <div className="session-stat">
                          <div className="session-stat__label">
                            Uso estanque (máx.)
                          </div>
                            <div className="session-stat__value">
    {fuelComparison.maxLitrosUsados != null
      ? `${fuelComparison.maxLitrosUsados.toFixed(3)} L`
      : "—"}
  </div>

                        </div>
                      </div>
                    )}
                  </>
                )}

                {/* Resumen por campo / cuartel */}
                {fieldStats.length > 0 && (
                  <div
                    className="session-points-list"
                    style={{ marginTop: 10 }}
                  >
                    <div className="session-points-list__title">
                      Resumen por campo / cuartel
                    </div>
                    <div className="session-points-list__table-wrapper">
                      <table className="session-points-table">
                        <thead>
                          <tr>
                            <th>Campo / cuartel</th>
                            <th>Centro de costo</th>
                            <th>Tiempo</th>
                            <th>Distancia</th>
                          </tr>
                        </thead>
                        <tbody>
                          {fieldStats.map((fs) => (
                            <tr key={fs.fieldId}>
                              <td>{fs.fieldName}</td>
                              <td>{fs.costCenterName ?? "—"}</td>
                              <td>{formatDurationMs(fs.totalTimeMs)}</td>
                              <td>
                                {(fs.totalDistanceM / 1000).toFixed(2)} km
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Transiciones entre campos */}
                {fieldTransitions.length > 0 && (
                  <div
                    className="session-points-list"
                    style={{ marginTop: 10 }}
                  >
                    <div className="session-points-list__title">
                      Transiciones entre campos / cuarteles
                    </div>
                    <div className="session-points-list__table-wrapper">
                      <table className="session-points-table">
                        <thead>
                          <tr>
                            <th>#</th>
                            <th>Desde</th>
                            <th>Hacia</th>
                            <th>Hora inicio</th>
                            <th>Hora fin</th>
                            <th>Tiempo</th>
                            <th>Distancia</th>
                          </tr>
                        </thead>
                        <tbody>
                          {fieldTransitions.map((t) => (
                            <tr key={t.index}>
                              <td>{t.index}</td>
                              <td>{t.fromFieldName}</td>
                              <td>{t.toFieldName}</td>
                              <td>{formatTime(t.startTs)}</td>
                              <td>{formatTime(t.endTs)}</td>
                              <td>{formatDurationMs(t.durationMs)}</td>
                              <td>
                                {(t.distanceM / 1000).toFixed(3)} km
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Lista de puntos con tiempo entre puntos y campo */}
                <div className="session-points-list">
                  <div className="session-points-list__title">
                    Puntos del recorrido
                  </div>
                  <div className="session-points-list__table-wrapper">
                    <table className="session-points-table">
                      <thead>
                        <tr>
                          <th>#</th>
                          <th>Hora</th>
                          <th>Lat</th>
                          <th>Lon</th>
                          <th>Campo / cuartel</th>
                          <th>Δt (s)</th>
                          <th>Vel (GPS)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {pointsWithDelta.map((p, idx) => (
                          <tr
                            key={p.id}
                            className={
                              p.fieldChanged
                                ? "session-points-row session-points-row--field-change"
                                : "session-points-row"
                            }
                          >
                            <td>{idx + 1}</td>
                            <td>{formatTime(p.ts)}</td>
                            <td>{p.lat.toFixed(5)}</td>
                            <td>{p.lon.toFixed(5)}</td>
                            <td>{p.fieldName || "—"}</td>
                            <td style={{ textAlign: "right" }}>
                              {p.deltaSec != null
                                ? p.deltaSec.toFixed(1)
                                : "—"}
                            </td>
                            <td style={{ textAlign: "right" }}>
                              {formatSpeedDynamicFromMps(p.speed_mps ?? null)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            )}
          </>
        )}
      </section>
    </div>
  );
};

export default SessionsPage;
