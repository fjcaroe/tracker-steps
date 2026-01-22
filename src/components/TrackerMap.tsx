// src/components/TrackerMap.tsx
import { useEffect, useState, useMemo, type CSSProperties } from "react";
import {
  GoogleMap,
  Polyline,
  Polygon,
  Marker,
  useJsApiLoader,
} from "@react-google-maps/api";
import { MAPS_LIBRARIES, MAPS_LOADER_ID } from "../mapsConfig";
import type { TrackPoint } from "../types";
import { apiJson } from "../services/http";
import { useRef } from "react";


type FieldPolygon = {
  id: number;
  name: string;
  color?: string | null;
  polygon: { lat: number; lon: number }[];
};

type ActiveSession = {
  id: string;
  machine_id: number;
  machine_name?: string | null;
  driver_name?: string | null;
  cost_center_name?: string | null;
  started_at: string;
  points_count: number;
};

type SessionPoint = {
  id: number;
  ts: string;
  lat: number;
  lon: number;
  speed_mps?: number | null;
};
type LivePoint = { lat: number; lon: number; ts?: string };

type TrackerMapProps = {
  /** Polígonos de los campos (ambos modos) */
  fields: FieldPolygon[];

  /** Modo LIVE: flota completa */
  activeSessions?: ActiveSession[];
  selectedSessionId?: string | null;

  /** Modo detalle de sesión (SessionsPage) */
  points?: TrackPoint[];
  selectedPoints?: LivePoint[];
};


const mapContainerStyle: CSSProperties = {
  width: "100%",
  height: "60vh",
  minHeight: "360px",
  borderRadius: "14px",
  overflow: "hidden",
};

const defaultCenter: google.maps.LatLngLiteral = {
  lat: -33.45,
  lng: -70.65,
};

const TrackerMap: React.FC<TrackerMapProps> = ({
  fields,
  activeSessions,
  selectedSessionId,
  points,
  selectedPoints,
}) => {
  const { isLoaded, loadError } = useJsApiLoader({
    id: MAPS_LOADER_ID,
    googleMapsApiKey: import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string,
    libraries: MAPS_LIBRARIES,
  });
  const [selectedDayKey, setSelectedDayKey] = useState<string | null>(null);
  const [mapRef, setMapRef] = useState<google.maps.Map | null>(null);
  type SessionPointT = SessionPoint & { t: number }; // t = timestamp en ms

  const cacheRef = useRef<Record<string, { points: SessionPointT[]; fetchedAt: number }>>({});
  const [sessionPoints, setSessionPoints] = useState<Record<string, SessionPointT[]>>({});

  const hasLiveMode = !!(activeSessions && activeSessions.length > 0);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isRealtime, setIsRealtime] = useState(false);
  // slider en ms (timestamp objetivo)
  const [scrubTs, setScrubTs] = useState<number | null>(null);

  const SCRUB_HOURS = 24; // puedes parametrizarlo si quieres

  // track seleccionado (LIVE)
  const selectedTrack = useMemo(() => {
    if (!hasLiveMode || !selectedSessionId) return [];
    return sessionPoints[selectedSessionId] ?? [];
  }, [hasLiveMode, selectedSessionId, sessionPoints]);


  const scrubPoints = useMemo(() => {
    if (!selectedTrack.length) return [];
    if (!selectedDayKey) return selectedTrack;
    return selectedTrack.filter((p) => dayKeyFromT(p.t) === selectedDayKey);
  }, [selectedTrack, selectedDayKey]);

const polylineTracks = useMemo(() => {
  const MAX_SELECTED = 2000; // ajusta: 1500-4000 según fluidez

  // Para cada sesión: si es la seleccionada, decima fuerte; si no, deja tal cual (ya es tail de flota)
  const out: Record<string, SessionPointT[]> = {};
  for (const [id, pts] of Object.entries(sessionPoints)) {
    if (!pts?.length) continue;
    out[id] = id === selectedSessionId ? decimate(pts, MAX_SELECTED) : pts;
  }
  return out;
}, [sessionPoints, selectedSessionId]);

  // --- Día seleccionado para scrub (key YYYY-MM-DD en America/Santiago)


  // Key estable tipo 2026-01-22 (sv-SE entrega YYYY-MM-DD)
  function dayKeyFromT(t: number) {
    return new Date(t).toLocaleDateString("sv-SE", { timeZone: "America/Santiago" });
  }
function normalize(json: SessionPoint[]): SessionPointT[] {
  return json
    .map((p) => ({ ...p, t: new Date(p.ts).getTime() }))
    .sort((a, b) => a.t - b.t);
}
const forceReloadRef = useRef<((id: string) => void) | null>(null);

const FULL_LIMIT = 40000;   // histórico: máximo de puntos que aceptas guardar
const LIVE_LIMIT = 2000;    // en vivo: máximo puntos en memoria para dibujar

function decimate<T>(arr: T[], maxPoints: number): T[] {
  if (arr.length <= maxPoints) return arr;
  const step = Math.ceil(arr.length / maxPoints);
  const out: T[] = [];
  for (let i = 0; i < arr.length; i += step) out.push(arr[i]);
  // asegura que el último punto siempre esté
  if (out[out.length - 1] !== arr[arr.length - 1]) out.push(arr[arr.length - 1]);
  return out;
}


async function loadSessionPoints(id: string, mode: "historical" | "live") {
  const json = await apiJson<SessionPoint[]>(`/sessions/${id}/points`);
  let pts = normalize(json);

  if (mode === "live") {
    pts = pts.slice(-LIVE_LIMIT);
  } else {
    pts = pts.slice(-FULL_LIMIT);
  }

  cacheRef.current[id] = { points: pts, fetchedAt: Date.now() };
  setSessionPoints((prev) => ({ ...prev, [id]: pts }));
}


  type DayOption = {
    key: string;        // YYYY-MM-DD
    label: string;      // "mié 22 ene" (ej)
    minTs: number;      // ms
    maxTs: number;      // ms
    count: number;
  };

  // Construye días disponibles desde el track seleccionado
  const dayOptions: DayOption[] = useMemo(() => {
    if (!selectedTrack.length) return [];
    const acc = new Map<string, DayOption>();

    for (const p of selectedTrack) {
      const key = dayKeyFromT(p.t);
      const existing = acc.get(key);

      if (!existing) {
        const label = new Intl.DateTimeFormat("es-CL", {
          weekday: "short",
          day: "2-digit",
          month: "short",
          timeZone: "America/Santiago",
        }).format(new Date(p.t));

        acc.set(key, { key, label, minTs: p.t, maxTs: p.t, count: 1 });
      } else {
        existing.minTs = Math.min(existing.minTs, p.t);
        existing.maxTs = Math.max(existing.maxTs, p.t);
        existing.count += 1;
      }
    }

    return Array.from(acc.values()).sort((a, b) => (a.key < b.key ? 1 : -1));
  }, [selectedTrack]);

  const scrubMinMax = useMemo(() => {
    if (!scrubPoints.length) return null;
      const min = scrubPoints[0].t;
      const max = scrubPoints[scrubPoints.length - 1].t;
    return { min, max };
  }, [scrubPoints]);

  function findNearestPointByTs(points: SessionPointT[], targetTs: number): SessionPointT | null {
  if (!points.length) return null;

  let lo = 0;
  let hi = points.length - 1;

  const getTs = (i: number) => points[i].t;

  while (lo < hi) {
    const mid = Math.floor((lo + hi) / 2);
    if (getTs(mid) < targetTs) lo = mid + 1;
    else hi = mid;
  }

  const idx = lo;
  const prevIdx = Math.max(0, idx - 1);

  const t1 = getTs(prevIdx);
  const t2 = getTs(idx);

  return Math.abs(t1 - targetTs) <= Math.abs(t2 - targetTs)
    ? points[prevIdx]
    : points[idx];
}


  const scrubPoint = useMemo(() => {
    if (!isFullscreen) return null;              // solo en fullscreen
    if (!selectedSessionId) return null;         // requiere selección
    if (!scrubPoints.length) return null;        // requiere datos
    if (scrubTs == null) return scrubPoints[scrubPoints.length - 1]; // default: último

    return findNearestPointByTs(scrubPoints, scrubTs);
  }, [isFullscreen, selectedSessionId, scrubPoints, scrubTs]);

  useEffect(() => {
  forceReloadRef.current = (id: string) => {
    loadSessionPoints(id, isRealtime ? "live" : "historical").catch((e) =>
      console.error("Error recargando sesión", e)
    );
  };
}, [isRealtime]);


useEffect(() => {
  if (!selectedSessionId) return;

  let cancelled = false;

  const ensureHistoricalOnce = async () => {
    // si está en histórico, solo carga si no existe cache
    if (!isRealtime) {
      if (cacheRef.current[selectedSessionId]?.points?.length) return;
      await loadSessionPoints(selectedSessionId, "historical");
    }
  };

  ensureHistoricalOnce().catch((e) => console.error(e));

  // si está en vivo, hace polling
  let interval: number | null = null;
  if (isRealtime) {
    const poll = async () => {
      if (cancelled) return;
      await loadSessionPoints(selectedSessionId, "live");
    };
    poll().catch((e) => console.error(e));
    interval = window.setInterval(() => poll().catch(console.error), 15_000);
  }

  return () => {
    cancelled = true;
    if (interval) window.clearInterval(interval);
  };
}, [selectedSessionId, isRealtime]);


useEffect(() => {
  if (!dayOptions.length) {
    if (selectedDayKey !== null) setSelectedDayKey(null);
    return;
  }
  if (!selectedDayKey) setSelectedDayKey(dayOptions[0].key);
}, [dayOptions, selectedDayKey]);

  useEffect(() => {
    if (!selectedDayKey) return;
    const opt = dayOptions.find((d) => d.key === selectedDayKey);
    if (!opt) return;
    setScrubTs(opt.maxTs);
  }, [selectedDayKey, dayOptions]);

  // cargar puntos de todas las sesiones activas (solo LIVE)

const TAIL_POINTS_FLEET = 80;
const TTL_FLEET_MS = 180_000;

useEffect(() => {
  if (!activeSessions?.length) return;

  let cancelled = false;
  const now = Date.now();
  const ids = activeSessions.map((s) => s.id);

  const fetchFleetTail = async (id: string) => {
    try {
      const cached = cacheRef.current[id];
      if (cached && now - cached.fetchedAt < TTL_FLEET_MS) return;

      const json = await apiJson<SessionPoint[]>(`/sessions/${id}/points`);
      const pts = normalize(json).slice(-TAIL_POINTS_FLEET);

      cacheRef.current[id] = { points: pts, fetchedAt: Date.now() };

      if (!cancelled) {
        setSessionPoints((prev) => ({ ...prev, [id]: pts }));
      }
    } catch (e) {
      console.error("Error cargando cola de flota", id, e);
    }
  };

  // para no saturar, limita concurrencia si hay muchas sesiones (simple: Promise.all está OK si son pocas)
  Promise.all(ids.map(fetchFleetTail));

  return () => {
    cancelled = true;
  };
}, [activeSessions]);


  const mapCenter: google.maps.LatLngLiteral = useMemo(
    () => defaultCenter,
    []
  );

  useEffect(() => {
    const onFsChange = () => {
      const fsEl = document.fullscreenElement;
      setIsFullscreen(!!fsEl);
    };
    document.addEventListener("fullscreenchange", onFsChange);
    return () => document.removeEventListener("fullscreenchange", onFsChange);
  }, []);

  const toggleFullscreen = async () => {
    const el = containerRef.current;
    if (!el) return;

    try {
      if (!document.fullscreenElement) {
        await el.requestFullscreen();
      } else {
        await document.exitFullscreen();
      }
    } catch (e) {
      console.error("No se pudo activar pantalla completa", e);
    }
  };


const panRafRef = useRef<number | null>(null);

useEffect(() => {
  if (!mapRef || !isLoaded || !scrubPoint) return;

  if (panRafRef.current) cancelAnimationFrame(panRafRef.current);
  panRafRef.current = requestAnimationFrame(() => {
    mapRef.panTo({ lat: scrubPoint.lat, lng: scrubPoint.lon });
  });

  return () => {
    if (panRafRef.current) cancelAnimationFrame(panRafRef.current);
  };
}, [mapRef, isLoaded, scrubPoint?.id]); // ojo: depende por id, no por objeto completo



  // al entrar a fullscreen, inicializa el scrubber al último punto disponible
  useEffect(() => {
    if (!isFullscreen) return;
    if (!scrubMinMax) return;
    setScrubTs(scrubMinMax.max);
  }, [isFullscreen, scrubMinMax]);

  useEffect(() => {
    if (!mapRef || !isLoaded) return;

    // Modo LIVE, sin sesión seleccionada: ajustar a toda la flota
    if (hasLiveMode && !selectedSessionId) {
      const allTracks = Object.values(sessionPoints);
      const allPoints = allTracks.flat();
      if (!allPoints.length) return;

      const bounds = new google.maps.LatLngBounds();
      allPoints.forEach((p) =>
        bounds.extend({ lat: p.lat, lng: p.lon })
      );
      mapRef.fitBounds(bounds);
      return;
    }

    // Modo detalle (SessionsPage): sin LIVE, con puntos
    if (!hasLiveMode && points && points.length > 0) {
      const bounds = new google.maps.LatLngBounds();
      points.forEach((p) =>
        bounds.extend({ lat: p.lat, lng: p.lon })
      );
      mapRef.fitBounds(bounds);
    }
  }, [mapRef, isLoaded, hasLiveMode, selectedSessionId, sessionPoints, points]);

  // Centrar cuando selecciono una sesión en LIVE
  useEffect(() => {
    if (!mapRef || !isLoaded || !selectedSessionId || !hasLiveMode) return;

    const track = sessionPoints[selectedSessionId];
    if (!track || !track.length) return;

    const last = track[track.length - 1];
    const center = { lat: last.lat, lng: last.lon };
    mapRef.panTo(center);
    mapRef.setZoom(18);
  }, [mapRef, isLoaded, selectedSessionId, hasLiveMode, sessionPoints]);


    useEffect(() => {
    if (!mapRef || !isLoaded) return;
    if (!selectedPoints || selectedPoints.length === 0) return;

    // en tu caso usamos el primero
    const sp = selectedPoints[0];
    mapRef.panTo({ lat: sp.lat, lng: sp.lon });
    mapRef.setZoom(19);
  }, [mapRef, isLoaded, selectedPoints]);

  
  if (loadError) {
    return (
      <div className="fields-map-loading">
        No se pudo cargar Google Maps en el seguimiento en vivo.
      </div>
    );
  }

  if (!isLoaded) {
    return <div className="fields-map-loading">Cargando mapa…</div>;
  }

  return (
    <div
      ref={containerRef}
      className={`tracker-map-shell ${isFullscreen ? "tracker-map-shell--fullscreen" : ""}`}
      style={{ position: "relative" }}
    >
      {/* Botón fullscreen */}
      <button
        type="button"
        className="tracker-map-fullscreen-btn"
        onClick={toggleFullscreen}
        title={isFullscreen ? "Salir de pantalla completa" : "Pantalla completa"}
      >
        {isFullscreen ? "Salir" : "Pantalla completa"}
      </button>
    <div className="tracker-map-scrubber__toprow">
  <button
    type="button"
    className={"tracker-map-scrubber__modebtn" + (isRealtime ? " is-active" : "")}
    onClick={() => setIsRealtime((v) => !v)}
    title="Cuando está activo, refresca puntos periódicamente"
  >
    {isRealtime ? "En vivo: ON" : "En vivo: OFF"}
  </button>

  <button
    type="button"
    className="tracker-map-scrubber__modebtn"
    onClick={() => {
      // fuerza una recarga manual
      if (selectedSessionId) forceReloadRef.current?.(selectedSessionId);
    }}
  >
    Actualizar
  </button>
</div>

      {/* Scrubber SOLO en LIVE + sesión seleccionada + fullscreen */}
      {hasLiveMode && selectedSessionId && scrubMinMax && (
        <div className="tracker-map-scrubber">
          <div className="tracker-map-scrubber__label">
            Tiempo:{" "}


            <strong>
              {new Date(scrubTs ?? scrubMinMax.max).toLocaleString("es-CL", {
                hour12: false,
              })}
            </strong>
          </div>
          {dayOptions.length > 0 && (
            <div className="tracker-map-scrubber__days">
              {dayOptions.slice(0, 7).map((d) => ( // limita a 7 si quieres; o quita el slice
                <button
                  key={d.key}
                  type="button"
                  className={
                    "tracker-map-scrubber__daybtn" +
                    (selectedDayKey === d.key ? " is-active" : "")
                  }
                  onClick={() => setSelectedDayKey(d.key)}
                  title={`${d.key} · ${d.count} puntos`}
                >
                  {d.label}
                </button>
              ))}
            </div>
          )}

          <input
            type="range"
            className="tracker-map-scrubber__range"
            min={scrubMinMax.min}
            max={scrubMinMax.max}
            step={1000} // 1 segundo; puedes subir a 5000 si quieres más fluido
            value={scrubTs ?? scrubMinMax.max}
            onChange={(e) => setScrubTs(Number(e.target.value))}
          />

          <div className="tracker-map-scrubber__hint">
            Ventana: últimas {SCRUB_HOURS} horas
          </div>
        </div>
      )}

      <GoogleMap
        onLoad={(map) => setMapRef(map)}
        center={mapCenter}
        zoom={14}
        mapContainerStyle={mapContainerStyle}
        options={{
          mapTypeId: "hybrid",
          streetViewControl: false,
          fullscreenControl: false, // usamos el nuestro
          mapTypeControl: false,
        }}
      >
        {/* Polígonos */}
        {fields.map((f) => {
          const path = f.polygon.map((p) => ({ lat: p.lat, lng: p.lon }));
          const baseColor = f.color || "#22c55e";
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

        {/* LIVE polylines */}
        {hasLiveMode &&
          activeSessions!.map((s) => {
            const track = polylineTracks[s.id] || [];
            if (track.length < 2) return null;

            const path = track.map((p) => ({ lat: p.lat, lng: p.lon }));

            const isSelected = selectedSessionId === s.id;
            const dimOthers = !!selectedSessionId && !isSelected;

            return (
              <Polyline
                key={`line-${s.id}`}
                path={path}
                options={{
                  strokeColor: isSelected ? "#f97316" : "#38bdf8",
                  strokeOpacity: dimOthers ? 0.25 : 0.9,
                  strokeWeight: isSelected ? 5 : 3,
                }}
              />
            );
          })}

        {/* LIVE markers por sesión */}
        {hasLiveMode &&
          activeSessions!.map((s) => {
            const track = sessionPoints[s.id] || [];
            if (!track.length) return null;

            const last = track[track.length - 1];
            const isSelected = selectedSessionId === s.id;
            const dimOthers = !!selectedSessionId && !isSelected;

            return (
              <Marker
                key={`marker-${s.id}`}
                position={{ lat: last.lat, lng: last.lon }}
                icon={{
                  path: google.maps.SymbolPath.CIRCLE,
                  scale: isSelected ? 8 : 6,
                  strokeColor: isSelected ? "#f97316" : "#0f172a",
                  strokeWeight: isSelected ? 3 : 2,
                  fillColor: isSelected ? "#ffffff" : "#e5e7eb",
                  fillOpacity: dimOthers ? 0.6 : 1,
                }}
              />
            );
          })}

        {/* Marker del scrubber (solo fullscreen + sesión seleccionada) */}
        {hasLiveMode && selectedSessionId && isFullscreen && scrubPoint && (
          <Marker
            key="scrub-marker"
            position={{ lat: scrubPoint.lat, lng: scrubPoint.lon }}
            icon={{
              path: google.maps.SymbolPath.CIRCLE,
              scale: 9,
              strokeColor: "#f97316",
              strokeWeight: 3,
              fillColor: "#ffffff",
              fillOpacity: 1,
            }}
          />
        )}

        {/* DETALLE SessionsPage */}
        {!hasLiveMode && points && points.length > 1 && (
          <Polyline
            path={points.map((p) => ({ lat: p.lat, lng: p.lon }))}
            options={{
              strokeColor: "#f97316",
              strokeOpacity: 0.95,
              strokeWeight: 4,
            }}
          />
        )}

        {!hasLiveMode && points && points.length > 0 && (
          <Marker
            position={{
              lat: points[points.length - 1].lat,
              lng: points[points.length - 1].lon,
            }}
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
  );

};

export default TrackerMap;
