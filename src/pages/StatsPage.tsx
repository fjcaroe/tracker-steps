// src/pages/StatsPage.tsx
/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useMemo, useState } from "react";
import { apiJson } from "../services/http";
import { useAuthWeb } from "../services/useAuthWeb";
import "./StatsPage.scss";

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
  points_count: number; // (existe en el payload, pero NO lo mostramos)
};

type Machine = {
  id: number;
  name: string;
  plate?: string | null;
  tank_capacity_liters?: number | null;
  fuel_consumption_lph?: number | null; // litros/hora
  fuel_consumption_lpkm?: number | null; // litros/km
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

type AggregateStats = {
  sessionsCount: number;
  sessionsWithStats: number;
  totalDistanceKm: number;
  totalDurationHours: number | null;
  avgSpeedKmh: number | null;
  avgDistancePerSessionKm: number | null;

  // Totales estimados (Litros)
  expectedFuelByKm: number | null;
  expectedFuelByHour: number | null;
  maxLitrosUsados: number | null;

  // Tasas (para mostrar al usuario correctamente)
  consumptionRateLpkm: number | null; // L/km
  consumptionRateLph: number | null;  // L/h
};


type Benchmarks = {
  distanceP50: number | null;
  distanceP95: number | null;
  durationP50h: number | null;
  durationP95h: number | null;
  speedP50: number | null;
  speedP95: number | null;
};

type PerMachineAgg = {
  machineId: number;
  machineName: string;
  plate?: string | null;
  sessions: number;
  distanceKm: number;
  durationHours: number;
};

type SessionRow = {
  session: SessionSummary;
  machine: Machine | null;
  stats: SessionStats | null;
  gpsPoints: number | null; // interno (no se muestra)
  fuelMaxLiters: number | null; // estimado por sesión
  flags: string[];
};

// ====== Formato ======
function formatDateTime(value: string | null | undefined) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("es-CL", { dateStyle: "short", timeStyle: "short" });
}

function formatDateOnly(value: string | null | undefined) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("es-CL", { dateStyle: "short" });
}

function formatHHMMFromMinutes(minutes: number | null | undefined): string {
  if (minutes == null || Number.isNaN(minutes)) return "—";
  const totalMin = Math.floor(minutes);
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}`;
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
  // filtra puntos al rango seleccionado (jornada)
  const inRange = points.filter((p) => {
    const t = new Date(p.ts).getTime();
    return !Number.isNaN(t) && t >= rangeMs.lo && t <= rangeMs.hi;
  });

  const sorted = [...inRange].sort(
    (a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime()
  );

  // distancia por GPS
  let distanceMeters = 0;
  if (sorted.length >= 2) {
    for (let i = 1; i < sorted.length; i++) {
      const p1 = sorted[i - 1];
      const p2 = sorted[i];
      distanceMeters += haversineMeters(p1.lat, p1.lon, p2.lat, p2.lon);
    }
  }

  // duración por timestamps de sesión (cortada al rango)
  const startRaw = new Date(session.started_at).getTime();
  if (Number.isNaN(startRaw)) {
    return { distanceKm: distanceMeters / 1000, distanceMeters, durationMinutes: null, durationHours: null, avgSpeedKmh: null };
  }

  const endRaw =
    session.ended_at && !Number.isNaN(new Date(session.ended_at).getTime())
      ? new Date(session.ended_at).getTime()
      : (rangeMs.hi !== Infinity ? rangeMs.hi : Date.now());

  const startMs = clamp(startRaw, rangeMs.lo, rangeMs.hi);
  const endMs = clamp(endRaw, rangeMs.lo, rangeMs.hi);

  const durationMinutes = endMs >= startMs ? (endMs - startMs) / 1000 / 60 : null;
  const durationHours = durationMinutes != null ? durationMinutes / 60 : null;

  const distanceKm = distanceMeters / 1000;
  const avgSpeedKmh = durationHours && durationHours > 0 ? distanceKm / durationHours : null;

  return { distanceKm, distanceMeters, durationMinutes, durationHours, avgSpeedKmh };
}

function getFirstPoint(points: HistoricalPoint[], rangeMs: { lo: number; hi: number }) {
  const inRange = points
    .map((p) => ({ p, t: new Date(p.ts).getTime() }))
    .filter((x) => !Number.isNaN(x.t) && x.t >= rangeMs.lo && x.t <= rangeMs.hi)
    .sort((a, b) => a.t - b.t);
  return inRange[0]?.p ?? null;
}

function getLastPoint(points: HistoricalPoint[], rangeMs: { lo: number; hi: number }) {
  const inRange = points
    .map((p) => ({ p, t: new Date(p.ts).getTime() }))
    .filter((x) => !Number.isNaN(x.t) && x.t >= rangeMs.lo && x.t <= rangeMs.hi)
    .sort((a, b) => a.t - b.t);
  return inRange.length ? inRange[inRange.length - 1].p : null;
}

function eff(s: SessionSummary) {
  return s.effort_factor != null && Number.isFinite(s.effort_factor) ? Number(s.effort_factor) : 1;
}

// ====== Stats helpers ======
function percentile(values: number[], p: number): number | null {
  const v = values.filter((x) => Number.isFinite(x)).slice().sort((a, b) => a - b);
  if (!v.length) return null;
  const idx = (p / 100) * (v.length - 1);
  const lo = Math.floor(idx);
  const hi = Math.ceil(idx);
  if (lo === hi) return v[lo];
  const w = idx - lo;
  return v[lo] * (1 - w) + v[hi] * w;
}

function fmtNum(n: number | null | undefined, digits = 2): string {
  if (n == null || !Number.isFinite(n)) return "—";
  return n.toFixed(digits);
}
function normText(s: string | null | undefined) {
  return (s ?? "")
    .trim()
    .replace(/\s+/g, " ") // colapsa dobles espacios
    .toLowerCase();
}

// ---------- Helpers ----------
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

// ======================================
const StatsPage = () => {
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

  const [sessionStatsById, setSessionStatsById] = useState<Record<string, SessionStats>>({});
  const [sessionGpsPointsById, setSessionGpsPointsById] = useState<Record<string, number>>({});

  const [aggregateStats, setAggregateStats] = useState<AggregateStats | null>(null);
  const [benchmarks, setBenchmarks] = useState<Benchmarks | null>(null);

  const [statsLoading, setStatsLoading] = useState(false);

  const [perMachineAgg, setPerMachineAgg] = useState<PerMachineAgg[]>([]);
  const [uniqueDrivers, setUniqueDrivers] = useState<string[]>([]);

  // UI controls (tabla)
  const [onlyAlerts, setOnlyAlerts] = useState(false);
  const [sortKey, setSortKey] = useState<
    "started_at" | "machine" | "cost_center" | "distance" | "duration" | "speed" | "fuel" | "status"
  >("started_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

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

  const selectedMachine = useMemo(() => {
    if (!selectedMachineId) return null;
    const id = Number(selectedMachineId);
    return machines.find((m) => m.id === id) ?? null;
  }, [selectedMachineId, machines]);

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

    // si la sesión está abierta y hay "Hasta", la cortamos al fin del rango
    const rawEndMs = s.ended_at ? new Date(s.ended_at).getTime() : null;
    const endMs =
      rawEndMs != null && !Number.isNaN(rawEndMs)
        ? rawEndMs
        : hi !== Infinity
          ? hi
          : Date.now();

    // intersección: [start,end] con [lo,hi]
    return startMs <= hi && endMs >= lo;
  });
}


    return [...base].sort(
      (a, b) => new Date(a.started_at).getTime() - new Date(b.started_at).getTime()
    );
  }, [sessions, selectedMachineId, selectedCostCenter, dateFrom, dateTo]);

  // Cálculo de stats por sesión + agregados
  useEffect(() => {
    let cancelled = false;

    const computeForFilters = async () => {
      if (filteredSessions.length === 0) {
        setSessionStatsById({});
        setSessionGpsPointsById({});
        setAggregateStats(null);
        setBenchmarks(null);
        setPerMachineAgg([]);
        setUniqueDrivers([]);
        setStatsLoading(false);
        return;
      }

      setStatsLoading(true);
      const lo = dateFrom ? (parseDateOnlyLocalMs(dateFrom, false) ?? -Infinity) : -Infinity;
const hi = dateTo ? (parseDateOnlyLocalMs(dateTo, true) ?? Infinity) : Infinity;
const rangeMs = { lo, hi };

// agrupa filtered por máquina para saber la "primera del rango"
const filteredByMachine = new Map<number, SessionSummary[]>();
for (const s of filteredSessions) {
  const arr = filteredByMachine.get(s.machine_id) ?? [];
  arr.push(s);
  filteredByMachine.set(s.machine_id, arr);
}
for (const arr of filteredByMachine.values()) {
  arr.sort((a, b) => new Date(a.started_at).getTime() - new Date(b.started_at).getTime());
}

// busca 1 sesión anterior por máquina (en el listado completo "sessions" que ya tienes)
const extraPrevSessions: SessionSummary[] = [];
const prevForFirstInRangeBySessionId: Record<string, SessionSummary | null> = {};

for (const [mid, arr] of filteredByMachine.entries()) {
  const first = arr[0];
  const firstStart = new Date(first.started_at).getTime();

  const prev = [...sessions]
    .filter((x) => x.machine_id === mid && new Date(x.started_at).getTime() < firstStart)
    .sort((a, b) => new Date(a.started_at).getTime() - new Date(b.started_at).getTime())
    .pop() ?? null;

  prevForFirstInRangeBySessionId[first.id] = prev;

  if (prev) {
    // solo la agregamos para fetch de puntos si NO está ya en filtered
    if (!filteredSessions.some((fs) => fs.id === prev.id)) extraPrevSessions.push(prev);
  }
}

      try {
      const sessionsToFetch = [...filteredSessions, ...extraPrevSessions];
// unique por id
const uniqueToFetch = Array.from(new Map(sessionsToFetch.map((s) => [s.id, s])).values());

const pointsBySessionId: Record<string, HistoricalPoint[]> = {};
const gpsCountById: Record<string, number> = {};
const statsById: Record<string, SessionStats> = {};

await Promise.all(
  uniqueToFetch.map(async (s) => {
    try {
      const data = await apiJson<HistoricalPoint[]>(`/sessions/${s.id}/points`);
      pointsBySessionId[s.id] = data;
      gpsCountById[s.id] = data.length;
    } catch (err: any) {
      if (String(err?.message || "").includes("401")) logout();
      // si falla, dejamos sin puntos y que el resto siga
      pointsBySessionId[s.id] = [];
      gpsCountById[s.id] = 0;
    }
  })
);

// stats para las sesiones filtradas (considerando rango)
for (const s of filteredSessions) {
  const pts = pointsBySessionId[s.id] ?? [];
  let st = computeSessionStats(pts, s, rangeMs);

  // puente: último punto sesión anterior -> primer punto actual
  const isFirstInRange = filteredByMachine.get(s.machine_id)?.[0]?.id === s.id;
  const prev = isFirstInRange ? prevForFirstInRangeBySessionId[s.id] : null;

  if (prev) {
    const prevPts = pointsBySessionId[prev.id] ?? [];
    const prevLast = getLastPoint(prevPts, rangeMs);
    const curFirst = getFirstPoint(pts, rangeMs);
    if (prevLast && curFirst) {
      const bridge = haversineMeters(prevLast.lat, prevLast.lon, curFirst.lat, curFirst.lon);
      const newMeters = st.distanceMeters + bridge;
      const newKm = newMeters / 1000;
      const newAvg = st.durationHours && st.durationHours > 0 ? newKm / st.durationHours : null;

      st = { ...st, distanceMeters: newMeters, distanceKm: newKm, avgSpeedKmh: newAvg };
    }
  }

  statsById[s.id] = st;
}

setSessionStatsById(statsById);
setSessionGpsPointsById(gpsCountById);

      

        const validPairs = filteredSessions
          .map((s) => ({ s, st: statsById[s.id] }))
          .filter((x) => !!x.st) as { s: SessionSummary; st: SessionStats }[];

        const sessionsCount = filteredSessions.length;
        const sessionsWithStats = validPairs.length;

        if (sessionsWithStats === 0) {
          setAggregateStats({
              sessionsCount,
              sessionsWithStats,
              totalDistanceKm: 0,
              totalDurationHours: null,
              avgSpeedKmh: null,
              avgDistancePerSessionKm: null,
              expectedFuelByKm: null,
              expectedFuelByHour: null,
              maxLitrosUsados: null,
              consumptionRateLpkm: null,
              consumptionRateLph: null,
            });

          setBenchmarks(null);
          setPerMachineAgg([]);
          setUniqueDrivers([]);
          return;
        }

        const totalDistanceKm = validPairs.reduce((acc, { st }) => acc + st.distanceKm, 0);
        const totalDurationHoursNum = validPairs.reduce((acc, { st }) => acc + (st.durationHours ?? 0), 0);
        const totalDurationHours = Number.isFinite(totalDurationHoursNum) ? totalDurationHoursNum : null;

        const avgSpeedKmh =
          totalDurationHours && totalDurationHours > 0 ? totalDistanceKm / totalDurationHours : null;

        const avgDistancePerSessionKm =
          sessionsCount > 0 ? totalDistanceKm / sessionsCount : null;

        // Benchmarks (p50/p95) para "qué es normal" en este set filtrado
        const distVals = validPairs.map((x) => x.st.distanceKm).filter((x) => Number.isFinite(x) && x >= 0);
        const durVals = validPairs.map((x) => x.st.durationHours ?? 0).filter((x) => Number.isFinite(x) && x >= 0);
        const spdVals = validPairs.map((x) => x.st.avgSpeedKmh ?? 0).filter((x) => Number.isFinite(x) && x >= 0);

        setBenchmarks({
          distanceP50: percentile(distVals, 50),
          distanceP95: percentile(distVals, 95),
          durationP50h: percentile(durVals, 50),
          durationP95h: percentile(durVals, 95),
          speedP50: percentile(spdVals, 50),
          speedP95: percentile(spdVals, 95),
        });

        // Agregados por máquina
        const byMachine = new Map<number, PerMachineAgg>();
        for (const { s, st } of validPairs) {
          const mId = s.machine_id;
          const mMeta = machines.find((m) => m.id === mId) || null;
          const current = byMachine.get(mId) || {
            machineId: mId,
            machineName: mMeta?.name || s.machine_name || `#${mId}`,
            plate: mMeta?.plate ?? null,
            sessions: 0,
            distanceKm: 0,
            durationHours: 0,
          };
          current.sessions += 1;
          current.distanceKm += st.distanceKm;
          current.durationHours += st.durationHours ?? 0;
          byMachine.set(mId, current);
        }
        const perMachine = Array.from(byMachine.values()).sort((a, b) => b.distanceKm - a.distanceKm);
        setPerMachineAgg(perMachine);

        // Conductores únicos
        const drivers = Array.from(
          new Set(
            filteredSessions
              .map((s) => (s.driver_name || "").trim())
              .filter((n) => n.length > 0)
          )
        ).sort();
        setUniqueDrivers(drivers);

const eff = (s: SessionSummary) =>
  s.effort_factor != null && Number.isFinite(s.effort_factor) ? Number(s.effort_factor) : 1;

// Totales estimados (Litros)
let expectedFuelByKm: number | null = null;
let expectedFuelByHour: number | null = null;
let maxLitrosUsados: number | null = null;

if (selectedMachine) {
  const consLpkm = selectedMachine.fuel_consumption_lpkm ?? null;
  const consLph = selectedMachine.fuel_consumption_lph ?? null;

  if (consLpkm != null) {
    const sum = validPairs.reduce((acc, { s, st }) => acc + st.distanceKm * consLpkm * eff(s), 0);
    expectedFuelByKm = Number.isFinite(sum) ? sum : null;
  }

  if (consLph != null) {
    const sum = validPairs.reduce((acc, { s, st }) => acc + (st.durationHours ?? 0) * consLph * eff(s), 0);
    expectedFuelByHour = Number.isFinite(sum) ? sum : null;
  }

  maxLitrosUsados = Math.max(expectedFuelByKm ?? 0, expectedFuelByHour ?? 0);
} else {
  // múltiples máquinas: consumo por sesión usando su máquina
  let sumKm = 0;
  let sumHr = 0;

  for (const { s, st } of validPairs) {
    const mMeta = machines.find((m) => m.id === s.machine_id);
    if (!mMeta) continue;

    if (mMeta.fuel_consumption_lpkm != null) sumKm += st.distanceKm * mMeta.fuel_consumption_lpkm * eff(s);
    if (mMeta.fuel_consumption_lph != null && st.durationHours != null) sumHr += st.durationHours * mMeta.fuel_consumption_lph * eff(s);
  }

  expectedFuelByKm = Number.isFinite(sumKm) ? sumKm : null;
  expectedFuelByHour = Number.isFinite(sumHr) ? sumHr : null;
  maxLitrosUsados = Math.max(expectedFuelByKm ?? 0, expectedFuelByHour ?? 0);
}

const consumptionRateLpkm =
  expectedFuelByKm != null && totalDistanceKm > 0 ? expectedFuelByKm / totalDistanceKm : null;

const consumptionRateLph =
  expectedFuelByHour != null && totalDurationHours != null && totalDurationHours > 0
    ? expectedFuelByHour / totalDurationHours
    : null;

        setAggregateStats({
        sessionsCount,
        sessionsWithStats,
        totalDistanceKm,
        totalDurationHours,
        avgSpeedKmh,
        avgDistancePerSessionKm,
        expectedFuelByKm,
        expectedFuelByHour,
        maxLitrosUsados,

        consumptionRateLpkm,
        consumptionRateLph,
      });
      } finally {
        if (!cancelled) setStatsLoading(false);
      }
    };

    void computeForFilters();
    return () => {
      cancelled = true;
    };
  }, [filteredSessions, machines, selectedMachine, logout]);

  // ====== Construcción de filas “operativas” + alertas ======
  const sessionRows: SessionRow[] = useMemo(() => {
    const b = benchmarks;

    const distP95 = b?.distanceP95 ?? null;
    const durP95h = b?.durationP95h ?? null;
    const spdP95 = b?.speedP95 ?? null;

    const distHigh = distP95 != null && distP95 > 0.1 ? distP95 * 1.25 : null;
    const durHigh = durP95h != null && durP95h > 0.25 ? durP95h * 1.25 : null;

    // hard cap para detectar imposibles (ajústalo si corresponde a tu realidad)
    const speedHardCap = 80; // km/h promedio es rarísimo para maquinaria agrícola
    const speedHigh = spdP95 != null && spdP95 > 5 ? Math.max(speedHardCap, spdP95 * 1.25) : speedHardCap;

    return filteredSessions.map((s) => {
      const machine = machines.find((m) => m.id === s.machine_id) ?? null;
      const stats = sessionStatsById[s.id] ?? null;
      const gpsPoints = typeof sessionGpsPointsById[s.id] === "number" ? sessionGpsPointsById[s.id] : null;

      // Consumo por sesión (si hay maestro)
      const factor = eff(s);

let fuelMaxLiters: number | null = null;
if (stats && machine) {
  const byKm =
    machine.fuel_consumption_lpkm != null ? stats.distanceKm * machine.fuel_consumption_lpkm * factor : null;

  const byHr =
    machine.fuel_consumption_lph != null && stats.durationHours != null
      ? stats.durationHours * machine.fuel_consumption_lph * factor
      : null;

  fuelMaxLiters = Math.max(byKm ?? 0, byHr ?? 0);
}

  

      const flags: string[] = [];

      if (stats == null) flags.push("Sin datos GPS o sin permiso");
      if (s.status === "open") flags.push("Sesión abierta");
      if (s.status === "closed" && !s.ended_at) flags.push("Cerrada sin término");

      if (gpsPoints != null && gpsPoints < 10) flags.push("Datos GPS insuficientes");

      if (stats) {
        const durH = stats.durationHours ?? null;
        const distKm = stats.distanceKm;
        const spd = stats.avgSpeedKmh ?? null;

        if (durH != null && durH > 0.25 && distKm < 0.1) flags.push("Duración alta con distancia casi cero");
        if (distHigh != null && distKm > distHigh) flags.push("Distancia fuera de rango");
        if (durHigh != null && durH != null && durH > durHigh) flags.push("Duración fuera de rango");
        if (spd != null && spd > speedHigh) flags.push("Velocidad media fuera de rango");
      }

      return { session: s, machine, stats, gpsPoints, fuelMaxLiters, flags };
    });
  }, [filteredSessions, machines, sessionStatsById, sessionGpsPointsById, benchmarks]);

  const alertsSummary = useMemo(() => {
    const m = new Map<string, number>();
    for (const r of sessionRows) {
      for (const f of r.flags) m.set(f, (m.get(f) ?? 0) + 1);
    }
    return Array.from(m.entries()).sort((a, b) => b[1] - a[1]);
  }, [sessionRows]);

  const alertSessionsCount = useMemo(() => {
    return sessionRows.filter((r) => r.flags.length > 0).length;
  }, [sessionRows]);

  const visibleRows = useMemo(() => {
    const base = onlyAlerts ? sessionRows.filter((r) => r.flags.length > 0) : sessionRows;

    const dir = sortDir === "asc" ? 1 : -1;

    const str = (v: string | null | undefined) => (v || "").toLowerCase();
    const num = (v: number | null | undefined) => (v == null || !Number.isFinite(v) ? -Infinity : v);

    const sorted = [...base].sort((a, b) => {
      if (sortKey === "started_at") {
        const av = new Date(a.session.started_at).getTime();
        const bv = new Date(b.session.started_at).getTime();
        return (av - bv) * dir;
      }
      if (sortKey === "machine") return (str(a.machine?.name ?? a.session.machine_name) > str(b.machine?.name ?? b.session.machine_name) ? 1 : -1) * dir;
      if (sortKey === "cost_center") return (str(a.session.cost_center_name) > str(b.session.cost_center_name) ? 1 : -1) * dir;
      if (sortKey === "status") return (str(a.session.status) > str(b.session.status) ? 1 : -1) * dir;
      if (sortKey === "distance") return (num(a.stats?.distanceKm) - num(b.stats?.distanceKm)) * dir;
      if (sortKey === "duration") return (num(a.stats?.durationHours) - num(b.stats?.durationHours)) * dir;
      if (sortKey === "speed") return (num(a.stats?.avgSpeedKmh) - num(b.stats?.avgSpeedKmh)) * dir;
      if (sortKey === "fuel") return (num(a.fuelMaxLiters) - num(b.fuelMaxLiters)) * dir;
      return 0;
    });

    return sorted;
  }, [sessionRows, onlyAlerts, sortKey, sortDir]);

  const toggleSort = (key: typeof sortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  // ---------- Render ----------
  return (
    <section className="card stats-page">
      <div className="card-header">
        <div>
          <div className="card-title">Estadísticas</div>
          <div className="card-subtitle">
            Filtra por máquina, centro de costo y fechas. Revisa sesiones, distancias, horas, consumo estimado y, sobre todo,
            identifica sesiones fuera de rango mediante alertas.
          </div>
        </div>
      </div>

      {error && <div className="tracker-error">⚠️ {error}</div>}

      <div className="stats-layout">
        {/* Panel izquierdo */}
        <div className="stats-left">
          <div className="stats-filters">
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
          </div>

          {loading && (
            <div className="sessions-loading" style={{ marginTop: 8 }}>
              Cargando datos…
            </div>
          )}

          {!loading && (
            <>
              <div className="stats-summary-title">Resumen (KPIs)</div>

              {statsLoading && <div className="sessions-loading">Calculando estadísticas…</div>}

              {!statsLoading && (!aggregateStats || filteredSessions.length === 0) && (
                <div className="sessions-empty">No hay sesiones para los filtros seleccionados.</div>
              )}

              {!statsLoading && aggregateStats && (
                <div className="session-stats">
                  <div className="session-stat">
                    <div className="session-stat__label">Sesiones (filtradas)</div>
                    <div className="session-stat__value">{aggregateStats.sessionsCount}</div>
                  </div>

                  <div className="session-stat">
                    <div className="session-stat__label">Sesiones con stats válidos</div>
                    <div className="session-stat__value">{aggregateStats.sessionsWithStats}</div>
                  </div>

                  <div className="session-stat">
                    <div className="session-stat__label">Alertas detectadas</div>
                    <div className="session-stat__value">{alertSessionsCount}</div>
                  </div>

                  <div className="session-stat">
                    <div className="session-stat__label">Distancia total</div>
                    <div className="session-stat__value">{fmtNum(aggregateStats.totalDistanceKm, 2)} km</div>
                  </div>

                  <div className="session-stat">
                    <div className="session-stat__label">Horas totales</div>
                    <div className="session-stat__value">
                      {aggregateStats.totalDurationHours != null ? fmtNum(aggregateStats.totalDurationHours, 2) : "—"} h
                    </div>
                  </div>

                  <div className="session-stat">
                    <div className="session-stat__label">Velocidad media</div>
                    <div className="session-stat__value">
                      {aggregateStats.avgSpeedKmh != null ? `${fmtNum(aggregateStats.avgSpeedKmh, 1)} km/h` : "—"}
                    </div>
                  </div>

                  <div className="session-stat">
                    <div className="session-stat__label">Distancia promedio / sesión</div>
                    <div className="session-stat__value">
                      {aggregateStats.avgDistancePerSessionKm != null ? `${fmtNum(aggregateStats.avgDistancePerSessionKm, 2)} km` : "—"}
                    </div>
                  </div>

             <div className="session-stat">
  <div className="session-stat__label">Consumo (L/km)</div>
  <div className="session-stat__value">
    {aggregateStats.consumptionRateLpkm != null ? `${fmtNum(aggregateStats.consumptionRateLpkm, 3)} L/km` : "—"}
  </div>
  <div className="muted">
    Total est.: {aggregateStats.expectedFuelByKm != null ? `${fmtNum(aggregateStats.expectedFuelByKm, 2)} L` : "—"}
  </div>
</div>

<div className="session-stat">
  <div className="session-stat__label">Consumo (L/h)</div>
  <div className="session-stat__value">
    {aggregateStats.consumptionRateLph != null ? `${fmtNum(aggregateStats.consumptionRateLph, 2)} L/h` : "—"}
  </div>
  <div className="muted">
    Total est.: {aggregateStats.expectedFuelByHour != null ? `${fmtNum(aggregateStats.expectedFuelByHour, 2)} L` : "—"}
  </div>
</div>


                 <div className="session-stat">
  <div className="session-stat__label">Baja de combustible (est.)</div>
  <div className="session-stat__value">
    {aggregateStats.maxLitrosUsados != null ? `${fmtNum(aggregateStats.maxLitrosUsados, 2)} L` : "—"}
  </div>

  {selectedMachine?.tank_capacity_liters != null &&
    aggregateStats.maxLitrosUsados != null &&
    selectedMachine.tank_capacity_liters > 0 && (
      <div className="muted">
        ≈ {fmtNum((aggregateStats.maxLitrosUsados / selectedMachine.tank_capacity_liters) * 100, 1)}% del estanque ·
        Restante (si partiste lleno): {fmtNum(Math.max(0, selectedMachine.tank_capacity_liters - aggregateStats.maxLitrosUsados), 1)} L
      </div>
    )}
</div>

                </div>
              )}

              {/* Referencias (p50/p95) */}
              {!statsLoading && benchmarks && (
                <>
                  <div className="stats-summary-title" style={{ marginTop: 12 }}>
                    Referencias del set filtrado (p50 / p95)
                  </div>
                  <div className="session-stats">
                    <div className="session-stat">
                      <div className="session-stat__label">Distancia</div>
                      <div className="session-stat__value">
                        {benchmarks.distanceP50 != null ? `${fmtNum(benchmarks.distanceP50, 2)} km` : "—"}{" "}
                        / {benchmarks.distanceP95 != null ? `${fmtNum(benchmarks.distanceP95, 2)} km` : "—"}
                      </div>
                    </div>
                    <div className="session-stat">
                      <div className="session-stat__label">Duración</div>
                      <div className="session-stat__value">
                        {benchmarks.durationP50h != null ? `${fmtNum(benchmarks.durationP50h, 2)} h` : "—"}{" "}
                        / {benchmarks.durationP95h != null ? `${fmtNum(benchmarks.durationP95h, 2)} h` : "—"}
                      </div>
                    </div>
                    <div className="session-stat">
                      <div className="session-stat__label">Velocidad media</div>
                      <div className="session-stat__value">
                        {benchmarks.speedP50 != null ? `${fmtNum(benchmarks.speedP50, 1)} km/h` : "—"}{" "}
                        / {benchmarks.speedP95 != null ? `${fmtNum(benchmarks.speedP95, 1)} km/h` : "—"}
                      </div>
                    </div>
                  </div>
                </>
              )}
            </>
          )}
        </div>

        {/* Panel derecho */}
        <div className="stats-right">
          <div className="stats-summary-title">Alertas y tabla operativa de sesiones</div>

          {statsLoading && <div className="sessions-loading">Calculando métricas por sesión…</div>}

          {!statsLoading && filteredSessions.length === 0 && (
            <div className="sessions-empty">No hay sesiones para mostrar con los filtros actuales.</div>
          )}

          {!statsLoading && filteredSessions.length > 0 && (
            <>
              {/* Resumen de alertas */}
              <div className="stats-alerts-panel">
                <div className="stats-alerts-panel__header">
                  <label className="checkbox">
                    <input
                      type="checkbox"
                      checked={onlyAlerts}
                      onChange={(e) => setOnlyAlerts(e.target.checked)}
                    />{" "}
                    Mostrar solo sesiones con alertas
                  </label>

                  <div className="stats-alerts-panel__meta">
                    Total: <b>{sessionRows.length}</b> · En tabla: <b>{visibleRows.length}</b>
                  </div>
                </div>

                {alertsSummary.length > 0 ? (
                  <div className="stats-alerts-chips">
                    {alertsSummary.map(([name, count]) => (
                      <span key={name} className="chip chip--alert" title={name}>
                        {name}: {count}
                      </span>
                    ))}
                  </div>
                ) : (
                  <div className="sessions-empty">Sin alertas detectadas con los filtros actuales.</div>
                )}
              </div>

              {/* Tabla operativa */}
              <div className="stats-table-wrapper stats-table-wrapper--main" style={{ marginTop: 10 }}>
                <table className="stats-table stats-table--compact">
                  <thead>
                    <tr>
                      <th onClick={() => toggleSort("started_at")} style={{ cursor: "pointer" }}>Fecha</th>
                      <th onClick={() => toggleSort("machine")} style={{ cursor: "pointer" }}>Máquina</th>
                      <th>Chofer</th>
                      <th onClick={() => toggleSort("cost_center")} style={{ cursor: "pointer" }}>Centro de Costo</th>
                      <th onClick={() => toggleSort("status")} style={{ cursor: "pointer" }}>Estado</th>
                      <th onClick={() => toggleSort("distance")} style={{ cursor: "pointer", textAlign: "right" }}>Distancia</th>
                      <th onClick={() => toggleSort("duration")} style={{ cursor: "pointer", textAlign: "right" }}>Duración</th>
                      <th onClick={() => toggleSort("speed")} style={{ cursor: "pointer", textAlign: "right" }}>Vel. media</th>
                      <th onClick={() => toggleSort("fuel")} style={{ cursor: "pointer", textAlign: "right" }}>Consumo máx.</th>
                      <th>Alertas</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleRows.map((row) => {
                      const st = row.stats;
                      const hasAlerts = row.flags.length > 0;

                      const machineLabel =
                        row.machine?.name ||
                        row.session.machine_name ||
                        `#${row.session.machine_id}`;

                      const machineExtra = row.machine?.plate ? ` (${row.machine.plate})` : "";

                      return (
                        <tr
                          key={row.session.id}
                          className={hasAlerts ? "stats-row--alert" : ""}
                          title={
                            row.gpsPoints != null
                              ? `Puntos GPS (interno): ${row.gpsPoints}`
                              : "Puntos GPS: no disponible"
                          }
                        >
                          <td>
                            <div>{formatDateOnly(row.session.started_at)}</div>
                            <div className="muted">{formatDateTime(row.session.started_at)}</div>
                          </td>
                          <td>{machineLabel}{machineExtra}</td>
                          <td>{row.session.driver_name || "—"}</td>
                          <td>{row.session.cost_center_name || "—"}</td>
                          <td>
                            <span className={"status-pill " + (row.session.status === "open" ? "status-pill--open" : "status-pill--closed")}>
                              {row.session.status === "open" ? "Abierta" : "Cerrada"}
                            </span>
                          </td>
                          <td style={{ textAlign: "right" }}>{st ? `${fmtNum(st.distanceKm, 2)} km` : "—"}</td>
                          <td style={{ textAlign: "right" }}>{st ? formatHHMMFromMinutes(st.durationMinutes) : "—"}</td>
                          <td style={{ textAlign: "right" }}>
                            {st && st.avgSpeedKmh != null ? `${fmtNum(st.avgSpeedKmh, 1)} km/h` : "—"}
                          </td>
<td style={{ textAlign: "right" }}>
  {row.fuelMaxLiters != null ? (
    <>
      <div>{`${fmtNum(row.fuelMaxLiters, 2)} L`}</div>
      <div className="muted">
        factor: {fmtNum(eff(row.session), 2)}
        {row.session.target_speed_kmh != null ? ` · obj: ${fmtNum(row.session.target_speed_kmh, 1)} km/h` : ""}
      </div>
    </>
  ) : "—"}
</td>

                          <td>
                            {row.flags.length === 0 ? (
                              <span className="muted">—</span>
                            ) : (
                              <div className="stats-flags">
                                {row.flags.map((f) => (
                                  <span key={f} className="chip chip--alert" title={f}>
                                    {f}
                                  </span>
                                ))}
                              </div>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Si hay CC seleccionado: máquinas que pasaron por él */}
              {selectedCostCenter && perMachineAgg.length > 0 && (
                <>
                  <div className="stats-summary-title" style={{ marginTop: 16 }}>
                    Máquinas que pasaron por el Centro de Costo
                  </div>

                  <div className="stats-table-wrapper">
                    <table className="stats-table stats-table--compact">
                      <thead>
                        <tr>
                          <th>Máquina</th>
                          <th>Patente</th>
                          <th style={{ textAlign: "right" }}>Sesiones</th>
                          <th style={{ textAlign: "right" }}>Distancia</th>
                          <th style={{ textAlign: "right" }}>Horas</th>
                        </tr>
                      </thead>
                      <tbody>
                        {perMachineAgg.map((row) => (
                          <tr key={row.machineId}>
                            <td>{row.machineName}</td>
                            <td>{row.plate || "—"}</td>
                            <td style={{ textAlign: "right" }}>{row.sessions}</td>
                            <td style={{ textAlign: "right" }}>{fmtNum(row.distanceKm, 2)} km</td>
                            <td style={{ textAlign: "right" }}>{fmtNum(row.durationHours, 2)} h</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {uniqueDrivers.length > 0 && (
                    <>
                      <div className="stats-summary-title" style={{ marginTop: 12 }}>
                        Conductores que pasaron por el Centro de Costo
                      </div>
                      <div className="cc-driver-chips">
                        {uniqueDrivers.map((d) => (
                          <span key={d} className="chip">
                            {d}
                          </span>
                        ))}
                      </div>
                    </>
                  )}
                </>
              )}
            </>
          )}
        </div>
      </div>
    </section>
  );
};

export default StatsPage;
