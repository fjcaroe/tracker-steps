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

type TrackApiItem = {
  ts: string;
  lat: number;
  lon: number;
  speed_mps?: number | null;
  n?: number;
};

type TrackApiResp = {
  items: TrackApiItem[];
  next_cursor?: string | null;
  resolution: string;
};


type TrackerMapProps = {
  /** Polígonos de los campos (ambos modos) */
  fields: FieldPolygon[];

  /** Modo LIVE: flota completa */
  activeSessions?: ActiveSession[];
  selectedSessionId?: string | null;
  liveAutoRefresh?: boolean;
  /** Modo detalle de sesión (SessionsPage) */
  points?: TrackPoint[];
  selectedPoints?: TrackPoint[];
  followSelected?: boolean;         
  showOnlySelectedTrack?: boolean;  
  onUserInteract?: () => void;    
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
  followSelected = true,
  showOnlySelectedTrack = false,
}) => {

  const { isLoaded, loadError } = useJsApiLoader({
    id: MAPS_LOADER_ID,
    googleMapsApiKey: import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string,
    libraries: MAPS_LIBRARIES,
  });
  const [selectedDayKey, setSelectedDayKey] = useState<string | null>(null);
  const [mapRef, setMapRef] = useState<google.maps.Map | null>(null);
  //   type SessionPoint = {
  //   id: number;
  //   ts: string;
  //   lat: number;
  //   lon: number;
  //   speed_mps?: number | null;
  // };

  type TrackT = {
    id: number;
    lat: number;
    lon: number;
    t: number;                 // epoch ms
    speed_mps?: number | null; // opcional, si quieres mostrar velocidad
  };


  const cacheRef = useRef<Record<string, { points: TrackT[]; fetchedAt: number }>>({});
  const [sessionPoints, setSessionPoints] = useState<Record<string, TrackT[]>>({});


  const hasLiveMode = !!(activeSessions && activeSessions.length > 0);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isRealtime, setIsRealtime] = useState(false);
  // slider en ms (timestamp objetivo)
  const [scrubTs, setScrubTs] = useState<number | null>(null);

  const SCRUB_HOURS = 24; // puedes parametrizarlo si quieres
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackRate, setPlaybackRate] = useState<number>(4); // 1x, 2x, 4x, 8x, etc.
  const playRafRef = useRef<number | null>(null);
  const lastFrameRef = useRef<number | null>(null);

  // track seleccionado (LIVE)

  const selectedTrack: TrackT[] = useMemo(() => {
    if (!hasLiveMode || !selectedSessionId) return [];

    // Preferimos SIEMPRE lo que viene desde App (rango + maxPoints)
    if (selectedPoints && selectedPoints.length) {
      return selectedPoints
        .map((p) => ({ id: p.id, lat: p.lat, lon: p.lon, t: p.timestamp }))
        .sort((a, b) => a.t - b.t);
    }

    // fallback: si por alguna razón no viene, usa sessionPoints
    const fallback = sessionPoints[selectedSessionId] || [];
    return fallback;
  }, [hasLiveMode, selectedSessionId, selectedPoints, sessionPoints]);


function normalizeTrack(resp: TrackApiResp): TrackT[] {
  return resp.items.map((p, idx) => {
    const t = new Date(p.ts).getTime();
    return {
      id: t + idx,
      lat: p.lat,
      lon: p.lon,
      t,
      speed_mps: p.speed_mps ?? null,
    };
  }).sort((a, b) => a.t - b.t);
}

function iso(ms: number) { return new Date(ms).toISOString(); }

useEffect(() => {
  setIsPlaying(false);
}, [selectedDayKey]);

const onScrubChange = (v: number) => {
  setIsPlaying(false);
  setScrubTs(v);
};


const scrubPoints = useMemo(() => {
  if (!selectedTrack.length) return [];
  if (!selectedDayKey) return selectedTrack;
  return selectedTrack.filter((p) => dayKeyFromT(p.t) === selectedDayKey);
}, [selectedTrack, selectedDayKey]);



  // --- Día seleccionado para scrub (key YYYY-MM-DD en America/Santiago)


  // Key estable tipo 2026-01-22 (sv-SE entrega YYYY-MM-DD)
  function dayKeyFromT(t: number) {
    return new Date(t).toLocaleDateString("sv-SE", { timeZone: "America/Santiago" });
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


const LIVE_WINDOW_MIN = 30;

type CacheEntry = {
  points: TrackT[];
  fetchedAt: number;
  cursor?: string | null;
};

const cacheRef2 = useRef<Record<string, CacheEntry>>({});

async function loadSessionPoints(id: string, mode: "historical" | "live") {
  const now = Date.now();

  const from =
    mode === "historical"
      ? now - SCRUB_HOURS * 3600_000
      : now - LIVE_WINDOW_MIN * 60_000;

  const resolution = mode === "historical" ? "10s" : "raw";
  const limit = mode === "historical" ? 20000 : 5000;

  const cached = cacheRef2.current[id];
  const cursor = mode === "live" ? cached?.cursor : null;

  const qs = new URLSearchParams({
    from: iso(from),
    to: iso(now),
    resolution,
    limit: String(limit),
  });
  if (cursor) qs.set("cursor", cursor);

  const resp = await apiJson<TrackApiResp>(`/sessions/${id}/track?${qs.toString()}`);
  const fresh = normalizeTrack(resp);

  let merged: TrackT[];
  if (mode === "live" && cursor && cached?.points?.length) {
    // append incremental
    merged = [...cached.points, ...fresh];
    merged.sort((a, b) => a.t - b.t);
  } else {
    merged = fresh;
  }

  // recortes memoria (tus límites)
  const pts = mode === "live" ? merged.slice(-LIVE_LIMIT) : merged.slice(-FULL_LIMIT);

  cacheRef2.current[id] = { points: pts, fetchedAt: Date.now(), cursor: resp.next_cursor ?? cursor ?? null };
  setSessionPoints((prev) => ({ ...prev, [id]: pts }));
}


  type DayOption = { key: string; label: string; minTs: number; maxTs: number; count: number };

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


useEffect(() => {
  if (!dayOptions.length) {
    if (selectedDayKey !== null) setSelectedDayKey(null);
    return;
  }
  if (!selectedDayKey) setSelectedDayKey(dayOptions[0].key);
}, [dayOptions, selectedDayKey]);

  const scrubMinMax = useMemo(() => {
  if (!scrubPoints.length) return null;
  return { min: scrubPoints[0].t, max: scrubPoints[scrubPoints.length - 1].t };
}, [scrubPoints]);  

 function findNearestPointByTs(points: TrackT[], targetTs: number): TrackT | null {
  if (!points.length) return null;

  let lo = 0;
  let hi = points.length - 1;

  while (lo < hi) {
    const mid = Math.floor((lo + hi) / 2);
    if (points[mid].t < targetTs) lo = mid + 1;
    else hi = mid;
  }

  const idx = lo;
  const prevIdx = Math.max(0, idx - 1);

  const t1 = points[prevIdx].t;
  const t2 = points[idx].t;

  return Math.abs(t1 - targetTs) <= Math.abs(t2 - targetTs)
    ? points[prevIdx]
    : points[idx];
}

const scrubPoint = useMemo(() => {
  if (!isFullscreen) return null;
  if (!selectedSessionId) return null;
  if (!scrubPoints.length) return null;
  if (scrubTs == null) return scrubPoints[scrubPoints.length - 1];
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
  if (!isFullscreen) { setIsPlaying(false); return; }
  if (!isPlaying) return;
  if (!scrubMinMax) return;

  lastFrameRef.current = null;

  const tick = (now: number) => {
    if (!isPlaying) return;
    if (!scrubMinMax) return;

    if (lastFrameRef.current == null) lastFrameRef.current = now;
    const dt = now - lastFrameRef.current; // ms reales
    lastFrameRef.current = now;

    setScrubTs((prev) => {
      const cur = prev ?? scrubMinMax.min;
      const next = cur + dt * playbackRate; // 1x = tiempo real, 4x = 4 veces más rápido

      if (next >= scrubMinMax.max) {
        // llega al final
        setIsPlaying(false);
        return scrubMinMax.max;
      }
      return next;
    });

    playRafRef.current = requestAnimationFrame(tick);
  };

  playRafRef.current = requestAnimationFrame(tick);

  return () => {
    if (playRafRef.current) cancelAnimationFrame(playRafRef.current);
    playRafRef.current = null;
  };
}, [isPlaying, playbackRate, isFullscreen, scrubMinMax]);

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
    if (!selectedDayKey) return;
    const opt = dayOptions.find((d) => d.key === selectedDayKey);
    if (!opt) return;
    setScrubTs(opt.maxTs);
  }, [selectedDayKey, dayOptions]);

  // cargar puntos de todas las sesiones activas (solo LIVE)



useEffect(() => {
  if (!activeSessions?.length) return;


  const ids = activeSessions.map((s) => s.id);

 const TAIL_POINTS_FLEET = 80;

const fetchFleetTail = async (id: string) => {
  const now = Date.now();
  const from = now - 10 * 60_000; // últimos 10 min

  const qs = new URLSearchParams({
    from: iso(from),
    to: iso(now),
    resolution: "raw",
    limit: "800",
  });

  const resp = await apiJson<TrackApiResp>(`/sessions/${id}/track?${qs.toString()}`);
  const pts = normalizeTrack(resp).slice(-TAIL_POINTS_FLEET);

  cacheRef2.current[id] = { points: pts, fetchedAt: Date.now(), cursor: null };
  setSessionPoints((prev) => ({ ...prev, [id]: pts }));
};

  // para no saturar, limita concurrencia si hay muchas sesiones (simple: Promise.all está OK si son pocas)
  Promise.all(ids.map(fetchFleetTail));

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

const lastFollowTsRef = useRef<number | null>(null);
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
    if (!mapRef || !isLoaded || !hasLiveMode) return;
    if (!selectedSessionId) return;
    if (!followSelected) return;

    // Preferimos los puntos filtrados del seleccionado (vienen desde App)
    const track =
    (selectedPoints && selectedPoints.length > 0)
      ? selectedPoints
      : (sessionPoints[selectedSessionId] || []);


    if (!track.length) return;

    const last = track[track.length - 1];

    // TrackPoint: timestamp number / SessionPoint: ts string
    const lastTs =
      typeof (last as any).timestamp === "number"
        ? (last as any).timestamp
        : new Date((last as any).ts).getTime();

    // Solo seguir si llegó un punto nuevo
    if (lastFollowTsRef.current != null && lastTs <= lastFollowTsRef.current) {
      return;
    }
    lastFollowTsRef.current = lastTs;

    mapRef.panTo({ lat: (last as any).lat, lng: (last as any).lon });
    mapRef.setZoom(18);
  }, [mapRef, isLoaded, hasLiveMode, selectedSessionId, followSelected, selectedPoints, sessionPoints]);

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
      {isFullscreen && (
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
)}
      {/* Scrubber SOLO en LIVE + sesión seleccionada + fullscreen */}
      {isFullscreen && hasLiveMode && selectedSessionId && scrubMinMax && (
        <div className="tracker-map-scrubber">
          <div className="tracker-map-scrubber__label">
            Tiempo:{" "}


            <strong>
              {new Date(scrubTs ?? scrubMinMax.max).toLocaleString("es-CL", {
                hour12: false,
              })}
            </strong>
          </div>
   

          <input
            type="range"
            className="tracker-map-scrubber__range"
            min={scrubMinMax.min}
            max={scrubMinMax.max}
            step={1000} // 1 segundo; puedes subir a 5000 si quieres más fluido
            value={scrubTs ?? scrubMinMax.max}
            onChange={(e) => onScrubChange(Number(e.target.value))}

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
        {/* LIVE polylines */}
{hasLiveMode &&
  activeSessions!.map((s) => {
    const isSelected = selectedSessionId === s.id;

    // Si está activo "solo seleccionado", oculta los demás
    if (showOnlySelectedTrack && selectedSessionId && !isSelected) return null;

    // Para el seleccionado: usa selectedTrack (prioriza selectedPoints)
    // Para el resto: usa sessionPoints
    const base = isSelected ? selectedTrack : (sessionPoints[s.id] || []);

  // Si el seleccionado viene desde App (selectedPoints), ya viene acotado.
  // Solo decimamos si es gigantesco (fallbacks / históricos).
  const SELECTED_CAP = 15000;
  const track =
    isSelected
      ? (base.length > SELECTED_CAP ? decimate(base, SELECTED_CAP) : base)
      : base;

    if (track.length < 2) return null;

    const path = track.map((p) => ({ lat: p.lat, lng: p.lon }));
    const dimOthers = !!selectedSessionId && !isSelected;
          console.log("poly", s.id, {
            isSelected,
            selectedTrack: selectedTrack.length,
            sessionPts: (sessionPoints[s.id] || []).length,
          });
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
       {/* LIVE markers por sesión */}
{hasLiveMode &&
  activeSessions!.map((s) => {
    const isSelected = selectedSessionId === s.id;

    if (showOnlySelectedTrack && selectedSessionId && !isSelected) return null;

    const track = isSelected ? selectedTrack : (sessionPoints[s.id] || []);
    if (!track.length) return null;

    const last = track[track.length - 1];
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
{isFullscreen && hasLiveMode && selectedSessionId && scrubMinMax && (
  <div className="tracker-map-playback">
    <button
      type="button"
      className="tracker-map-playback__btn"
      onClick={() => setIsPlaying((v) => !v)}
      disabled={!scrubPoints.length}
      title="Reproducir/Pausar"
    >
      {isPlaying ? "Pausar" : "Play"}
    </button>

    <select
      className="tracker-map-playback__select"
      value={playbackRate}
      onChange={(e) => setPlaybackRate(Number(e.target.value))}
      title="Velocidad"
    >
      <option value={0.5}>0.5x</option>
      <option value={1}>1x</option>
      <option value={2}>2x</option>
      <option value={4}>4x</option>
      <option value={8}>8x</option>
      <option value={16}>16x</option>
    </select>

    <button
      type="button"
      className="tracker-map-playback__btn"
      onClick={() => {
        setIsPlaying(false);
        setScrubTs(scrubMinMax.min);
      }}
      title="Reiniciar"
    >
      Reiniciar
    </button>
  </div>
)}

      {/* Debajo del mapa: selector de días (NO tapa el mapa) */}
{isFullscreen && hasLiveMode && selectedSessionId && dayOptions.length > 0 && (
  <div className="tracker-map-days-panel">
    <div className="tracker-map-days-panel__row">
      <div className="tracker-map-days-panel__label">Día</div>

      <select
        className="tracker-map-days-panel__select"
        value={selectedDayKey ?? ""}
        onChange={(e) => {
          const v = e.target.value;
          setSelectedDayKey(v || null);
        }}
      >
        {dayOptions.map((d) => (
          <option key={d.key} value={d.key}>
            {d.label} ({d.count})
          </option>
        ))}
      </select>

      <div className="tracker-map-days-panel__meta">
        {scrubMinMax ? (
          <>
            {new Date(scrubMinMax.min).toLocaleString("es-CL", { hour12: false })}{" "}
            —{" "}
            {new Date(scrubMinMax.max).toLocaleString("es-CL", { hour12: false })}
          </>
        ) : null}
      </div>
    </div>
  </div>
)}

    </div>
  );

};

export default TrackerMap;
