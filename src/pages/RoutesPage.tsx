// src/pages/RoutesPage.tsx
/* eslint-disable @typescript-eslint/no-explicit-any */

import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";
import {
  GoogleMap,
  Marker,
  Polygon,
  Polyline,
  useJsApiLoader,
} from "@react-google-maps/api";
import { MAPS_LIBRARIES, MAPS_LOADER_ID } from "../mapsConfig";
import { useTracker } from "../hooks/useTracker";

const apiBaseUrl =
  ((import.meta.env.VITE_API_BASE_URL as string | undefined) ||
    "http://localhost:8000").replace(/\/+$/, "");

type Machine = {
  id: number;
  name: string;
  plate?: string | null;
};

type Driver = {
  id: number;
  name: string;
  rut?: string | null;
};

type CostCenter = {
  id: number;
  name: string;
};

type FieldPolygon = {
  id: number;
  name: string;
  cost_center_id: number | null;
  cost_center_name?: string | null;
  color?: string | null;
  polygon: { lat: number; lon: number }[];
};

type DraftPoint = {
  lat: number;
  lon: number;
  timestamp: number;
};

type FieldStat = {
  fieldId: number;
  fieldName: string;
  costCenterName?: string | null;
  totalDistanceM: number;
  totalTimeMs: number;
};

const defaultCenter: google.maps.LatLngLiteral = {
  lat: -33.45,
  lng: -70.65,
};

const routePolylineOptions: google.maps.PolylineOptions = {
  strokeColor: "#f97316",
  strokeOpacity: 0.95,
  strokeWeight: 4,
};

const fieldPolygonBaseOptions: google.maps.PolygonOptions = {
  strokeOpacity: 0.9,
  strokeWeight: 2,
  fillOpacity: 0.14,
  clickable: true,
};

const mapContainerStyle: CSSProperties = {
  width: "100%",
  minHeight: "460px",
  borderRadius: "14px",
  overflow: "hidden",
};

// ---- helpers geométricos ----

function toRad(deg: number): number {
  return (deg * Math.PI) / 180;
}

// distancia Haversine en metros
function haversineDistanceM(a: DraftPoint, b: DraftPoint): number {
  const R = 6371000; // radio tierra en metros
  const dLat = toRad(b.lat - a.lat);
  const dLon = toRad(b.lon - a.lon);
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);

  const sinDLat = Math.sin(dLat / 2);
  const sinDLon = Math.sin(dLon / 2);

  const h =
    sinDLat * sinDLat +
    Math.cos(lat1) * Math.cos(lat2) * sinDLon * sinDLon;

  const c = 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));
  return R * c;
}

// point-in-polygon (ray casting)
// point: { lat, lon }, polygon: array { lat, lon }
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

function formatDuration(ms: number): string {
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

function formatKm(meters: number): string {
  return `${(meters / 1000).toFixed(2)} km`;
}

function formatKmh(kmh: number): string {
  if (!kmh || kmh < 0.5) return "0 km/h";
  return `${kmh.toFixed(1)} km/h`;
}

function formatLiters(l: number): string {
  return `${l.toFixed(2)} L`;
}

const RoutesPage = () => {
  const { isLoaded, loadError } = useJsApiLoader({
    id: MAPS_LOADER_ID,
    googleMapsApiKey: import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string,
    libraries: MAPS_LIBRARIES,
  });

  const {
    isTracking,
    points,
    error: trackerError,
    sessionId,
    start,
    stop,
    lastPoint,
  } = useTracker();

  const [machines, setMachines] = useState<Machine[]>([]);
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [costCenters, setCostCenters] = useState<CostCenter[]>([]);
  const [fields, setFields] = useState<FieldPolygon[]>([]);

  const [selectedMachineId, setSelectedMachineId] = useState<string>("");
  const [selectedDriverId, setSelectedDriverId] = useState<string>("");
  const [selectedCostCenterId, setSelectedCostCenterId] = useState<string>("");

  const [tankLitersStart, setTankLitersStart] = useState<string>("");
  const [consumptionLPer100Km, setConsumptionLPer100Km] = useState<string>("15");

  const [localError, setLocalError] = useState<string | null>(null);
  const [localSuccess, setLocalSuccess] = useState<string | null>(null);

  const [mapRef, setMapRef] = useState<google.maps.Map | null>(null);
  const [locating, setLocating] = useState(false);

  const [machineOdo, setMachineOdo] = useState<{
    totalDistanceM: number;
    totalSessions: number;
    lastSessionAt?: string | null;
    } | null>(null);

    const [machineOdoLoading, setMachineOdoLoading] = useState(false);
    const [machineOdoError, setMachineOdoError] = useState<string | null>(null);

  // ---- carga de maestros ----
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [mRes, dRes, ccRes, fieldsRes] = await Promise.all([
          fetch(`${apiBaseUrl}/machines`),
          fetch(`${apiBaseUrl}/drivers`),
          fetch(`${apiBaseUrl}/cost_centers`),
          fetch(`${apiBaseUrl}/fields`),
        ]);

        if (mRes.ok) setMachines(await mRes.json());
        if (dRes.ok) setDrivers(await dRes.json());
        if (ccRes.ok) setCostCenters(await ccRes.json());
        if (fieldsRes.ok) {
          const data: FieldPolygon[] = await fieldsRes.json();
          setFields(data);
        }
      } catch (e: any) {
        console.error(e);
        setLocalError("No se pudieron cargar los datos iniciales.");
      }
    };
    fetchData();
  }, []);

  useEffect(() => {
  if (!selectedMachineId) {
    setMachineOdo(null);
    setMachineOdoError(null);
    return;
  }

  const fetchOdometer = async () => {
    try {
      setMachineOdoLoading(true);
      setMachineOdoError(null);

      // 👇 Ajusta la ruta según como lo implementes en el backend
      const res = await fetch(
        `${apiBaseUrl}/machines/${selectedMachineId}/odometer`
      );

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`Error ${res.status}: ${text}`);
      }

      const data = await res.json();
      // Espero algo así del backend:
      // { total_distance_m: number, total_sessions: number, last_session_at?: string }
      setMachineOdo({
        totalDistanceM: data.total_distance_m ?? 0,
        totalSessions: data.total_sessions ?? 0,
        lastSessionAt: data.last_session_at ?? null,
      });
    } catch (e: any) {
      console.error(e);
      setMachineOdoError(
        e?.message || "No se pudo cargar el odómetro de la máquina."
      );
    } finally {
      setMachineOdoLoading(false);
    }
  };

  fetchOdometer();
}, [selectedMachineId]);


  // ---- centrar mapa en mi ubicación actual ----
  const handleCenterOnMe = () => {
    setLocalError(null);

    if (!navigator.geolocation) {
      setLocalError("Este navegador no soporta geolocalización.");
      return;
    }

    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const coords = {
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
        };
        if (mapRef) {
          mapRef.panTo(coords);
          mapRef.setZoom(19);
        }
        setLocating(false);
      },
      (err) => {
        console.error(err);
        setLocalError("No se pudo obtener tu ubicación actual.");
        setLocating(false);
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 0,
      }
    );
  };

  // autopan al último punto
  useEffect(() => {
    if (!mapRef || !lastPoint) return;
    const pos = { lat: lastPoint.lat, lng: lastPoint.lon };
    mapRef.panTo(pos);
  }, [lastPoint, mapRef]);

  // ---- helpers de búsqueda de campo ----
  const findFieldForPoint = useCallback(
    (pt: { lat: number; lon: number }): FieldPolygon | null => {
      for (const f of fields) {
        if (f.polygon.length < 3) continue;
        if (isPointInPolygon(pt, f.polygon)) {
          return f;
        }
      }
      return null;
    },
    [fields]
  );

  // ---- métricas de recorrido (distancia, tiempos, campos) ----
  const {
    totalDistanceM,
    totalTimeMs,
    avgSpeedKmh,
    currentField,
    currentSpeedKmh,
    fieldStats,
  } = useMemo(() => {
    if (points.length < 2) {
      const last = points[points.length - 1];
      const currentField =
        last && fields.length
          ? findFieldForPoint({ lat: last.lat, lon: last.lon })
          : null;
      const lastSpeedKmh =
        last && last.speed != null ? last.speed * 3.6 : 0;

      return {
        totalDistanceM: 0,
        totalTimeMs: 0,
        avgSpeedKmh: 0,
        currentField,
        currentSpeedKmh: lastSpeedKmh,
        fieldStats: [] as FieldStat[],
      };
    }

    let totalDist = 0;
    let totalTime = 0;
    let currentSpeed = 0;

    const statsMap = new Map<number, FieldStat>();

    for (let i = 1; i < points.length; i++) {
      const prev = points[i - 1];
      const curr = points[i];
      const dtMs = curr.timestamp - prev.timestamp;
      if (dtMs <= 0) continue;

      const a: DraftPoint = {
        lat: prev.lat,
        lon: prev.lon,
        timestamp: prev.timestamp,
      };
      const b: DraftPoint = {
        lat: curr.lat,
        lon: curr.lon,
        timestamp: curr.timestamp,
      };

      const dM = haversineDistanceM(a, b);
      totalDist += dM;
      totalTime += dtMs;

      // velocidad instantánea aproximada
      const dtSec = dtMs / 1000;
      if (dtSec > 0) {
        currentSpeed = (dM / dtSec) * 3.6;
      }

      // punto medio del segmento para determinar campo al que asignamos ese tramo
      const midPoint = {
        lat: (a.lat + b.lat) / 2,
        lon: (a.lon + b.lon) / 2,
      };
      const field = findFieldForPoint(midPoint);

      if (field) {
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
    }

    const last = points[points.length - 1];
    const currentField =
      last && fields.length
        ? findFieldForPoint({ lat: last.lat, lon: last.lon })
        : null;

    // si viene velocidad del GPS, la usamos
    if (last && last.speed != null) {
      currentSpeed = last.speed * 3.6;
    }

    const avgKmh =
      totalTime > 0 ? (totalDist / (totalTime / 1000)) * 3.6 : 0;

    const fieldStats: FieldStat[] = Array.from(statsMap.values()).sort(
      (a, b) => b.totalTimeMs - a.totalTimeMs
    );

    return {
      totalDistanceM: totalDist,
      totalTimeMs: totalTime,
      avgSpeedKmh: avgKmh,
      currentField,
      currentSpeedKmh: currentSpeed,
      fieldStats,
    };
  }, [points, fields, findFieldForPoint]);

  // ---- métricas de combustible teórico ----
  const fuelMetrics = useMemo(() => {
    const tank = parseFloat(tankLitersStart.replace(",", ".")) || 0;
    const cons = parseFloat(consumptionLPer100Km.replace(",", ".")) || 0;

    if (!tank || tank <= 0 || !totalDistanceM) {
      return {
        tank,
        cons,
        distanceKm: totalDistanceM / 1000,
        fuelUsed: 0,
        fuelRemaining: tank,
      };
    }

    const distanceKm = totalDistanceM / 1000;
    const fuelUsed = (distanceKm * cons) / 100;
    const fuelRemaining = tank - fuelUsed;

    return {
      tank,
      cons,
      distanceKm,
      fuelUsed,
      fuelRemaining,
    };
  }, [tankLitersStart, consumptionLPer100Km, totalDistanceM]);

  const totalTimeFmt = formatDuration(totalTimeMs);
  const totalDistanceFmt = formatKm(totalDistanceM);

  // ---- start / stop ----
  const handleStartRoute = async () => {
    setLocalError(null);
    setLocalSuccess(null);

    if (!selectedMachineId) {
      setLocalError("Debes seleccionar una máquina.");
      return;
    }

    const tank = parseFloat(tankLitersStart.replace(",", ".")) || 0;
    if (!tank || tank <= 0) {
      setLocalError(
        "Debes indicar los litros actuales del estanque para iniciar el recorrido."
      );
      return;
    }

    const cons =
      parseFloat(consumptionLPer100Km.replace(",", ".")) || 0;
    if (!cons || cons <= 0) {
      setLocalError(
        "Debes indicar el consumo teórico (L/100 km) para poder estimar el gasto de bencina."
      );
      return;
    }

    try {
      await start({
        machineId: Number(selectedMachineId),
        driverId: selectedDriverId ? Number(selectedDriverId) : null,
        costCenterId: selectedCostCenterId
          ? Number(selectedCostCenterId)
          : null,
      });
      setLocalSuccess("Recorrido iniciado. Ya estamos registrando posición.");
    } catch (e: any) {
      console.error(e);
      setLocalError(e?.message || "No se pudo iniciar el recorrido.");
    }
  };

  const handleStopRoute = async () => {
    setLocalError(null);
    setLocalSuccess(null);
    await stop();
    setLocalSuccess("Recorrido detenido. Puedes revisar las métricas del tramo.");
  };

  const combinedError = trackerError || localError;

  // ruta para el Polyline
  const routePath: google.maps.LatLngLiteral[] = points.map((p) => ({
    lat: p.lat,
    lng: p.lon,
  }));

  const currentPosition =
    lastPoint != null
      ? {
          lat: lastPoint.lat,
          lng: lastPoint.lon,
        }
      : null;

  const effectiveCenter: google.maps.LatLngLiteral =
    currentPosition ?? defaultCenter;

  if (loadError) {
    return (
      <section className="card">
        <div className="card-header">
          <div>
            <div className="card-title">Recorrido / Odómetro</div>
            <div className="card-subtitle">
              No se pudo cargar Google Maps. Revisa tu API key.
            </div>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="card">
      <div className="card-header">
        <div>
          <div className="card-title">Recorrido / Odómetro</div>
          <div className="card-subtitle">
            Inicia un recorrido desde tu posición, visualiza por qué campos
            pasas y estima el gasto teórico de combustible.
          </div>
        </div>
        {sessionId && (
          <div className="app-badge">
            Sesión activa: <span style={{ fontWeight: 700 }}>{sessionId}</span>
          </div>
        )}
      </div>

      <div className="route-layout">
        {/* LADO IZQUIERDO: configuración + métricas */}
        <div className="route-sidebar">
          <div className="fields-section">
            <div className="fields-section-title">Configuración de recorrido</div>

            <div className="form-field">
              <label className="form-label">Máquina</label>
              <select
                className="form-select"
                value={selectedMachineId}
                onChange={(e) => setSelectedMachineId(e.target.value)}
                disabled={isTracking}
              >
                <option value="">Seleccionar máquina</option>
                {machines.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                    {m.plate ? ` (${m.plate})` : ""}
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
                disabled={isTracking}
              >
                <option value="">(Opcional) Seleccionar conductor</option>
                {drivers.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                    {d.rut ? ` (${d.rut})` : ""}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-field">
              <label className="form-label">Centro de costo principal</label>
              <select
                className="form-select"
                value={selectedCostCenterId}
                onChange={(e) => setSelectedCostCenterId(e.target.value)}
                disabled={isTracking}
              >
                <option value="">(Opcional) Seleccionar centro de costo</option>
                {costCenters.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
                {selectedMachineId && (
  <div className="route-odometer-card" style={{ marginTop: 8 }}>
    <div className="session-stat__label">Odómetro máquina (histórico)</div>

    {machineOdoLoading ? (
      <div className="sessions-loading">Cargando odómetro…</div>
    ) : machineOdoError ? (
      <div className="tracker-error" style={{ marginTop: 4 }}>
        ⚠️ {machineOdoError}
      </div>
    ) : machineOdo ? (
      <div style={{ marginTop: 4, fontSize: "0.8rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <span className="tracker-meta-label">Recorrido total</span>
          <span className="tracker-meta-value">
            {formatKm(machineOdo.totalDistanceM)}
          </span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <span className="tracker-meta-label">Sesiones</span>
          <span className="tracker-meta-value">
            {machineOdo.totalSessions}
          </span>
        </div>
        {machineOdo.lastSessionAt && (
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span className="tracker-meta-label">Última vez usada</span>
            <span className="tracker-meta-value">
              {new Date(machineOdo.lastSessionAt).toLocaleString("es-CL")}
            </span>
          </div>
        )}
      </div>
    ) : (
      <div style={{ marginTop: 4, fontSize: "0.78rem", color: "#6b7280" }}>
        No hay datos de odómetro para esta máquina todavía.
      </div>
    )}
  </div>
)}

            <div className="form-field">
              <label className="form-label">Litros actuales en estanque</label>
              <input
                className="form-input"
                type="number"
                min={0}
                step="0.1"
                value={tankLitersStart}
                onChange={(e) => setTankLitersStart(e.target.value)}
                disabled={isTracking}
                placeholder="Ej: 80"
              />
            </div>

            <div className="form-field">
              <label className="form-label">
                Consumo teórico (L / 100 km)
              </label>
              <input
                className="form-input"
                type="number"
                min={0}
                step="0.1"
                value={consumptionLPer100Km}
                onChange={(e) => setConsumptionLPer100Km(e.target.value)}
                disabled={isTracking}
                placeholder="Ej: 15"
              />
            </div>

            <div className="tracker-controls" style={{ marginTop: 10 }}>
              <button
                type="button"
                className={`tracker-button ${
                  isTracking ? "stop" : "start"
                }`}
                onClick={isTracking ? handleStopRoute : handleStartRoute}
              >
                {isTracking ? "Detener recorrido" : "Iniciar recorrido"}
              </button>

              <div className="tracker-status">
                <span
                  className={
                    "status-dot " + (isTracking ? "on" : "")
                  }
                />
                <span>
                  {isTracking
                    ? "Grabando recorrido en tiempo real."
                    : "Recorrido detenido."}
                </span>
              </div>
            </div>

            {combinedError && (
              <div className="tracker-error" style={{ marginTop: 8 }}>
                ⚠️ {combinedError}
              </div>
            )}
            {localSuccess && (
              <div className="tracker-success" style={{ marginTop: 8 }}>
                ✅ {localSuccess}
              </div>
            )}
          </div>

          {/* Métricas de recorrido + combustible */}
          <div className="fields-section">
            <div className="fields-section-title">Métricas en tiempo real</div>

            <div className="route-stats-grid">
              <div className="route-stats-card">
                <div className="session-stat__label">Tiempo total</div>
                <div className="session-stat__value">{totalTimeFmt}</div>
              </div>
             <div className="route-stats-card">
                <div className="session-stat__label">Odómetro (sesión actual)</div>
                <div className="session-stat__value">
                    {totalDistanceFmt}
                </div>
                </div>

              <div className="route-stats-card">
                <div className="session-stat__label">Velocidad actual</div>
                <div className="session-stat__value">
                  {formatKmh(currentSpeedKmh)}
                </div>
              </div>
              <div className="route-stats-card">
                <div className="session-stat__label">
                  Velocidad promedio
                </div>
                <div className="session-stat__value">
                  {formatKmh(avgSpeedKmh)}
                </div>
              </div>
            </div>

            <div
              className="route-stats-card"
              style={{ marginTop: 10, background: "#eff6ff" }}
            >
              <div className="session-stat__label">
                Combustible teórico del recorrido
              </div>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
                  gap: 6,
                  marginTop: 4,
                  fontSize: "0.78rem",
                }}
              >
                <div>
                  <div className="tracker-meta-label">Litros iniciales</div>
                  <div className="tracker-meta-value">
                    {fuelMetrics.tank
                      ? formatLiters(fuelMetrics.tank)
                      : "—"}
                  </div>
                </div>
                <div>
                  <div className="tracker-meta-label">
                    Consumo teórico
                  </div>
                  <div className="tracker-meta-value">
                    {fuelMetrics.cons
                      ? `${fuelMetrics.cons.toFixed(1)} L/100km`
                      : "—"}
                  </div>
                </div>
                <div>
                  <div className="tracker-meta-label">
                    Bencina usada (teórica)
                  </div>
                  <div className="tracker-meta-value">
                    {fuelMetrics.fuelUsed
                      ? formatLiters(fuelMetrics.fuelUsed)
                      : "—"}
                  </div>
                </div>
                <div>
                  <div className="tracker-meta-label">
                    Bencina restante (teórica)
                  </div>
                  <div
                    className="tracker-meta-value"
                    style={
                      fuelMetrics.fuelRemaining < 0
                        ? { color: "#b91c1c", fontWeight: 700 }
                        : {}
                    }
                  >
                    {fuelMetrics.tank
                      ? formatLiters(fuelMetrics.fuelRemaining)
                      : "—"}
                  </div>
                </div>
              </div>
            </div>

            {currentField && (
              <div className="route-stats-card" style={{ marginTop: 10 }}>
                <div className="session-stat__label">
                  Campo actual / polígono
                </div>
                <div className="session-stat__value">
                  {currentField.name}
                </div>
                <div
                  style={{
                    fontSize: "0.76rem",
                    color: "#4b5563",
                    marginTop: 4,
                  }}
                >
                  {currentField.cost_center_name
                    ? `Centro de costo: ${currentField.cost_center_name}`
                    : "Centro de costo no asignado al campo."}
                </div>
              </div>
            )}
          </div>

          {/* Resumen por campo recorrido */}
          <div className="fields-section">
            <div className="fields-section-title">
              Resumen por campo en este recorrido
            </div>

            {fieldStats.length === 0 ? (
              <div className="fields-empty">
                Aún no hay suficientes puntos para calcular tiempos por campo.
              </div>
            ) : (
              <div className="route-fields-table-wrapper">
                <table className="route-fields-table">
                  <thead>
                    <tr>
                      <th>Campo / Polígono</th>
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
                        <td>{formatDuration(fs.totalTimeMs)}</td>
                        <td>{formatKm(fs.totalDistanceM)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        {/* LADO DERECHO: mapa */}
        <div className="route-map-wrapper">
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
            <GoogleMap
              onLoad={(map) => setMapRef(map)}
              center={effectiveCenter}
              zoom={18}
              mapContainerStyle={mapContainerStyle}
              options={{
                mapTypeId: "hybrid",
                streetViewControl: false,
                fullscreenControl: true,
                mapTypeControl: true,
              }}
            >
              {/* Campos existentes */}
              {fields.map((f) => {
                const path = f.polygon.map((p) => ({
                  lat: p.lat,
                  lng: p.lon,
                }));

                const isCurrent =
                  currentField && currentField.id === f.id;
                const baseColor = f.color || "#1d4ed8";

                return (
                  <Polygon
                    key={f.id}
                    path={path}
                    options={{
                      ...fieldPolygonBaseOptions,
                      strokeColor: baseColor,
                      fillColor: baseColor,
                      strokeWeight: isCurrent ? 3 : 2,
                      fillOpacity: isCurrent ? 0.3 : 0.14,
                    }}
                  />
                );
              })}

              {/* Recorrido actual */}
              {routePath.length > 1 && (
                <Polyline path={routePath} options={routePolylineOptions} />
              )}

              {/* Posición actual */}
              {currentPosition && (
                <Marker
                  position={currentPosition}
                  icon={{
                    path: google.maps.SymbolPath.CIRCLE,
                    scale: 6,
                    strokeColor: "#f97316",
                    strokeWeight: 2,
                    fillColor: "#ffffff",
                    fillOpacity: 1,
                  }}
                />
              )}
            </GoogleMap>
          )}
        </div>
      </div>
    </section>
  );
};

export default RoutesPage;
