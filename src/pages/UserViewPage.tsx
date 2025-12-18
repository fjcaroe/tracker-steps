/* eslint-disable react-hooks/purity */
/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable @typescript-eslint/no-unused-vars */

import {
  useEffect,
  useMemo,
  useState,
  useCallback,
  useRef,
  type CSSProperties,
} from "react";
import {
  GoogleMap,
  Marker,
  Polygon,
  Polyline,
  useJsApiLoader,
} from "@react-google-maps/api";
import { MAPS_LIBRARIES, MAPS_LOADER_ID } from "../mapsConfig";
import { useTracker } from "../hooks/useTracker";
import "./UserViewPage.scss";

const apiBaseUrl =
  ((import.meta.env.VITE_API_BASE_URL as string | undefined) ||
    "http://localhost:8000").replace(/\/+$/, "");

type Machine = {
  id: number;
  name: string;
  plate?: string | null;

  tank_capacity_liters?: number | null;
  fuel_consumption_lph?: number | null;
  fuel_consumption_lpkm?: number | null;

  default_activity_id?: number | null;
  default_labor_id?: number | null;
};

type Driver = { id: number; name: string; rut?: string | null };
type CostCenter = { id: number; name: string };

type FieldPolygon = {
  id: number;
  name: string;
  cost_center_id?: number | null;
  color?: string | null;
  polygon: { lat: number; lon: number }[];
};

type Implement = { id: number; name: string };
type Activity = { id: number; name: string; code?: string | null };

type Labor = {
  id: number;
  activity_id: number;
  name: string;
  code?: string | null;
  effort_factor?: number | null;
  target_speed_kmh?: number | null;
};

type HourmeterResp = { hourmeter: number; last_session_at?: string | null };
type OdometerResp = { total_distance_m: number; total_sessions: number; last_session_at?: string | null };
type FuelStatusResp = { machine_id: number; tank_capacity_liters?: number | null; last_liters?: number | null };

const mapContainerStyle: CSSProperties = {
  width: "100%",
  minHeight: "420px",
  borderRadius: "14px",
  overflow: "hidden",
};

const defaultCenter: google.maps.LatLngLiteral = { lat: -33.45, lng: -70.65 };

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

function parseNumber(value: string): number | null {
  const n = parseFloat((value || "").replace(",", "."));
  return Number.isFinite(n) ? n : null;
}

function clamp(n: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, n));
}

async function safeFetchJSON<T>(url: string): Promise<T | null> {
  try {
    const r = await fetch(url);
    if (!r.ok) return null;
    return (await r.json()) as T;
  } catch {
    return null;
  }
}

function formatKm(n: number | null | undefined): string {
  if (n == null) return "—";
  return n >= 10 ? `${n.toFixed(0)} km` : `${n.toFixed(1)} km`;
}

function formatHrs(n: number | null | undefined): string {
  if (n == null) return "—";
  return `${n.toFixed(1)} h`;
}

function formatLiters(n: number | null | undefined): string {
  if (n == null) return "—";
  return `${n.toFixed(1).replace(".", ",")} L`;
}

const UserViewPage = () => {
  const { isLoaded, loadError } = useJsApiLoader({
    id: MAPS_LOADER_ID,
    googleMapsApiKey: import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string,
    libraries: MAPS_LIBRARIES,
  });

  const { isTracking, points, error: trackerError, start, stop, lastPoint } =
    useTracker();

  const [machines, setMachines] = useState<Machine[]>([]);
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [costCenters, setCostCenters] = useState<CostCenter[]>([]);
  const [fields, setFields] = useState<FieldPolygon[]>([]);

  const [implementsList, setImplementsList] = useState<Implement[]>([]);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [labors, setLabors] = useState<Labor[]>([]);

  const [selectedMachineId, setSelectedMachineId] = useState<string>("");
  const [selectedDriverId, setSelectedDriverId] = useState<string>("");
  const [selectedCostCenterId, setSelectedCostCenterId] = useState<string>("");

  const [selectedImplementId, setSelectedImplementId] = useState<string>("");
  const [selectedActivityId, setSelectedActivityId] = useState<string>("");
  const [selectedLaborId, setSelectedLaborId] = useState<string>("");
  const [selectedFieldId, setSelectedFieldId] = useState<string>("");

  // Inicio
  const [hourmeterStart, setHourmeterStart] = useState<string>("");
  const [tankLitersStart, setTankLitersStart] = useState<string>("");

  // Cierre (modal)
  const [showFinishModal, setShowFinishModal] = useState(false);
  const [hourmeterFinal, setHourmeterFinal] = useState<string>("");
  const [tankLitersEnd, setTankLitersEnd] = useState<string>("");
  const [fuelRefillLiters, setFuelRefillLiters] = useState<string>("");

  const [localError, setLocalError] = useState<string | null>(null);
  const [localSuccess, setLocalSuccess] = useState<string | null>(null);

  const [mapRef, setMapRef] = useState<google.maps.Map | null>(null);
  const [locating, setLocating] = useState(false);
  const mapWrapperRef = useRef<HTMLDivElement | null>(null);

  // WorkOrder activo
  const [activeWorkOrderId, setActiveWorkOrderId] = useState<number | null>(null);

  // Estado “live”
  const [hourmeterNow, setHourmeterNow] = useState<number | null>(null);
  const [odometerKm, setOdometerKm] = useState<number | null>(null);
  const [tankLastLiters, setTankLastLiters] = useState<number | null>(null);

  // timer local UI
  const [uiStartTime, setUiStartTime] = useState<number | null>(null);
  const [uiNow, setUiNow] = useState<number>(Date.now());
  const [lastDurationMinutes, setLastDurationMinutes] = useState<number>(0);

  useEffect(() => {
    if (uiStartTime === null) return;
    const id = setInterval(() => setUiNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [uiStartTime]);

  const uiDurationMinutes = useMemo(() => {
    if (uiStartTime === null) return lastDurationMinutes;
    const diffMs = uiNow - uiStartTime;
    return diffMs > 0 ? diffMs / 60000 : 0;
  }, [uiStartTime, uiNow, lastDurationMinutes]);

  const selectedMachine = useMemo(() => {
    if (!selectedMachineId) return null;
    return machines.find((m) => m.id === Number(selectedMachineId)) ?? null;
  }, [machines, selectedMachineId]);

  const tankCapacity = useMemo(() => {
    const c = selectedMachine?.tank_capacity_liters ?? null;
    return c != null ? Number(c) : null;
  }, [selectedMachine]);

  const distanceKm = useMemo(() => {
    if (points.length < 2) return 0;
    let sum = 0;
    for (let i = 1; i < points.length; i++) {
      const p1 = points[i - 1];
      const p2 = points[i];
      sum += haversineMeters(p1.lat, p1.lon, p2.lat, p2.lon);
    }
    return sum / 1000;
  }, [points]);

  const durationHours = useMemo(() => uiDurationMinutes / 60, [uiDurationMinutes]);

  const estimatedFuelUsedLiters = useMemo(() => {
    const m = selectedMachine;
    if (!m) return null;

    if (m.fuel_consumption_lph != null && durationHours > 0) {
      return durationHours * Number(m.fuel_consumption_lph);
    }
    if (m.fuel_consumption_lpkm != null && distanceKm > 0) {
      return distanceKm * Number(m.fuel_consumption_lpkm);
    }
    return null;
  }, [selectedMachine, durationHours, distanceKm]);

  const estimatedTankNow = useMemo(() => {
    const startL = parseNumber(tankLitersStart);
    if (startL == null) return null;
    const used = estimatedFuelUsedLiters ?? 0;
    let est = startL - used;
    if (tankCapacity != null) est = clamp(est, 0, tankCapacity);
    return est;
  }, [tankLitersStart, estimatedFuelUsedLiters, tankCapacity]);

  // cargar básicos
  useEffect(() => {
    const fetchData = async () => {
      const [m, d, cc, f, impl, acts, labs] = await Promise.all([
        safeFetchJSON<Machine[]>(`${apiBaseUrl}/machines`),
        safeFetchJSON<Driver[]>(`${apiBaseUrl}/drivers`),
        safeFetchJSON<CostCenter[]>(`${apiBaseUrl}/cost_centers`),
        safeFetchJSON<FieldPolygon[]>(`${apiBaseUrl}/fields`),
        safeFetchJSON<Implement[]>(`${apiBaseUrl}/implements`),
        safeFetchJSON<Activity[]>(`${apiBaseUrl}/activities`),
        safeFetchJSON<Labor[]>(`${apiBaseUrl}/labors`),
      ]);

      if (m) setMachines(m);
      if (d) setDrivers(d);
      if (cc) setCostCenters(cc);
      if (f) setFields(f);
      if (impl) setImplementsList(impl);
      if (acts) setActivities(acts);
      if (labs) setLabors(labs);
    };

    fetchData().catch((e) => {
      console.error(e);
      setLocalError("No se pudieron cargar los datos iniciales.");
    });
  }, []);

  // Defaults por máquina
  useEffect(() => {
    if (!selectedMachineId) return;
    const id = Number(selectedMachineId);
    const m = machines.find((x) => x.id === id);
    if (!m) return;

    if (!selectedActivityId && m.default_activity_id != null) {
      setSelectedActivityId(String(m.default_activity_id));
    }
    if (!selectedLaborId && m.default_labor_id != null) {
      setSelectedLaborId(String(m.default_labor_id));
    }
  }, [selectedMachineId, machines, selectedActivityId, selectedLaborId]);

  // Si elijo labor, sincronizo activity
  useEffect(() => {
    if (!selectedLaborId) return;
    const l = labors.find((x) => x.id === Number(selectedLaborId));
    if (!l) return;
    if (!selectedActivityId || Number(selectedActivityId) !== l.activity_id) {
      setSelectedActivityId(String(l.activity_id));
    }
  }, [selectedLaborId, labors, selectedActivityId]);

  const filteredLabors = useMemo(() => {
    if (!selectedActivityId) return labors;
    const aid = Number(selectedActivityId);
    return labors.filter((l) => l.activity_id === aid);
  }, [labors, selectedActivityId]);

  const filteredFields = useMemo(() => {
    if (!selectedCostCenterId) return fields;
    const ccid = Number(selectedCostCenterId);
    return fields.filter((f) => (f.cost_center_id ?? null) === ccid);
  }, [fields, selectedCostCenterId]);

  // --- carga “estado live” de máquina (horómetro/odómetro/bencina histórica) ---
  useEffect(() => {
    const mid = Number(selectedMachineId || 0);
    if (!mid) {
      setHourmeterNow(null);
      setOdometerKm(null);
      setTankLastLiters(null);
      return;
    }

    const loadStatus = async () => {
      const [hm, odo, fuel] = await Promise.all([
        safeFetchJSON<HourmeterResp>(`${apiBaseUrl}/machines/${mid}/hourmeter`),
        safeFetchJSON<OdometerResp>(`${apiBaseUrl}/machines/${mid}/odometer`),
        safeFetchJSON<FuelStatusResp>(`${apiBaseUrl}/machines/${mid}/fuel_status`),
      ]);

      if (hm?.hourmeter != null) setHourmeterNow(Number(hm.hourmeter));
      if (odo?.total_distance_m != null) setOdometerKm(Number(odo.total_distance_m) / 1000);

      // bencina: si no existe endpoint aún, fallback localStorage
      const lsKey = `tracker:fuel_last_liters:${mid}`;
      const fallback = (() => {
        const v = localStorage.getItem(lsKey);
        const n = v ? Number(v) : null;
        return Number.isFinite(n) ? n : null;
      })();

      const last = fuel?.last_liters != null ? Number(fuel.last_liters) : fallback;
      setTankLastLiters(last);

      // Prefill solo si no hay valores ingresados y NO estamos trackeando
      if (!isTracking) {
        if (!hourmeterStart && hm?.hourmeter != null) {
          setHourmeterStart(String(Number(hm.hourmeter).toFixed(1)));
        }
        if (!tankLitersStart && last != null) {
          setTankLitersStart(String(last.toFixed(1)));
        }
      }
    };

    loadStatus().catch(console.error);
  }, [selectedMachineId, isTracking, hourmeterStart, tankLitersStart]);

  // centrar mapa en mi ubicación
  const handleCenterOnMe = () => {
    setLocalError(null);
    if (!navigator.geolocation) {
      setLocalError("Este navegador no soporta geolocalización.");
      return;
    }

    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const coords = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        if (mapRef) {
          mapRef.panTo(coords);
          mapRef.setZoom(18);
        }
        setLocating(false);
      },
      (err) => {
        console.error(err);
        setLocalError("No se pudo obtener tu ubicación actual.");
        setLocating(false);
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    );
  };

  // autopan al último punto
  useEffect(() => {
    if (!mapRef || !lastPoint) return;
    mapRef.panTo({ lat: lastPoint.lat, lng: lastPoint.lon });
  }, [lastPoint, mapRef]);

  const routePath: google.maps.LatLngLiteral[] = points.map((p) => ({ lat: p.lat, lng: p.lon }));
  const currentPosition = lastPoint != null ? { lat: lastPoint.lat, lng: lastPoint.lon } : null;
  const effectiveCenter: google.maps.LatLngLiteral = currentPosition ?? defaultCenter;

  const combinedError = trackerError || localError;

  const validateStart = (): string | null => {
    if (!selectedMachineId) return "Debes seleccionar la máquina.";
    if (!selectedDriverId) return "Debes seleccionar el conductor.";
    if (!selectedCostCenterId) return "Debes seleccionar el centro de costo.";
    if (!selectedImplementId) return "Debes seleccionar el implemento.";
    if (!selectedLaborId) return "Debes seleccionar la labor.";

    const tank = parseNumber(tankLitersStart);
    if (tank == null || tank < 0) return "Debes indicar los litros actuales del estanque (>= 0).";

    if (tankCapacity != null && tank > tankCapacity) {
      return `Los litros no pueden exceder la capacidad del estanque (${tankCapacity} L).`;
    }

    const hmStart = parseNumber(hourmeterStart);
    if (hmStart == null || hmStart < 0) return "Debes indicar el horómetro inicial (>= 0).";

    return null;
  };

  const handleStart = useCallback(async () => {
    setLocalError(null);
    setLocalSuccess(null);

    const err = validateStart();
    if (err) return setLocalError(err);

    try {
      const now = new Date();
      const yyyy = now.getFullYear();
      const mm = String(now.getMonth() + 1).padStart(2, "0");
      const dd = String(now.getDate()).padStart(2, "0");
      const dateKey = `${yyyy}-${mm}-${dd}`;

      const hmStart = parseNumber(hourmeterStart)!;
      const tankStart = parseNumber(tankLitersStart)!;

      // activity_id obligatorio: inferimos desde labor si no está seleccionada
      let activityId = selectedActivityId ? Number(selectedActivityId) : null;
      if (!activityId) {
        const l = labors.find((x) => x.id === Number(selectedLaborId));
        activityId = l?.activity_id ?? null;
      }
      if (!activityId) return setLocalError("No se pudo determinar la actividad para la labor.");

      const woCode = `WO-${dateKey}-M${selectedMachineId}-CC${selectedCostCenterId}-L${selectedLaborId}`;

      const workOrderPayload: any = {
        code: woCode,
        work_date: dateKey,
        season: String(yyyy),

        machine_id: Number(selectedMachineId),
        activity_id: activityId,
        labor_id: Number(selectedLaborId),
        cost_center_id: Number(selectedCostCenterId),
        field_id: selectedFieldId ? Number(selectedFieldId) : null,
        notes: null,

        implement_id: Number(selectedImplementId),
        hourmeter_initial: hmStart,
        fuel_tank_start_liters: tankStart,
      };

      const woRes = await fetch(`${apiBaseUrl}/work_orders`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(workOrderPayload),
      });

      if (!woRes.ok) {
        const text = await woRes.text();
        throw new Error(`No se pudo crear el parte (work order): ${text}`);
      }

      const wo = await woRes.json();
      const workOrderId: number = wo.id;
      setActiveWorkOrderId(workOrderId);

      await start({
        machineId: Number(selectedMachineId),
        driverId: Number(selectedDriverId),
        costCenterId: Number(selectedCostCenterId),
        workOrderId,
      });

      const nowUi = Date.now();
      setUiStartTime(nowUi);
      setLastDurationMinutes(0);

      setLocalSuccess("Recorrido iniciado. Quedó asociado a un parte diario.");

      if (mapWrapperRef.current) {
        mapWrapperRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    } catch (e: any) {
      console.error(e);
      setLocalError(e?.message || "No se pudo iniciar el recorrido.");
    }
  }, [
    start,
    selectedMachineId,
    selectedDriverId,
    selectedCostCenterId,
    selectedImplementId,
    selectedActivityId,
    selectedLaborId,
    selectedFieldId,
    tankLitersStart,
    hourmeterStart,
    labors,
    tankCapacity,
  ]);

  const openFinish = () => {
    setLocalError(null);
    setLocalSuccess(null);

    // Prefill cierre
    if (!hourmeterFinal && hourmeterStart) setHourmeterFinal(hourmeterStart);
    if (!tankLitersEnd && tankLitersStart) setTankLitersEnd(tankLitersStart);
    if (!fuelRefillLiters) setFuelRefillLiters("");

    setShowFinishModal(true);
  };

  const validateFinish = (): string | null => {
    const hmStart = parseNumber(hourmeterStart);
    const hmEnd = parseNumber(hourmeterFinal);
    if (hmStart == null) return "Horómetro inicial inválido.";
    if (hmEnd == null || hmEnd < hmStart) return "Horómetro final debe ser >= horómetro inicial.";

    const endL = parseNumber(tankLitersEnd);
    if (endL == null || endL < 0) return "Litros al finalizar inválidos (>= 0).";
    if (tankCapacity != null && endL > tankCapacity) {
      return `Los litros finales no pueden exceder la capacidad (${tankCapacity} L).`;
    }

    const refill = parseNumber(fuelRefillLiters);
    if (refill != null && refill < 0) return "Litros recargados inválidos (>= 0).";
    return null;
  };

  const handleStopConfirmed = useCallback(async () => {
    setLocalError(null);
    setLocalSuccess(null);

    const err = validateFinish();
    if (err) return setLocalError(err);

    try {
      // congelamos duración UI
      if (uiStartTime !== null) {
        const finalMinutes = (Date.now() - uiStartTime) / 60000;
        setLastDurationMinutes(finalMinutes > 0 ? finalMinutes : 0);
        setUiStartTime(null);
      }

      // 1) Detener tracking (cierra sesión)
      await stop();

      // 2) Guardar cierre en WorkOrder (horómetro final + bencina final + recarga)
      if (activeWorkOrderId != null) {
        const payload: any = {
          hourmeter_final: parseNumber(hourmeterFinal),
          fuel_refill_liters: parseNumber(fuelRefillLiters),
          fuel_tank_end_liters: parseNumber(tankLitersEnd),
        };

        const res = await fetch(`${apiBaseUrl}/work_orders/${activeWorkOrderId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (!res.ok) {
          const text = await res.text();
          throw new Error(`No se pudo guardar el cierre del parte: ${text}`);
        }

        // Persistimos “último valor” en localStorage como fallback + UX
        const mid = Number(selectedMachineId || 0);
        if (mid) {
          localStorage.setItem(
            `tracker:fuel_last_liters:${mid}`,
            String(parseNumber(tankLitersEnd) ?? "")
          );
        }
      }

      setShowFinishModal(false);
      setActiveWorkOrderId(null);

      setLocalSuccess("Recorrido detenido y cierre registrado (horómetro y bencina).");
    } catch (e: any) {
      console.error(e);
      setLocalError(e?.message || "No se pudo detener el recorrido.");
    }
  }, [
    stop,
    uiStartTime,
    activeWorkOrderId,
    hourmeterFinal,
    fuelRefillLiters,
    tankLitersEnd,
    selectedMachineId,
  ]);

  if (loadError) {
    return (
      <section className="card">
        <div className="card-header">
          <div>
            <div className="card-title">Vista Usuario</div>
            <div className="card-subtitle">
              No se pudo cargar Google Maps. Revisa tu conexión y la API key.
            </div>
          </div>
        </div>
      </section>
    );
  }

  const startLitersNum = parseNumber(tankLitersStart);
  const endLitersNum = parseNumber(tankLitersEnd);

  return (
    <section className="card user-view-card">
      <div className="card-header">
        <div>
          <div className="card-title">Vista Usuario</div>
          <div className="card-subtitle">
            Configura el recorrido y registra horómetro/bencina al iniciar y finalizar.
          </div>
        </div>
      </div>

      <div className="user-view-layout">
        <aside className="user-view-panel">
          <div className="user-stats">
            <div className="stat">
              <div className="stat-label">Horómetro (actual)</div>
              <div className="stat-value">{formatHrs(hourmeterNow)}</div>
            </div>
            <div className="stat">
              <div className="stat-label">Odómetro (total)</div>
              <div className="stat-value">{formatKm(odometerKm)}</div>
            </div>
            <div className="stat">
              <div className="stat-label">Estanque (histórico)</div>
              <div className="stat-value">{formatLiters(tankLastLiters)}</div>
            </div>
            <div className="stat">
              <div className="stat-label">Capacidad</div>
              <div className="stat-value">{tankCapacity != null ? `${tankCapacity} L` : "—"}</div>
            </div>
          </div>

          {!isTracking ? (
            <div className="fields-section">
              <div className="fields-section-title">Configuración rápida</div>

              <div className="form-field">
                <label className="form-label">Máquina</label>
                <select
                  className="form-select"
                  value={selectedMachineId}
                  onChange={(e) => setSelectedMachineId(e.target.value)}
                >
                  <option value="">Seleccionar máquina</option>
                  {machines.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name}{m.plate ? ` (${m.plate})` : ""}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-field">
                <label className="form-label">Conductor</label>
                <select
                  className="form-select"
                  value={selectedDriverId}
                  onChange={(e) => setSelectedDriverId(e.target.value)}
                >
                  <option value="">Seleccionar tu nombre</option>
                  {drivers.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}{d.rut ? ` (${d.rut})` : ""}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-field">
                <label className="form-label">Centro de costo</label>
                <select
                  className="form-select"
                  value={selectedCostCenterId}
                  onChange={(e) => {
                    setSelectedCostCenterId(e.target.value);
                    setSelectedFieldId("");
                  }}
                >
                  <option value="">Seleccionar centro de costo</option>
                  {costCenters.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </div>

              <div className="form-field">
                <label className="form-label">Campo (polígono)</label>
                <select
                  className="form-select"
                  value={selectedFieldId}
                  onChange={(e) => setSelectedFieldId(e.target.value)}
                >
                  <option value="">(Opcional) Seleccionar campo</option>
                  {filteredFields.map((f) => (
                    <option key={f.id} value={f.id}>{f.name}</option>
                  ))}
                </select>
              </div>

              <div className="form-field">
                <label className="form-label">Implemento</label>
                <select
                  className="form-select"
                  value={selectedImplementId}
                  onChange={(e) => setSelectedImplementId(e.target.value)}
                >
                  <option value="">
                    {implementsList.length ? "Seleccionar implemento" : "No hay implementos"}
                  </option>
                  {implementsList.map((i) => (
                    <option key={i.id} value={i.id}>{i.name}</option>
                  ))}
                </select>
              </div>

              <div className="form-field">
                <label className="form-label">Actividad</label>
                <select
                  className="form-select"
                  value={selectedActivityId}
                  onChange={(e) => {
                    setSelectedActivityId(e.target.value);
                    setSelectedLaborId("");
                  }}
                >
                  <option value="">{activities.length ? "Seleccionar actividad" : "Cargando…"}</option>
                  {activities.map((a) => (
                    <option key={a.id} value={a.id}>{a.name}</option>
                  ))}
                </select>
              </div>

              <div className="form-field">
                <label className="form-label">Labor</label>
                <select
                  className="form-select"
                  value={selectedLaborId}
                  onChange={(e) => setSelectedLaborId(e.target.value)}
                >
                  <option value="">{filteredLabors.length ? "Seleccionar labor" : "Sin labores"}</option>
                  {filteredLabors.map((l) => (
                    <option key={l.id} value={l.id}>{l.name}</option>
                  ))}
                </select>
              </div>

              <div className="form-field">
                <label className="form-label">Horómetro inicial</label>
                <input
                  className="form-input"
                  type="number"
                  min={0}
                  step="0.1"
                  value={hourmeterStart}
                  onChange={(e) => setHourmeterStart(e.target.value)}
                  placeholder="Ej: 118.0"
                />
              </div>

              <div className="form-field">
                <label className="form-label">Litros actuales en estanque</label>

                {tankCapacity != null ? (
                  <div className="tank-control">
                    <input
                      className="tank-range"
                      type="range"
                      min={0}
                      max={tankCapacity}
                      step={0.5}
                      value={startLitersNum != null ? clamp(startLitersNum, 0, tankCapacity) : 0}
                      onChange={(e) => setTankLitersStart(e.target.value)}
                    />
                    <div className="tank-row">
                      <input
                        className="form-input"
                        type="number"
                        min={0}
                        max={tankCapacity}
                        step="0.1"
                        value={tankLitersStart}
                        onChange={(e) => setTankLitersStart(e.target.value)}
                        placeholder="Ej: 60"
                      />
                      <div className="tank-meta">
                        <div><b>{formatLiters(startLitersNum)}</b> / {tankCapacity} L</div>
                        {estimatedTankNow != null && (
                          <div className="tank-est">
                            Estimado en curso: <b>{formatLiters(estimatedTankNow)}</b>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ) : (
                  <input
                    className="form-input"
                    type="number"
                    min={0}
                    step="0.1"
                    value={tankLitersStart}
                    onChange={(e) => setTankLitersStart(e.target.value)}
                    placeholder="Ej: 60"
                  />
                )}
              </div>

              <div className="tracker-controls">
                <button
                  type="button"
                  className="tracker-button start"
                  onClick={handleStart}
                >
                  Iniciar recorrido
                </button>

                <div className="tracker-status">
                  <span className="status-dot" />
                  <span>Recorrido detenido.</span>
                </div>
              </div>

              {combinedError && <div className="tracker-error">⚠️ {combinedError}</div>}
              {localSuccess && <div className="tracker-success">✅ {localSuccess}</div>}
            </div>
          ) : (
            <div className="tracking-panel">
              <div className="tracking-title">Recorrido en curso</div>
              <div className="tracking-grid">
                <div className="tracking-item">
                  <div className="tracking-label">Duración</div>
                  <div className="tracking-value">{formatHrs(durationHours)}</div>
                </div>
                <div className="tracking-item">
                  <div className="tracking-label">Distancia</div>
                  <div className="tracking-value">{formatKm(distanceKm)}</div>
                </div>
                <div className="tracking-item">
                  <div className="tracking-label">Combustible estimado</div>
                  <div className="tracking-value">{formatLiters(estimatedFuelUsedLiters)}</div>
                </div>
                <div className="tracking-item">
                  <div className="tracking-label">Estanque estimado</div>
                  <div className="tracking-value">{formatLiters(estimatedTankNow)}</div>
                </div>
              </div>

              <button
                type="button"
                className="tracker-button stop"
                onClick={openFinish}
              >
                Finalizar y registrar
              </button>

              {combinedError && <div className="tracker-error">⚠️ {combinedError}</div>}
              {localSuccess && <div className="tracker-success">✅ {localSuccess}</div>}
            </div>
          )}
        </aside>

        <div className="user-view-map" ref={mapWrapperRef}>
          <div className="fields-map-toolbar">
            <button
              type="button"
              className="form-button-secondary"
              onClick={handleCenterOnMe}
              disabled={locating}
            >
              {locating ? "Localizando…" : "Centrar en mi ubicación"}
            </button>
          </div>

          {!isLoaded ? (
            <div className="fields-map-loading">Cargando mapa…</div>
          ) : (
            <div style={{ position: "relative" }}>
              <GoogleMap
                onLoad={(map) => setMapRef(map)}
                center={effectiveCenter}
                zoom={18}
                mapContainerStyle={mapContainerStyle}
                options={{
                  mapTypeId: "hybrid",
                  streetViewControl: false,
                  fullscreenControl: false,
                  mapTypeControl: false,
                }}
              >
                {fields.map((f) => {
                  const path = f.polygon.map((p) => ({ lat: p.lat, lng: p.lon }));
                  const baseColor = f.color || "#1d4ed8";

                  return (
                    <Polygon
                      key={f.id}
                      path={path}
                      options={{
                        strokeColor: baseColor,
                        strokeOpacity: 0.9,
                        strokeWeight: 2,
                        fillColor: baseColor,
                        fillOpacity: 0.18,
                        clickable: false,
                      }}
                    />
                  );
                })}

                {routePath.length > 1 && (
                  <Polyline
                    path={routePath}
                    options={{
                      strokeColor: "#f97316",
                      strokeOpacity: 0.95,
                      strokeWeight: 4,
                    }}
                  />
                )}

                {currentPosition && (
                  <Marker
                    position={currentPosition}
                    icon={{
                      path: google.maps.SymbolPath.CIRCLE,
                      scale: 7,
                      strokeColor: "#f97316",
                      strokeWeight: 2,
                      fillColor: "#ffffff",
                      fillOpacity: 1,
                    }}
                  />
                )}
              </GoogleMap>
            </div>
          )}
        </div>
      </div>

      {/* ===== Modal cierre ===== */}
      {showFinishModal && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal">
            <div className="modal-title">Finalizar recorrido</div>
            <div className="modal-subtitle">
              Registra el horómetro final y el estado del estanque.
            </div>

            <div className="modal-body">
              <div className="form-field">
                <label className="form-label">Horómetro final</label>
                <input
                  className="form-input"
                  type="number"
                  min={0}
                  step="0.1"
                  value={hourmeterFinal}
                  onChange={(e) => setHourmeterFinal(e.target.value)}
                />
              </div>

              <div className="form-field">
                <label className="form-label">Litros al finalizar</label>

                {tankCapacity != null ? (
                  <div className="tank-control">
                    <input
                      className="tank-range"
                      type="range"
                      min={0}
                      max={tankCapacity}
                      step={0.5}
                      value={endLitersNum != null ? clamp(endLitersNum, 0, tankCapacity) : 0}
                      onChange={(e) => setTankLitersEnd(e.target.value)}
                    />
                    <div className="tank-row">
                      <input
                        className="form-input"
                        type="number"
                        min={0}
                        max={tankCapacity}
                        step="0.1"
                        value={tankLitersEnd}
                        onChange={(e) => setTankLitersEnd(e.target.value)}
                      />
                      <div className="tank-meta">
                        <div><b>{formatLiters(endLitersNum)}</b> / {tankCapacity} L</div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <input
                    className="form-input"
                    type="number"
                    min={0}
                    step="0.1"
                    value={tankLitersEnd}
                    onChange={(e) => setTankLitersEnd(e.target.value)}
                  />
                )}
              </div>

              <div className="form-field">
                <label className="form-label">Litros recargados (opcional)</label>
                <input
                  className="form-input"
                  type="number"
                  min={0}
                  step="0.1"
                  value={fuelRefillLiters}
                  onChange={(e) => setFuelRefillLiters(e.target.value)}
                  placeholder="Ej: 20"
                />
              </div>

              {combinedError && <div className="tracker-error">⚠️ {combinedError}</div>}
            </div>

            <div className="modal-actions">
              <button
                type="button"
                className="form-button-ghost"
                onClick={() => setShowFinishModal(false)}
              >
                Cancelar
              </button>
              <button
                type="button"
                className="form-button-primary"
                onClick={handleStopConfirmed}
              >
                Guardar y finalizar
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
};

export default UserViewPage;
