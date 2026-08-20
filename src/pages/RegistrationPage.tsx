/* eslint-disable @typescript-eslint/no-explicit-any */
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
import { apiJson, apiFetch } from "../services/http";

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

const mapContainerStyle: CSSProperties = { width: "100%", height: "100%" };
const defaultCenter: google.maps.LatLngLiteral = { lat: -33.45, lng: -70.65 };

function toRad(deg: number): number {
  return (deg * Math.PI) / 180;
}

function haversineMeters(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371000;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const phi1 = toRad(lat1);
  const phi2 = toRad(lat2);
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(phi1) * Math.cos(phi2) * Math.sin(dLon / 2) ** 2;
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

async function safeFetchJSON<T>(path: string): Promise<T | null> {
  try {
    return await apiJson<T>(path);
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

export default function RegistrationPage() {
  const { isLoaded, loadError } = useJsApiLoader({
    id: MAPS_LOADER_ID,
    googleMapsApiKey: import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string,
    libraries: MAPS_LIBRARIES,
  });

  const { isTracking, points, error: trackerError, start, stop, lastPoint } = useTracker();

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

  const [hourmeterStart, setHourmeterStart] = useState<string>("");
  const [tankLitersStart, setTankLitersStart] = useState<string>("");

  const [showFinishModal, setShowFinishModal] = useState(false);
  const [hourmeterFinal, setHourmeterFinal] = useState<string>("");
  const [tankLitersEnd, setTankLitersEnd] = useState<string>("");
  const [fuelRefillLiters, setFuelRefillLiters] = useState<string>("");

  const [localError, setLocalError] = useState<string | null>(null);
  const [localSuccess, setLocalSuccess] = useState<string | null>(null);

  const [mapRef, setMapRef] = useState<google.maps.Map | null>(null);
  const [locating, setLocating] = useState(false);
  const mapWrapperRef = useRef<HTMLDivElement | null>(null);

  const [activeWorkOrderId, setActiveWorkOrderId] = useState<number | null>(null);

  const [hourmeterNow, setHourmeterNow] = useState<number | null>(null);
  const [odometerKm, setOdometerKm] = useState<number | null>(null);
  const [tankLastLiters, setTankLastLiters] = useState<number | null>(null);

  const [uiStartTime, setUiStartTime] = useState<number | null>(null);
  const [uiNow, setUiNow] = useState<number>(0);
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
      sum += haversineMeters(points[i - 1].lat, points[i - 1].lon, points[i].lat, points[i].lon);
    }
    return sum / 1000;
  }, [points]);

  const durationHours = useMemo(() => uiDurationMinutes / 60, [uiDurationMinutes]);

  const estimatedFuelUsedLiters = useMemo(() => {
    const m = selectedMachine;
    if (!m) return null;
    if (m.fuel_consumption_lph != null && durationHours > 0) return durationHours * Number(m.fuel_consumption_lph);
    if (m.fuel_consumption_lpkm != null && distanceKm > 0) return distanceKm * Number(m.fuel_consumption_lpkm);
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

  useEffect(() => {
    const fetchData = async () => {
      const [m, d, cc, f, impl, acts, labs] = await Promise.all([
        safeFetchJSON<Machine[]>("/machines"),
        safeFetchJSON<Driver[]>("/drivers"),
        safeFetchJSON<CostCenter[]>("/cost_centers"),
        safeFetchJSON<FieldPolygon[]>("/fields"),
        safeFetchJSON<Implement[]>("/implements"),
        safeFetchJSON<Activity[]>("/activities"),
        safeFetchJSON<Labor[]>("/labors"),
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

  const handleMachineChange = (value: string) => {
    setSelectedMachineId(value);
    const m = machines.find((x) => x.id === Number(value));
    if (!m) return;
    if (!selectedActivityId && m.default_activity_id != null) setSelectedActivityId(String(m.default_activity_id));
    if (!selectedLaborId && m.default_labor_id != null) setSelectedLaborId(String(m.default_labor_id));
  };

  const handleLaborChange = (value: string) => {
    setSelectedLaborId(value);
    const l = labors.find((x) => x.id === Number(value));
    if (l && Number(selectedActivityId) !== l.activity_id) setSelectedActivityId(String(l.activity_id));
  };

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

  useEffect(() => {
    const mid = Number(selectedMachineId || 0);
    const loadStatus = async () => {
      if (!mid) {
        setHourmeterNow(null);
        setOdometerKm(null);
        setTankLastLiters(null);
        return;
      }
      const [hm, odo, fuel] = await Promise.all([
        safeFetchJSON<HourmeterResp>(`/machines/${mid}/hourmeter`),
        safeFetchJSON<OdometerResp>(`/machines/${mid}/odometer`),
        safeFetchJSON<FuelStatusResp>(`/machines/${mid}/fuel_status`),
      ]);
      if (hm?.hourmeter != null) setHourmeterNow(Number(hm.hourmeter));
      if (odo?.total_distance_m != null) setOdometerKm(Number(odo.total_distance_m) / 1000);

      const lsKey = `tracker:fuel_last_liters:${mid}`;
      const fallback = (() => {
        const v = localStorage.getItem(lsKey);
        const n = v ? Number(v) : null;
        return Number.isFinite(n) ? n : null;
      })();
      const last = fuel?.last_liters != null ? Number(fuel.last_liters) : fallback;
      setTankLastLiters(last);

      if (!isTracking) {
        if (!hourmeterStart && hm?.hourmeter != null) setHourmeterStart(String(Number(hm.hourmeter).toFixed(1)));
        if (!tankLitersStart && last != null) setTankLitersStart(String(last.toFixed(1)));
      }
    };
    loadStatus().catch(console.error);
  }, [selectedMachineId, isTracking, hourmeterStart, tankLitersStart]);

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

  useEffect(() => {
    if (!mapRef || !lastPoint) return;
    mapRef.panTo({ lat: lastPoint.lat, lng: lastPoint.lon });
  }, [lastPoint, mapRef]);

  const routePath: google.maps.LatLngLiteral[] = points.map((p) => ({ lat: p.lat, lng: p.lon }));
  const currentPosition = lastPoint != null ? { lat: lastPoint.lat, lng: lastPoint.lon } : null;
  const effectiveCenter: google.maps.LatLngLiteral = currentPosition ?? defaultCenter;
  const combinedError = trackerError || localError;

  const handleStart = useCallback(async () => {
    setLocalError(null);
    setLocalSuccess(null);

    const tank = parseNumber(tankLitersStart);
    const hmStartCheck = parseNumber(hourmeterStart);
    const err =
      !selectedMachineId ? "Debes seleccionar la máquina."
      : !selectedDriverId ? "Debes seleccionar el conductor."
      : !selectedCostCenterId ? "Debes seleccionar el centro de costo."
      : !selectedImplementId ? "Debes seleccionar el implemento."
      : !selectedLaborId ? "Debes seleccionar la labor."
      : (tank == null || tank < 0) ? "Debes indicar los litros actuales del estanque (>= 0)."
      : (tankCapacity != null && tank > tankCapacity) ? `Los litros no pueden exceder la capacidad del estanque (${tankCapacity} L).`
      : (hmStartCheck == null || hmStartCheck < 0) ? "Debes indicar el horómetro inicial (>= 0)."
      : null;
    if (err) return setLocalError(err);

    try {
      const now = new Date();
      const dateKey = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
      const hmStart = parseNumber(hourmeterStart)!;
      const tankStart = parseNumber(tankLitersStart)!;

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
        season: String(now.getFullYear()),
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

      const woRes = await apiFetch("/work_orders", {
        method: "POST",
        body: JSON.stringify(workOrderPayload),
      });
      const wo = await woRes.json();
      const workOrderId: number = wo.id;
      setActiveWorkOrderId(workOrderId);

      await start({
        machineId: Number(selectedMachineId),
        driverId: Number(selectedDriverId),
        costCenterId: Number(selectedCostCenterId),
        workOrderId,
      });

      setUiStartTime(Date.now());
      setLastDurationMinutes(0);
      setLocalSuccess("Recorrido iniciado. Quedó asociado a un parte diario.");
      mapWrapperRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (e: any) {
      console.error(e);
      setLocalError(e?.message || "No se pudo iniciar el recorrido.");
    }
  }, [start, selectedMachineId, selectedDriverId, selectedCostCenterId, selectedImplementId, selectedActivityId, selectedLaborId, selectedFieldId, tankLitersStart, hourmeterStart, labors, tankCapacity]);

  const openFinish = () => {
    setLocalError(null);
    setLocalSuccess(null);
    if (!hourmeterFinal && hourmeterStart) setHourmeterFinal(hourmeterStart);
    if (!tankLitersEnd && tankLitersStart) setTankLitersEnd(tankLitersStart);
    if (!fuelRefillLiters) setFuelRefillLiters("");
    setShowFinishModal(true);
  };

  const handleStopConfirmed = useCallback(async () => {
    setLocalError(null);
    setLocalSuccess(null);

    const hmStart = parseNumber(hourmeterStart);
    const hmEnd = parseNumber(hourmeterFinal);
    const endL = parseNumber(tankLitersEnd);
    const refill = parseNumber(fuelRefillLiters);
    const err =
      hmStart == null ? "Horómetro inicial inválido."
      : (hmEnd == null || hmEnd < hmStart) ? "Horómetro final debe ser >= horómetro inicial."
      : (endL == null || endL < 0) ? "Litros al finalizar inválidos (>= 0)."
      : (tankCapacity != null && endL > tankCapacity) ? `Los litros finales no pueden exceder la capacidad (${tankCapacity} L).`
      : (refill != null && refill < 0) ? "Litros recargados inválidos (>= 0)."
      : null;
    if (err) return setLocalError(err);

    try {
      if (uiStartTime !== null) {
        const finalMinutes = (Date.now() - uiStartTime) / 60000;
        setLastDurationMinutes(finalMinutes > 0 ? finalMinutes : 0);
        setUiStartTime(null);
      }
      await stop();

      if (activeWorkOrderId != null) {
        const payload: any = {
          hourmeter_final: parseNumber(hourmeterFinal),
          fuel_refill_liters: parseNumber(fuelRefillLiters),
          fuel_tank_end_liters: parseNumber(tankLitersEnd),
        };
        await apiFetch(`/work_orders/${activeWorkOrderId}`, { method: "PUT", body: JSON.stringify(payload) });

        const mid = Number(selectedMachineId || 0);
        if (mid) localStorage.setItem(`tracker:fuel_last_liters:${mid}`, String(parseNumber(tankLitersEnd) ?? ""));
      }

      setShowFinishModal(false);
      setActiveWorkOrderId(null);
      setLocalSuccess("Recorrido detenido y cierre registrado (horómetro y bencina).");
    } catch (e: any) {
      console.error(e);
      setLocalError(e?.message || "No se pudo detener el recorrido.");
    }
  }, [stop, uiStartTime, activeWorkOrderId, hourmeterFinal, fuelRefillLiters, tankLitersEnd, selectedMachineId, hourmeterStart, tankCapacity]);

  if (loadError) {
    return (
      <section className="ops-panel ops-register-error-card">
        <header><div><span className="section-kicker">Registro de operación</span><h2>No se pudo cargar el mapa</h2><p>Revisa tu conexión y la clave de Google Maps.</p></div></header>
      </section>
    );
  }

  const startLitersNum = parseNumber(tankLitersStart);
  const endLitersNum = parseNumber(tankLitersEnd);

  return (
    <div className="ops-register-layout">
      <aside className="ops-panel ops-register-panel">
        <header>
          <div><span className="section-kicker">Datos reales</span><h2>Registro de operación</h2><p>Reemplaza el dato dummy: registra máquina, labor, horómetro y combustible al iniciar y al finalizar.</p></div>
        </header>

        <div className="ops-register-stats">
          <div><span>Horómetro actual</span><b>{formatHrs(hourmeterNow)}</b></div>
          <div><span>Odómetro total</span><b>{formatKm(odometerKm)}</b></div>
          <div><span>Estanque histórico</span><b>{formatLiters(tankLastLiters)}</b></div>
          <div><span>Capacidad</span><b>{tankCapacity != null ? `${tankCapacity} L` : "—"}</b></div>
        </div>

        {!isTracking ? (
          <div className="ops-register-form">
            <label className="ops-register-field">
              <span>Máquina</span>
              <select value={selectedMachineId} onChange={(e) => handleMachineChange(e.target.value)}>
                <option value="">Seleccionar máquina</option>
                {machines.map((m) => <option key={m.id} value={m.id}>{m.name}{m.plate ? ` (${m.plate})` : ""}</option>)}
              </select>
            </label>

            <label className="ops-register-field">
              <span>Conductor</span>
              <select value={selectedDriverId} onChange={(e) => setSelectedDriverId(e.target.value)}>
                <option value="">Seleccionar tu nombre</option>
                {drivers.map((d) => <option key={d.id} value={d.id}>{d.name}{d.rut ? ` (${d.rut})` : ""}</option>)}
              </select>
            </label>

            <label className="ops-register-field">
              <span>Centro de costo</span>
              <select value={selectedCostCenterId} onChange={(e) => { setSelectedCostCenterId(e.target.value); setSelectedFieldId(""); }}>
                <option value="">Seleccionar centro de costo</option>
                {costCenters.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>

            <label className="ops-register-field">
              <span>Predio (opcional)</span>
              <select value={selectedFieldId} onChange={(e) => setSelectedFieldId(e.target.value)}>
                <option value="">(Opcional) Seleccionar predio</option>
                {filteredFields.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
              </select>
            </label>

            <label className="ops-register-field">
              <span>Implemento</span>
              <select value={selectedImplementId} onChange={(e) => setSelectedImplementId(e.target.value)}>
                <option value="">{implementsList.length ? "Seleccionar implemento" : "No hay implementos"}</option>
                {implementsList.map((i) => <option key={i.id} value={i.id}>{i.name}</option>)}
              </select>
            </label>

            <label className="ops-register-field">
              <span>Actividad</span>
              <select value={selectedActivityId} onChange={(e) => { setSelectedActivityId(e.target.value); setSelectedLaborId(""); }}>
                <option value="">{activities.length ? "Seleccionar actividad" : "Cargando…"}</option>
                {activities.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
              </select>
            </label>

            <label className="ops-register-field">
              <span>Labor</span>
              <select value={selectedLaborId} onChange={(e) => handleLaborChange(e.target.value)}>
                <option value="">{filteredLabors.length ? "Seleccionar labor" : "Sin labores"}</option>
                {filteredLabors.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
              </select>
            </label>

            <label className="ops-register-field">
              <span>Horómetro inicial</span>
              <input type="number" min={0} step="0.1" value={hourmeterStart} onChange={(e) => setHourmeterStart(e.target.value)} placeholder="Ej: 118,0…" />
            </label>

            <label className="ops-register-field">
              <span>Litros actuales en estanque</span>
              {tankCapacity != null ? (
                <div className="ops-register-tank">
                  <input type="range" min={0} max={tankCapacity} step={0.5} value={startLitersNum != null ? clamp(startLitersNum, 0, tankCapacity) : 0} onChange={(e) => setTankLitersStart(e.target.value)} />
                  <div className="ops-register-tank__row">
                    <input type="number" min={0} max={tankCapacity} step="0.1" value={tankLitersStart} onChange={(e) => setTankLitersStart(e.target.value)} placeholder="Ej: 60…" />
                    <div className="ops-register-tank__meta">
                      <b>{formatLiters(startLitersNum)}</b> / {tankCapacity} L
                      {estimatedTankNow != null && <small>Estimado en curso: <b>{formatLiters(estimatedTankNow)}</b></small>}
                    </div>
                  </div>
                </div>
              ) : (
                <input type="number" min={0} step="0.1" value={tankLitersStart} onChange={(e) => setTankLitersStart(e.target.value)} placeholder="Ej: 60…" />
              )}
            </label>

            <button type="button" className="ops-action ops-action--dark ops-register-submit" onClick={handleStart}>Iniciar recorrido</button>
            <div className="ops-register-status"><i className="ops-dot" /> Recorrido detenido.</div>

            {combinedError && <div className="ops-register-alert is-error" role="alert">{combinedError}</div>}
            {localSuccess && <div className="ops-register-alert is-success" role="status" aria-live="polite">{localSuccess}</div>}
          </div>
        ) : (
          <div className="ops-register-tracking">
            <b>Recorrido en curso</b>
            <div className="ops-register-tracking__grid">
              <div><span>Duración</span><b>{formatHrs(durationHours)}</b></div>
              <div><span>Distancia</span><b>{formatKm(distanceKm)}</b></div>
              <div><span>Combustible estimado</span><b>{formatLiters(estimatedFuelUsedLiters)}</b></div>
              <div><span>Estanque estimado</span><b>{formatLiters(estimatedTankNow)}</b></div>
            </div>
            <button type="button" className="ops-action ops-action--dark ops-register-submit" onClick={openFinish}>Finalizar y registrar</button>
            {combinedError && <div className="ops-register-alert is-error" role="alert">{combinedError}</div>}
            {localSuccess && <div className="ops-register-alert is-success" role="status" aria-live="polite">{localSuccess}</div>}
          </div>
        )}
      </aside>

      <section className="ops-map-card ops-register-map" ref={mapWrapperRef}>
        <header>
          <div><span className="section-kicker">GPS en vivo</span><h2>Recorrido actual</h2><p>{isTracking ? "Transmitiendo posición…" : "Sin transmisión activa"}</p></div>
          <div className="ops-layer-controls">
            <button type="button" onClick={handleCenterOnMe} disabled={locating}>{locating ? "Localizando…" : "Centrar en mí"}</button>
          </div>
        </header>
        <div className="ops-map-frame">
          {!isLoaded ? (
            <div className="ops-map-state"><span className="view-loader__spinner" /> Cargando mapa…</div>
          ) : (
            <GoogleMap
              onLoad={(map) => setMapRef(map)}
              center={effectiveCenter}
              zoom={17}
              mapContainerStyle={mapContainerStyle}
              options={{ mapTypeId: "hybrid", streetViewControl: false, fullscreenControl: false, mapTypeControl: false }}
            >
              {fields.map((f) => (
                <Polygon
                  key={f.id}
                  path={f.polygon.map((p) => ({ lat: p.lat, lng: p.lon }))}
                  options={{ strokeColor: f.color || "#1d4ed8", strokeOpacity: 0.9, strokeWeight: 2, fillColor: f.color || "#1d4ed8", fillOpacity: 0.16, clickable: false }}
                />
              ))}
              {routePath.length > 1 && (
                <Polyline path={routePath} options={{ strokeColor: "#d94835", strokeOpacity: 0.95, strokeWeight: 4 }} />
              )}
              {currentPosition && (
                <Marker
                  position={currentPosition}
                  icon={{ path: google.maps.SymbolPath.CIRCLE, scale: 7, strokeColor: "#d94835", strokeWeight: 2, fillColor: "#ffffff", fillOpacity: 1 }}
                />
              )}
            </GoogleMap>
          )}
        </div>
        <footer><span><i className="ops-dot is-lime" /> Predios registrados</span><span><i className="ops-line-sample" /> Recorrido GPS real</span><b>Dato productivo</b></footer>
      </section>

      {showFinishModal && (
        <div className="ops-modal-backdrop" role="dialog" aria-modal="true">
          <div className="ops-modal">
            <h2>Finalizar recorrido</h2>
            <p>Registra el horómetro final y el estado del estanque.</p>
            <div className="ops-modal__body">
              <label className="ops-register-field">
                <span>Horómetro final</span>
                <input type="number" min={0} step="0.1" value={hourmeterFinal} onChange={(e) => setHourmeterFinal(e.target.value)} />
              </label>
              <label className="ops-register-field">
                <span>Litros al finalizar</span>
                {tankCapacity != null ? (
                  <div className="ops-register-tank">
                    <input type="range" min={0} max={tankCapacity} step={0.5} value={endLitersNum != null ? clamp(endLitersNum, 0, tankCapacity) : 0} onChange={(e) => setTankLitersEnd(e.target.value)} />
                    <div className="ops-register-tank__row">
                      <input type="number" min={0} max={tankCapacity} step="0.1" value={tankLitersEnd} onChange={(e) => setTankLitersEnd(e.target.value)} />
                      <div className="ops-register-tank__meta"><b>{formatLiters(endLitersNum)}</b> / {tankCapacity} L</div>
                    </div>
                  </div>
                ) : (
                  <input type="number" min={0} step="0.1" value={tankLitersEnd} onChange={(e) => setTankLitersEnd(e.target.value)} />
                )}
              </label>
              <label className="ops-register-field">
                <span>Litros recargados (opcional)</span>
                <input type="number" min={0} step="0.1" value={fuelRefillLiters} onChange={(e) => setFuelRefillLiters(e.target.value)} placeholder="Ej: 20…" />
              </label>
              {combinedError && <div className="ops-register-alert is-error" role="alert">{combinedError}</div>}
            </div>
            <div className="ops-modal__actions">
              <button type="button" className="ops-action" onClick={() => setShowFinishModal(false)}>Cancelar</button>
              <button type="button" className="ops-action ops-action--dark" onClick={handleStopConfirmed}>Guardar y finalizar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
