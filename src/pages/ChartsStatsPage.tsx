// src/pages/ChartsStatsPage.tsx
/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useMemo, useState } from "react";
import { apiJson } from "../services/http";
import { useAuthWeb } from "../services/AuthContext";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import "./ChartsStatsPage.scss";

// ====== Tipos ======
type SessionSummary = {
  id: string;
  machine_id: number;
  machine_name?: string | null;
  driver_name?: string | null;
  cost_center_name?: string | null;
  started_at: string;
  ended_at?: string | null;
  work_order_id?: number | null;
  labor_id?: number | null;
  effort_factor?: number | null;
  target_speed_kmh?: number | null;
  status: "open" | "closed";
  points_count: number;
};

type Machine = {
  id: number;
  name: string;
  plate?: string | null;
  tank_capacity_liters?: number | null;
  fuel_consumption_lph?: number | null;
  fuel_consumption_lpkm?: number | null;
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

type SessionStats = {
  distanceKm: number;
  distanceMeters: number;
  durationMinutes: number | null;
  durationHours: number | null;
  avgSpeedKmh: number | null;
};

type SessionRow = {
  session: SessionSummary;
  machine: Machine | null;
  stats: SessionStats | null;
  gpsPoints: number | null;
  flags: string[];
};

// ====== Utils formato ======
function formatDateOnly(value: string | null | undefined) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("es-CL", { dateStyle: "short" });
}

function fmtNum(n: number | null | undefined, digits = 2): string {
  if (n == null || !Number.isFinite(n)) return "—";
  return n.toFixed(digits);
}

function normText(s: string | null | undefined) {
  return (s ?? "").trim().replace(/\s+/g, " ").toLowerCase();
}

async function tryFetchJSON(paths: string[]): Promise<any | null> {
  for (const p of paths) {
    try {
      return await apiJson<any>(p);
    } catch {
      // continúa
    }
  }
  return null;
}

function parseDateOnlyLocalMs(dateStr: string, endOfDay: boolean): number | null {
  if (!dateStr) return null;
  const d = new Date(`${dateStr}T${endOfDay ? "23:59:59.999" : "00:00:00.000"}`);
  const ms = d.getTime();
  return Number.isNaN(ms) ? null : ms;
}

// ====== Geo ======
function toRad(deg: number): number {
  return (deg * Math.PI) / 180;
}
function haversineMeters(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371000;
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
function clamp(n: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, n));
}

function computeSessionStats(
  points: HistoricalPoint[],
  session: SessionSummary,
  rangeMs: { lo: number; hi: number }
): SessionStats {
  const inRange = points.filter((p) => {
    const t = new Date(p.ts).getTime();
    return !Number.isNaN(t) && t >= rangeMs.lo && t <= rangeMs.hi;
  });

  const sorted = [...inRange].sort(
    (a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime()
  );

  let distanceMeters = 0;
  if (sorted.length >= 2) {
    for (let i = 1; i < sorted.length; i++) {
      const p1 = sorted[i - 1];
      const p2 = sorted[i];
      distanceMeters += haversineMeters(p1.lat, p1.lon, p2.lat, p2.lon);
    }
  }

  const startRaw = new Date(session.started_at).getTime();
  if (Number.isNaN(startRaw)) {
    return {
      distanceKm: distanceMeters / 1000,
      distanceMeters,
      durationMinutes: null,
      durationHours: null,
      avgSpeedKmh: null,
    };
  }

  const endRaw =
    session.ended_at && !Number.isNaN(new Date(session.ended_at).getTime())
      ? new Date(session.ended_at).getTime()
      : rangeMs.hi !== Infinity
        ? rangeMs.hi
        : Date.now();

  const startMs = clamp(startRaw, rangeMs.lo, rangeMs.hi);
  const endMs = clamp(endRaw, rangeMs.lo, rangeMs.hi);

  const durationMinutes = endMs >= startMs ? (endMs - startMs) / 1000 / 60 : null;
  const durationHours = durationMinutes != null ? durationMinutes / 60 : null;

  const distanceKm = distanceMeters / 1000;
  const avgSpeedKmh = durationHours && durationHours > 0 ? distanceKm / durationHours : null;

  return { distanceKm, distanceMeters, durationMinutes, durationHours, avgSpeedKmh };
}


// ====== Export helpers ======
function downloadBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function toCSV(rows: Record<string, any>[]) {
  const headers = Array.from(
    new Set(rows.flatMap((r) => Object.keys(r)))
  );

  const esc = (v: any) => {
    if (v == null) return "";
    const s = String(v);
    if (/[",\n;]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
    return s;
  };

  const lines = [
    headers.join(";"),
    ...rows.map((r) => headers.map((h) => esc(r[h])).join(";")),
  ];

  return lines.join("\n");
}

async function exportToXlsx(filename: string, sheetName: string, rows: Record<string, any>[]) {
  // Lazy import para no inflar bundle si no se usa
  const XLSX = await import("xlsx");
  const ws = XLSX.utils.json_to_sheet(rows);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, sheetName);
  XLSX.writeFile(wb, filename);
}

// ====== Dashboards ======
type DashboardKey =
  | "MACHINES_DISTANCE"
  | "MACHINES_HOURS"
  | "DAILY_SESSIONS"
  | "ALERTS_BY_TYPE"
  | "SPEED_DISTRIBUTION";

const DASHBOARDS: { key: DashboardKey; label: string; desc: string }[] = [
  {
    key: "MACHINES_DISTANCE",
    label: "Distancia por máquina",
    desc: "Top máquinas por distancia total (km).",
  },
  {
    key: "MACHINES_HOURS",
    label: "Horas por máquina",
    desc: "Top máquinas por horas totales.",
  },
  {
    key: "DAILY_SESSIONS",
    label: "Sesiones por día",
    desc: "Cantidad de sesiones (filtradas) por fecha.",
  },
  {
    key: "ALERTS_BY_TYPE",
    label: "Alertas por tipo",
    desc: "Distribución de alertas detectadas en el set filtrado.",
  },
  {
    key: "SPEED_DISTRIBUTION",
    label: "Distribución velocidad",
    desc: "Buckets de velocidad media (km/h) por sesión.",
  },
];

// ======================================
const ChartsStatsPage = () => {
  const { token, logout } = useAuthWeb();

  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [machines, setMachines] = useState<Machine[]>([]);
  const [costCenters, setCostCenters] = useState<string[]>([]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedMachineId, setSelectedMachineId] = useState<string>("");
  const [selectedCostCenter, setSelectedCostCenter] = useState<string>("");
  const [dateFrom, setDateFrom] = useState<string>("");
  const [dateTo, setDateTo] = useState<string>("");

  const [statsLoading, setStatsLoading] = useState(false);

  const [sessionStatsById, setSessionStatsById] = useState<Record<string, SessionStats>>({});
  const [sessionGpsPointsById, setSessionGpsPointsById] = useState<Record<string, number>>({});

  const [activeDashboard, setActiveDashboard] = useState<DashboardKey>("MACHINES_DISTANCE");

  // carga inicial
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);

        const [sessionsData, machinesData] = await Promise.all([
          apiJson<SessionSummary[]>("/sessions_recent?limit=300"),
          apiJson<Machine[]>("/machines"),
        ]);

        setSessions(sessionsData);
        setMachines(machinesData);

        const cc = await tryFetchJSON([
          "/cost_centers",
          "/cost-centers",
          "/costCenters",
        ]);

        if (Array.isArray(cc) && cc.length > 0) {
          const names = cc
            .map((c: any) => (typeof c === "string" ? c : c?.name))
            .filter((n: any) => !!n) as string[];
          setCostCenters([...new Set(names)].sort());
        } else {
          const names = Array.from(
            new Set(
              sessionsData
                .map((s) => (s.cost_center_name || "").trim())
                .filter((n) => n.length > 0)
            )
          ).sort();
          setCostCenters(names);
        }
      } catch (e: any) {
        console.error(e);
        if (String(e?.message || "").includes("401")) {
          logout();
          return;
        }
        setError(e?.message || "No se pudieron cargar los datos.");
      } finally {
        setLoading(false);
      }
    };

    void fetchData();
  }, [token, logout]);

  // Filtrado por máquina + centro de costo + rango de fechas
  const filteredSessions = useMemo(() => {
    let base = sessions;

    if (selectedMachineId) {
      const mid = Number(selectedMachineId);
      base = base.filter((s) => s.machine_id === mid);
    }

    if (selectedCostCenter) {
      const q = normText(selectedCostCenter);
      base = base.filter((s) => normText(s.cost_center_name) === q);
    }

    const fromMs = dateFrom ? parseDateOnlyLocalMs(dateFrom, false) : null;
    const toMs = dateTo ? parseDateOnlyLocalMs(dateTo, true) : null;

    if (fromMs != null || toMs != null) {
      const lo = fromMs ?? -Infinity;
      const hi = toMs ?? Infinity;

      base = base.filter((s) => {
        const startMs = new Date(s.started_at).getTime();
        if (Number.isNaN(startMs)) return false;

        const rawEndMs = s.ended_at ? new Date(s.ended_at).getTime() : null;
        const endMs =
          rawEndMs != null && !Number.isNaN(rawEndMs)
            ? rawEndMs
            : hi !== Infinity
              ? hi
              : Date.now();

        return startMs <= hi && endMs >= lo;
      });
    }

    return [...base].sort(
      (a, b) => new Date(a.started_at).getTime() - new Date(b.started_at).getTime()
    );
  }, [sessions, selectedMachineId, selectedCostCenter, dateFrom, dateTo]);

  // Cálculo stats por sesión (para el set filtrado)
  useEffect(() => {
    let cancelled = false;

    const compute = async () => {
      if (filteredSessions.length === 0) {
        setSessionStatsById({});
        setSessionGpsPointsById({});
        setStatsLoading(false);
        return;
      }

      setStatsLoading(true);

      const lo = dateFrom ? (parseDateOnlyLocalMs(dateFrom, false) ?? -Infinity) : -Infinity;
      const hi = dateTo ? (parseDateOnlyLocalMs(dateTo, true) ?? Infinity) : Infinity;
      const rangeMs = { lo, hi };

      try {
        const pointsBySessionId: Record<string, HistoricalPoint[]> = {};
        const gpsCountById: Record<string, number> = {};
        const statsById: Record<string, SessionStats> = {};

        await Promise.all(
          filteredSessions.map(async (s) => {
            try {
              const data = await apiJson<HistoricalPoint[]>(`/sessions/${s.id}/points`);
              pointsBySessionId[s.id] = data;
              gpsCountById[s.id] = data.length;
            } catch (err: any) {
              if (String(err?.message || "").includes("401")) logout();
              pointsBySessionId[s.id] = [];
              gpsCountById[s.id] = 0;
            }
          })
        );

        for (const s of filteredSessions) {
          const pts = pointsBySessionId[s.id] ?? [];
          statsById[s.id] = computeSessionStats(pts, s, rangeMs);
        }

        if (!cancelled) {
          setSessionStatsById(statsById);
          setSessionGpsPointsById(gpsCountById);
        }
      } finally {
        if (!cancelled) setStatsLoading(false);
      }
    };

    void compute();
    return () => {
      cancelled = true;
    };
  }, [filteredSessions, dateFrom, dateTo, logout]);

  // Session rows + flags (simplificado, pero útil para dashboard de alertas)
  const sessionRows: SessionRow[] = useMemo(() => {
    // reglas simples de alertas (puedes expandir con tu lógica p95 si quieres)
    return filteredSessions.map((s) => {
      const machine = machines.find((m) => m.id === s.machine_id) ?? null;
      const stats = sessionStatsById[s.id] ?? null;
      const gpsPoints = typeof sessionGpsPointsById[s.id] === "number" ? sessionGpsPointsById[s.id] : null;

      const flags: string[] = [];
      if (!stats) flags.push("Sin stats");
      if (s.status === "open") flags.push("Sesión abierta");
      if (gpsPoints != null && gpsPoints < 10) flags.push("Datos GPS insuficientes");
      if (stats?.durationHours != null && stats.durationHours > 0.25 && stats.distanceKm < 0.1) {
        flags.push("Duración alta con distancia casi cero");
      }
      if (stats?.avgSpeedKmh != null && stats.avgSpeedKmh > 80) flags.push("Velocidad media fuera de rango");

      return { session: s, machine, stats, gpsPoints, flags };
    });
  }, [filteredSessions, machines, sessionStatsById, sessionGpsPointsById]);

  // =========================
  // Construcción de datasets por dashboard
  // =========================
  const dataset = useMemo(() => {
    const valid = sessionRows.filter((r) => r.stats != null) as Array<
      SessionRow & { stats: SessionStats }
    >;

    if (activeDashboard === "MACHINES_DISTANCE") {
      const byMachine = new Map<number, { machineId: number; machine: string; plate: string; km: number; sessions: number }>();
      for (const r of valid) {
        const mId = r.session.machine_id;
        const name = r.machine?.name || r.session.machine_name || `#${mId}`;
        const plate = r.machine?.plate || "";
        const cur = byMachine.get(mId) || { machineId: mId, machine: name, plate, km: 0, sessions: 0 };
        cur.km += r.stats.distanceKm;
        cur.sessions += 1;
        byMachine.set(mId, cur);
      }
      return Array.from(byMachine.values()).sort((a, b) => b.km - a.km).slice(0, 12);
    }

    if (activeDashboard === "MACHINES_HOURS") {
      const byMachine = new Map<number, { machineId: number; machine: string; plate: string; hours: number; sessions: number }>();
      for (const r of valid) {
        const mId = r.session.machine_id;
        const name = r.machine?.name || r.session.machine_name || `#${mId}`;
        const plate = r.machine?.plate || "";
        const cur = byMachine.get(mId) || { machineId: mId, machine: name, plate, hours: 0, sessions: 0 };
        cur.hours += r.stats.durationHours ?? 0;
        cur.sessions += 1;
        byMachine.set(mId, cur);
      }
      return Array.from(byMachine.values()).sort((a, b) => b.hours - a.hours).slice(0, 12);
    }

    if (activeDashboard === "DAILY_SESSIONS") {
      const byDay = new Map<string, { day: string; sessions: number; km: number; hours: number }>();
      for (const r of valid) {
        const day = formatDateOnly(r.session.started_at);
        const cur = byDay.get(day) || { day, sessions: 0, km: 0, hours: 0 };
        cur.sessions += 1;
        cur.km += r.stats.distanceKm;
        cur.hours += r.stats.durationHours ?? 0;
        byDay.set(day, cur);
      }
      // orden cronológico real (no alfabético por formato)
      const parse = (d: string) => {
        // intenta parse es-CL (dd-mm-aaaa) vs (dd/mm/aaaa) según locale
        const norm = d.replace(/\./g, "").replace(/-/g, "/");
        const parts = norm.split("/");
        if (parts.length === 3) {
          const [dd, mm, yy] = parts.map((x) => parseInt(x, 10));
          if (Number.isFinite(dd) && Number.isFinite(mm) && Number.isFinite(yy)) {
            return new Date(yy, mm - 1, dd).getTime();
          }
        }
        return Number.POSITIVE_INFINITY;
      };
      return Array.from(byDay.values()).sort((a, b) => parse(a.day) - parse(b.day));
    }

    if (activeDashboard === "ALERTS_BY_TYPE") {
      const m = new Map<string, number>();
      for (const r of sessionRows) {
        for (const f of r.flags) m.set(f, (m.get(f) ?? 0) + 1);
      }
      return Array.from(m.entries())
        .map(([type, count]) => ({ type, count }))
        .sort((a, b) => b.count - a.count);
    }

    // SPEED_DISTRIBUTION
    const buckets = [
      { label: "0–5", lo: 0, hi: 5 },
      { label: "5–10", lo: 5, hi: 10 },
      { label: "10–20", lo: 10, hi: 20 },
      { label: "20–40", lo: 20, hi: 40 },
      { label: "40–80", lo: 40, hi: 80 },
      { label: "80+", lo: 80, hi: Infinity },
    ];
    const counts = buckets.map((b) => ({ bucket: b.label, sessions: 0 }));
    for (const r of valid) {
      const v = r.stats.avgSpeedKmh ?? 0;
      const idx = buckets.findIndex((b) => v >= b.lo && v < b.hi);
      if (idx >= 0) counts[idx].sessions += 1;
    }
    return counts;
  }, [activeDashboard, sessionRows]);

  // Dataset exportable (el que alimenta el gráfico actual)
  const exportRows = useMemo(() => {
    // además de dataset, agregamos contexto de filtros aplicados
    const filters = {
      filtro_maquina: selectedMachineId ? Number(selectedMachineId) : "Todas",
      filtro_centro_costo: selectedCostCenter || "Todos",
      filtro_desde: dateFrom || "—",
      filtro_hasta: dateTo || "—",
      sesiones_filtradas: filteredSessions.length,
    };

    // “flatten” de dataset
    const rows = (dataset as any[]).map((r) => ({ ...filters, ...r }));
    return rows;
  }, [dataset, selectedMachineId, selectedCostCenter, dateFrom, dateTo, filteredSessions.length]);

  const exportNameBase = useMemo(() => {
    const key = activeDashboard.toLowerCase();
    const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
    return `dashboard_${key}_${stamp}`;
  }, [activeDashboard]);

  const onExportCsv = () => {
    const csv = toCSV(exportRows);
    downloadBlob(`${exportNameBase}.csv`, new Blob([csv], { type: "text/csv;charset=utf-8" }));
  };

  const onExportXlsx = async () => {
    await exportToXlsx(`${exportNameBase}.xlsx`, "data", exportRows);
  };

  // Render charts por dashboard
  const renderCharts = () => {
    if (filteredSessions.length === 0) {
      return <div className="empty">No hay sesiones para los filtros seleccionados.</div>;
    }
    if (statsLoading) {
      return <div className="loading">Calculando estadísticas…</div>;
    }

    if (activeDashboard === "MACHINES_DISTANCE") {
      const data = dataset as Array<{ machine: string; plate: string; km: number; sessions: number }>;
      return (
        <div className="grid">
          <div className="panel">
            <div className="panel-title">Top máquinas por distancia (km)</div>
            <div className="panel-subtitle">Muestra las 12 máquinas con mayor distancia total en el set filtrado.</div>
            <div className="chart">
              <ResponsiveContainer width="100%" height={340}>
                <BarChart data={data}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="machine" tick={{ fontSize: 12 }} interval={0} angle={-15} textAnchor="end" height={70} />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="km" name="Km" />
                  <Bar dataKey="sessions" name="Sesiones" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="panel">
            <div className="panel-title">Tabla del gráfico (exportable)</div>
            <div className="table">
              <table>
                <thead>
                  <tr>
                    <th>Máquina</th>
                    <th>Patente</th>
                    <th style={{ textAlign: "right" }}>Km</th>
                    <th style={{ textAlign: "right" }}>Sesiones</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((r) => (
                    <tr key={`${r.machine}-${r.plate}`}>
                      <td>{r.machine}</td>
                      <td>{r.plate || "—"}</td>
                      <td style={{ textAlign: "right" }}>{fmtNum(r.km, 2)}</td>
                      <td style={{ textAlign: "right" }}>{r.sessions}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      );
    }

    if (activeDashboard === "MACHINES_HOURS") {
      const data = dataset as Array<{ machine: string; plate: string; hours: number; sessions: number }>;
      return (
        <div className="grid">
          <div className="panel">
            <div className="panel-title">Top máquinas por horas</div>
            <div className="panel-subtitle">Horas totales acumuladas (duración de sesión) en el set filtrado.</div>
            <div className="chart">
              <ResponsiveContainer width="100%" height={340}>
                <BarChart data={data}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="machine" tick={{ fontSize: 12 }} interval={0} angle={-15} textAnchor="end" height={70} />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="hours" name="Horas" />
                  <Bar dataKey="sessions" name="Sesiones" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="panel">
            <div className="panel-title">Tabla del gráfico (exportable)</div>
            <div className="table">
              <table>
                <thead>
                  <tr>
                    <th>Máquina</th>
                    <th>Patente</th>
                    <th style={{ textAlign: "right" }}>Horas</th>
                    <th style={{ textAlign: "right" }}>Sesiones</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((r) => (
                    <tr key={`${r.machine}-${r.plate}`}>
                      <td>{r.machine}</td>
                      <td>{r.plate || "—"}</td>
                      <td style={{ textAlign: "right" }}>{fmtNum(r.hours, 2)}</td>
                      <td style={{ textAlign: "right" }}>{r.sessions}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      );
    }

    if (activeDashboard === "DAILY_SESSIONS") {
      const data = dataset as Array<{ day: string; sessions: number; km: number; hours: number }>;
      return (
        <div className="grid">
          <div className="panel">
            <div className="panel-title">Sesiones por día</div>
            <div className="panel-subtitle">Serie temporal: sesiones/día y distancia (km).</div>
            <div className="chart">
              <ResponsiveContainer width="100%" height={340}>
                <LineChart data={data}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="day" tick={{ fontSize: 12 }} />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="sessions" name="Sesiones" />
                  <Line type="monotone" dataKey="km" name="Km" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="panel">
            <div className="panel-title">Tabla del gráfico (exportable)</div>
            <div className="table">
              <table>
                <thead>
                  <tr>
                    <th>Día</th>
                    <th style={{ textAlign: "right" }}>Sesiones</th>
                    <th style={{ textAlign: "right" }}>Km</th>
                    <th style={{ textAlign: "right" }}>Horas</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((r) => (
                    <tr key={r.day}>
                      <td>{r.day}</td>
                      <td style={{ textAlign: "right" }}>{r.sessions}</td>
                      <td style={{ textAlign: "right" }}>{fmtNum(r.km, 2)}</td>
                      <td style={{ textAlign: "right" }}>{fmtNum(r.hours, 2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      );
    }

    if (activeDashboard === "ALERTS_BY_TYPE") {
      const data = dataset as Array<{ type: string; count: number }>;
      // Recharts pide color por slice; dejamos palette simple sin hardcode agresivo
      const colors = ["#2b6cb0", "#2f855a", "#b7791f", "#9b2c2c", "#6b46c1", "#285e61", "#744210"];
      return (
        <div className="grid">
          <div className="panel">
            <div className="panel-title">Alertas por tipo</div>
            <div className="panel-subtitle">Conteo de flags detectadas dentro del set filtrado.</div>
            <div className="chart">
              <ResponsiveContainer width="100%" height={340}>
                <PieChart>
                  <Tooltip />
                  <Legend />
                  <Pie data={data} dataKey="count" nameKey="type" outerRadius={120} label>
                    {data.map((_, idx) => (
                      <Cell key={idx} fill={colors[idx % colors.length]} />
                    ))}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="panel">
            <div className="panel-title">Tabla del gráfico (exportable)</div>
            <div className="table">
              <table>
                <thead>
                  <tr>
                    <th>Tipo de alerta</th>
                    <th style={{ textAlign: "right" }}>Cantidad</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((r) => (
                    <tr key={r.type}>
                      <td>{r.type}</td>
                      <td style={{ textAlign: "right" }}>{r.count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      );
    }

    // SPEED_DISTRIBUTION
    const data = dataset as Array<{ bucket: string; sessions: number }>;
    return (
      <div className="grid">
        <div className="panel">
          <div className="panel-title">Distribución de velocidad media</div>
          <div className="panel-subtitle">Bucketiza la velocidad media por sesión (km/h).</div>
          <div className="chart">
            <ResponsiveContainer width="100%" height={340}>
              <BarChart data={data}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="bucket" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="sessions" name="Sesiones" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="panel">
          <div className="panel-title">Tabla del gráfico (exportable)</div>
          <div className="table">
            <table>
              <thead>
                <tr>
                  <th>Rango (km/h)</th>
                  <th style={{ textAlign: "right" }}>Sesiones</th>
                </tr>
              </thead>
              <tbody>
                {data.map((r) => (
                  <tr key={r.bucket}>
                    <td>{r.bucket}</td>
                    <td style={{ textAlign: "right" }}>{r.sessions}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  };

  // ---------- Render ----------
  return (
    <section className="card charts-page">
      <div className="card-header">
        <div>
          <div className="card-title">Dashboards (Gráficos)</div>
          <div className="card-subtitle">
            Selecciona un dashboard, aplica filtros y exporta a CSV/Excel la data exacta que alimenta el gráfico.
          </div>
        </div>
      </div>

      {error && <div className="tracker-error">⚠️ {error}</div>}

      <div className="charts-layout">
        {/* Panel izquierdo: filtros */}
        <div className="charts-left">
          <div className="filters">
            <div className="form-field">
              <label className="form-label">Máquina</label>
              <select
                className="form-select"
                value={selectedMachineId}
                onChange={(e) => setSelectedMachineId(e.target.value)}
              >
                <option value="">Todas</option>
                {machines.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                    {m.plate ? ` (${m.plate})` : ""}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-field">
              <label className="form-label">Centro de Costo</label>
              <select
                className="form-select"
                value={selectedCostCenter}
                onChange={(e) => setSelectedCostCenter(e.target.value)}
              >
                <option value="">Todos</option>
                {costCenters.map((cc) => (
                  <option key={cc} value={cc}>
                    {cc}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-field">
              <label className="form-label">Desde</label>
              <input
                type="date"
                className="form-input"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
              />
            </div>

            <div className="form-field">
              <label className="form-label">Hasta</label>
              <input
                type="date"
                className="form-input"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
              />
            </div>

            <div className="filters-meta">
              {loading ? (
                <div className="loading">Cargando datos…</div>
              ) : (
                <>
                  <div><b>Sesiones filtradas:</b> {filteredSessions.length}</div>
                  <div><b>Sesiones con stats:</b> {sessionRows.filter((r) => r.stats != null).length}</div>
                  <div><b>Alertas (total):</b> {sessionRows.reduce((a, r) => a + r.flags.length, 0)}</div>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Panel derecho: dashboards + gráficos */}
        <div className="charts-right">
          <div className="dash-header">
            <div className="dash-buttons">
              {DASHBOARDS.map((d) => (
                <button
                  key={d.key}
                  className={`dash-btn ${activeDashboard === d.key ? "active" : ""}`}
                  onClick={() => setActiveDashboard(d.key)}
                  disabled={loading}
                >
                  {d.label}
                </button>
              ))}
            </div>

            <div className="dash-actions">
              <div className="dash-desc">
                <div className="dash-desc-title">{DASHBOARDS.find((d) => d.key === activeDashboard)?.label}</div>
                <div className="dash-desc-sub">{DASHBOARDS.find((d) => d.key === activeDashboard)?.desc}</div>
              </div>

              <div className="export">
                <button className="btn" onClick={onExportCsv} disabled={statsLoading || exportRows.length === 0}>
                  Exportar CSV
                </button>
                <button className="btn btn-primary" onClick={onExportXlsx} disabled={statsLoading || exportRows.length === 0}>
                  Exportar Excel
                </button>
              </div>
            </div>
          </div>

          <div className="dash-body">
            {renderCharts()}
          </div>
        </div>
      </div>
    </section>
  );
};

export default ChartsStatsPage;
