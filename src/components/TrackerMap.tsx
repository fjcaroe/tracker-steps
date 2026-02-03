// src/components/TrackerMap.tsx
import { useEffect, useState, useMemo, useRef, Fragment } from "react";
import { GoogleMap, Polyline, Polygon, Marker, useJsApiLoader } from "@react-google-maps/api";
import { MAPS_LIBRARIES, MAPS_LOADER_ID } from "../mapsConfig";
import type { TrackPoint } from "../types";
import { apiJson } from "../services/http";
import "./TrackerMap.scss";

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
  fields: FieldPolygon[];

  activeSessions?: ActiveSession[];
  selectedSessionId?: string | null;

  // detalle/histórico (SessionsPage)
  points?: TrackPoint[];

  // LIVE: puntos seleccionados ya filtrados desde App (rango + limit)
  selectedPoints?: TrackPoint[];

  followSelected?: boolean;
  showOnlySelectedTrack?: boolean;

  // ✅ para mobile/UX: cuando el usuario toca/arrastra el mapa, deja de seguir
  onUserInteract?: () => void;
};

const defaultCenter: google.maps.LatLngLiteral = { lat: -33.45, lng: -70.65 };

function useMediaQuery(query: string) {
  const [matches, setMatches] = useState(() => {
    if (typeof window === "undefined" || !window.matchMedia) return false;
    return window.matchMedia(query).matches;
  });

  useEffect(() => {
    if (!window.matchMedia) return;
    const mql = window.matchMedia(query);
    const onChange = () => setMatches(mql.matches);
    onChange();
    // Safari old
    if ((mql as any).addEventListener) (mql as any).addEventListener("change", onChange);
    else (mql as any).addListener(onChange);
    return () => {
      if ((mql as any).removeEventListener) (mql as any).removeEventListener("change", onChange);
      else (mql as any).removeListener(onChange);
    };
  }, [query]);

  return matches;
}

type TrackT = {
  id: number;
  lat: number;
  lon: number;
  t: number; // epoch ms
  speed_mps?: number | null;
};

function parseTs(ts: string) {
  const cleaned = (!ts.includes("T") && ts.includes(" ")) ? ts.replace(" ", "T") : ts;
  const hasTZ = /Z$|[+-]\d{2}:\d{2}$/.test(cleaned);
  // Si no tiene TZ, lo tratamos como hora local (Chile) => evita corrimientos raros de día
  return hasTZ ? Date.parse(cleaned) : new Date(cleaned).getTime();
}


function normalizeTrack(resp: TrackApiResp): TrackT[] {
  return resp.items
    .map((p, idx) => {
      const t = parseTs(p.ts);
      return { id: t * 100 + idx, lat: p.lat, lon: p.lon, t, speed_mps: p.speed_mps ?? null };
    })
    .filter((p) => Number.isFinite(p.t))
    .sort((a, b) => a.t - b.t);
}

function iso(ms: number) {
  return new Date(ms).toISOString();
}

function dayKeyFromT(t: number) {
  return new Date(t).toLocaleDateString("sv-SE", { timeZone: "America/Santiago" });
}

function decimate<T>(arr: T[], maxPoints: number): T[] {
  if (arr.length <= maxPoints) return arr;
  const step = Math.ceil(arr.length / maxPoints);
  const out: T[] = [];
  for (let i = 0; i < arr.length; i += step) out.push(arr[i]);
  if (out[out.length - 1] !== arr[arr.length - 1]) out.push(arr[arr.length - 1]);
  return out;
}



function interpByTime(points: TrackT[], targetTs: number): TrackT | null {
  if (!points.length) return null;
  if (targetTs <= points[0].t) return points[0];
  const last = points[points.length - 1];
  if (targetTs >= last.t) return last;

  // lower_bound por t
  let lo = 0, hi = points.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (points[mid].t < targetTs) lo = mid + 1;
    else hi = mid;
  }
  const b = points[lo];
  const a = points[Math.max(0, lo - 1)];
  const span = b.t - a.t;
  if (span <= 0) return b;

  const f = (targetTs - a.t) / span;
  return {
    id: a.id,
    t: targetTs,
    lat: a.lat + (b.lat - a.lat) * f,
    lon: a.lon + (b.lon - a.lon) * f,
    speed_mps: a.speed_mps ?? null,
  };
}

function interpByIndex(points: TrackT[], pos: number): TrackT | null {
  if (!points.length) return null;
  const max = points.length - 1;
  if (pos <= 0) return points[0];
  if (pos >= max) return points[max];

  const i = Math.floor(pos);
  const f = pos - i;
  const a = points[i];
  const b = points[i + 1];

  return {
    id: a.id,
    t: a.t + (b.t - a.t) * f,
    lat: a.lat + (b.lat - a.lat) * f,
    lon: a.lon + (b.lon - a.lon) * f,
    speed_mps: a.speed_mps ?? null,
  };
}


const SCRUB_HOURS = 24;
const LIVE_WINDOW_MIN = 30;
const FULL_LIMIT = 120000;
const LIVE_LIMIT = 2000;



const TrackerMap: React.FC<TrackerMapProps> = ({
  fields,
  activeSessions,
  selectedSessionId,
  points,
  selectedPoints,
  followSelected = true,
  showOnlySelectedTrack = false,
  onUserInteract,
}) => {
  const { isLoaded, loadError } = useJsApiLoader({
    id: MAPS_LOADER_ID,
    googleMapsApiKey: import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string,
    libraries: MAPS_LIBRARIES,
  });

  const isMobile = useMediaQuery("(max-width: 768px)");
  const hasLiveMode = !!(activeSessions && activeSessions.length > 0);

  const [mapRef, setMapRef] = useState<google.maps.Map | null>(null);
  const PLAYED_CAP = isMobile ? 15000 : 35000;
  // fullscreen nativo + fallback pseudo
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [isNativeFullscreen, setIsNativeFullscreen] = useState(false);
  const [isPseudoFullscreen, setIsPseudoFullscreen] = useState(false);
  const isFs = isNativeFullscreen || isPseudoFullscreen;

  // scrub/playback
  const [selectedDayKey, setSelectedDayKey] = useState<string | null>(null);
  const [scrubTs, setScrubTs] = useState<number | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackRate, setPlaybackRate] = useState<number>(4);
  const playRafRef = useRef<number | null>(null);
  const lastFrameRef = useRef<number | null>(null);
  const playPosRef = useRef<number>(0); // índice float dentro de scrubPoints
  const [playedIdx, setPlayedIdx] = useState<number>(0);
  const UI_TICK_MS = 80;
  const RENDER_CAP = isMobile ? 25000 : 60000;
  
  // modo carga puntos /track dentro del fullscreen (histórico vs live)
  const [isRealtime, setIsRealtime] = useState(false);
  type CacheEntry = { points: TrackT[]; fetchedAt: number; cursor?: string | null };
  const cacheRef = useRef<Record<string, CacheEntry>>({});
  const [sessionPoints, setSessionPoints] = useState<Record<string, TrackT[]>>({});
  const lastUiRef = useRef<number>(0);
  // ---- track seleccionado (LIVE): preferimos lo que viene desde App (selectedPoints) ----
  const selectedTrack: TrackT[] = useMemo(() => {
    if (!hasLiveMode || !selectedSessionId) return [];
    
    if (selectedPoints && selectedPoints.length) {
      const mapped = selectedPoints
        .map((p) => ({ id: p.id, lat: p.lat, lon: p.lon, t: p.timestamp }))
        .sort((a, b) => a.t - b.t);
      // para render: evita reventar si llega gigante
      return mapped.length > RENDER_CAP ? decimate(mapped, RENDER_CAP) : mapped;
    }

    const fallback = sessionPoints[selectedSessionId] || [];
    return fallback;
  }, [hasLiveMode, selectedSessionId, selectedPoints, sessionPoints]);

  // ---- día options (para el selector) ----
  type DayOption = { key: string; label: string; minTs: number; maxTs: number; count: number };
  const [renderNonce, setRenderNonce] = useState(0);

const usingSelectedPoints = !!(selectedPoints?.length);

// firma del filtro SOLO cuando estás usando selectedPoints (o sea, viene del App)
const filterSig = useMemo(() => {
  if (!usingSelectedPoints) return "server";
  if (!selectedTrack.length) return "empty";
  const first = selectedTrack[0].t;
  const last = selectedTrack[selectedTrack.length - 1].t;
  return `${first}-${last}-${selectedTrack.length}`;
}, [usingSelectedPoints, selectedTrack]);

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
  // cambia sesión o cambia el filtro => resetea todo
  setIsPlaying(false);
  playPosRef.current = 0;
  setPlayedIdx(0);
  lastFollowTsRef.current = null;

  setScrubTs(null);
  setSelectedDayKey(null);

  // limpia cache de la sesión seleccionada (evita mezcla/solape)
  if (selectedSessionId) {
    delete cacheRef.current[selectedSessionId];
    setSessionPoints((prev) => {
      const copy = { ...prev };
      delete copy[selectedSessionId];
      return copy;
    });
  }

  // fuerza remount de overlays (evita overlays pegados)
  setRenderNonce((n) => n + 1);
}, [selectedSessionId, filterSig]);

  useEffect(() => {
    if (!dayOptions.length) {
      if (selectedDayKey !== null) setSelectedDayKey(null);
      return;
    }
    if (!selectedDayKey) setSelectedDayKey(dayOptions[0].key);
  }, [dayOptions, selectedDayKey]);

  // ---- scrub points (filtrados por día si aplica) ----
  const scrubPoints = useMemo(() => {
    if (!selectedTrack.length) return [];
    if (!selectedDayKey) return selectedTrack;
    return selectedTrack.filter((p) => dayKeyFromT(p.t) === selectedDayKey);
  }, [selectedTrack, selectedDayKey]);

  const scrubPointsRaw = useMemo(() => {
  if (!selectedTrack.length) return [];
  if (!selectedDayKey) return selectedTrack;
  return selectedTrack.filter((p) => dayKeyFromT(p.t) === selectedDayKey);
}, [selectedTrack, selectedDayKey]);

const scrubPointsRender = useMemo(() => {

  const CAP = PLAYED_CAP;
  return scrubPointsRaw.length > CAP ? decimate(scrubPointsRaw, CAP) : scrubPointsRaw;
}, [scrubPointsRaw]);


const scrubMinMax = useMemo(() => {
  if (!scrubPointsRaw.length) return null;
  return { min: scrubPointsRaw[0].t, max: scrubPointsRaw[scrubPointsRaw.length - 1].t };
}, [scrubPointsRaw]);

  // al entrar a fullscreen, inicializa scrub al último punto
  useEffect(() => {
    if (!isFs) return;
    if (!scrubMinMax) return;
    setScrubTs(scrubMinMax.max);
  }, [isFs, scrubMinMax]);

  // cambia día => pausa
  useEffect(() => {
    setIsPlaying(false);
  }, [selectedDayKey]);

  // si cambia selectedDayKey => mover scrub al final del día
  useEffect(() => {
    if (!selectedDayKey) return;
    const opt = dayOptions.find((d) => d.key === selectedDayKey);
    if (!opt) return;
    setScrubTs(opt.maxTs);
  }, [selectedDayKey, dayOptions]);

  const onScrubChange = (v: number) => {
    setIsPlaying(false);
    setScrubTs(v);
    if (scrubPoints.length) {
      playPosRef.current = idxFromTs(scrubPoints, v);
      setPlayedIdx(Math.floor(playPosRef.current));
    }
  };

const scrubPoint = useMemo<TrackT | null>(() => {
  if (!isFs) return null;
  if (!selectedSessionId) return null;
  if (!scrubPointsRaw.length) return null;

  if (isPlaying) return interpByIndex(scrubPointsRaw, playPosRef.current);

  const t = scrubTs ?? scrubPointsRaw[scrubPointsRaw.length - 1].t;
  return interpByTime(scrubPointsRaw, t);
}, [isFs, selectedSessionId, scrubPointsRaw, scrubTs, isPlaying]);



  useEffect(() => {
  const onVis = () => {
    lastFrameRef.current = null;
  };
  document.addEventListener("visibilitychange", onVis);
  return () => document.removeEventListener("visibilitychange", onVis);
}, []);

useEffect(() => {
  if (!isFs) { setIsPlaying(false); return; }
  if (!isPlaying) return;
  if (!scrubMinMax || scrubPointsRaw.length < 2) return;

  lastFrameRef.current = null;

  const BASE_PTS_PER_SEC = 8;
  const maxPos = scrubPointsRaw.length - 1;

  const tick = (now: number) => {
    if (!isPlaying) return;

    if (lastFrameRef.current == null) lastFrameRef.current = now;
    let dt = now - lastFrameRef.current;
    lastFrameRef.current = now;
    if (dt > 200) dt = 200;

    const delta = (dt / 1000) * BASE_PTS_PER_SEC * playbackRate;
    playPosRef.current = Math.min(maxPos, playPosRef.current + delta);

    const idx = Math.floor(playPosRef.current);

    if (now - lastUiRef.current >= UI_TICK_MS) {
      lastUiRef.current = now;
      setPlayedIdx(idx);
      setScrubTs(scrubPointsRaw[idx].t);
    }

    if (idx >= maxPos) {
      setIsPlaying(false);
      setPlayedIdx(maxPos);
      setScrubTs(scrubMinMax.max);
      return;
    }

    playRafRef.current = requestAnimationFrame(tick);
  };

  playRafRef.current = requestAnimationFrame(tick);

  return () => {
    if (playRafRef.current) cancelAnimationFrame(playRafRef.current);
    playRafRef.current = null;
  };
}, [isPlaying, playbackRate, isFs, scrubMinMax, scrubPointsRaw]);


const API_TRACK_MAX_LIMIT = 20000;

async function loadSessionPoints(id: string, mode: "historical" | "live") {
  const now = Date.now();
  const from =
    mode === "historical"
      ? now - SCRUB_HOURS * 3600_000
      : now - LIVE_WINDOW_MIN * 60_000;

  // histórico: mejor decimado por backend si quieres (10s/1m); si quieres raw, déjalo raw.
  const resolution: "raw" | "10s" | "1m" = mode === "historical" ? "raw" : "raw";
  const pageLimit = mode === "historical" ? API_TRACK_MAX_LIMIT : 5000;

  const cached = cacheRef.current[id];
  let cursor = mode === "live" ? (cached?.cursor ?? null) : null;

  // acumulador
  let acc: TrackT[] =
    mode === "live" && cached?.points?.length ? [...cached.points] : [];

  const cap = mode === "live" ? LIVE_LIMIT : FULL_LIMIT;

  // loop de páginas hasta cap o fin
  while (true) {
    const qs = new URLSearchParams({
      from: iso(from),
      to: iso(now),
      resolution,
      limit: String(pageLimit), // ✅ <= 20000
    });
    if (cursor) qs.set("cursor", cursor);

    const resp = await apiJson<TrackApiResp>(`/sessions/${id}/track?${qs.toString()}`);
    const fresh = normalizeTrack(resp);

    if (fresh.length) {
      acc = [...acc, ...fresh].sort((a, b) => a.t - b.t);
      if (acc.length > cap) acc = acc.slice(-cap);
    }

    const next = resp.next_cursor ?? null;

    // corta si no hay más páginas o no llegó nada (evita loop infinito)
    if (!next || fresh.length === 0) {
      cursor = next;
      break;
    }

    cursor = next;

    // si ya juntamos suficiente para render, corta
    if (acc.length >= cap) break;
  }

  cacheRef.current[id] = {
    points: acc,
    fetchedAt: Date.now(),
    cursor, // para live se puede reusar
  };

  setSessionPoints((prev) => ({ ...prev, [id]: acc }));
}



function idxFromTs(points: TrackT[], ts: number) {
  if (!points.length) return 0;
  let lo = 0, hi = points.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (points[mid].t < ts) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}


  useEffect(() => {
    if (!isFs) return;
    if (!selectedSessionId) return;
    if (!hasLiveMode) return;

    let cancelled = false;

    const ensureHistorical = async () => {
      if (cancelled) return;
      if (!isRealtime) {
        // histórico solo 1 vez si no existe
        if (cacheRef.current[selectedSessionId]?.points?.length) return;
        await loadSessionPoints(selectedSessionId, "historical");
      }
    };

    ensureHistorical().catch(console.error);

    let interval: number | null = null;
    if (isRealtime) {
      const poll = async () => {
        if (cancelled) return;
        await loadSessionPoints(selectedSessionId, "live");
      };
      poll().catch(console.error);
      interval = window.setInterval(() => poll().catch(console.error), 15_000);
    }

    return () => {
      cancelled = true;
      if (interval) window.clearInterval(interval);
    };
  }, [isFs, selectedSessionId, hasLiveMode, isRealtime]);

  // ---- carga tail de flota (live mode sin seleccionar) ----
  useEffect(() => {
    if (!activeSessions?.length) return;
    const ids = activeSessions.map((s) => s.id);
    const TAIL_POINTS_FLEET = 80;

    const fetchFleetTail = async (id: string) => {
      const now = Date.now();
      const from = now - 10 * 60_000;

      const qs = new URLSearchParams({
        from: iso(from),
        to: iso(now),
        resolution: "raw",
        limit: "800",
      });

      const resp = await apiJson<TrackApiResp>(`/sessions/${id}/track?${qs.toString()}`);
      const pts = normalizeTrack(resp).slice(-TAIL_POINTS_FLEET);

      cacheRef.current[id] = { points: pts, fetchedAt: Date.now(), cursor: null };
      setSessionPoints((prev) => ({ ...prev, [id]: pts }));
    };

    Promise.all(ids.map(fetchFleetTail)).catch(console.error);
  }, [activeSessions]);

  // ---- fullscreen handling ----
  useEffect(() => {
    const onFsChange = () => {
      setIsNativeFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener("fullscreenchange", onFsChange);
    return () => document.removeEventListener("fullscreenchange", onFsChange);
  }, []);

  useEffect(() => {
    // lock scroll en fullscreen/pseudo fullscreen
    if (!isFs) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [isFs]);

  // fuerza resize del mapa cuando cambia el contenedor (clave en mobile/fullscreen)
  useEffect(() => {
    if (!mapRef) return;
    const id = window.setTimeout(() => {
      try {
        google.maps.event.trigger(mapRef, "resize");
      } catch {
        /* noop */
      }
    }, 80);
    return () => window.clearTimeout(id);
  }, [mapRef, isFs]);

  const toggleFullscreen = async () => {
    const el = containerRef.current;
    if (!el) return;

    // si estamos en pseudo, salimos
    if (isPseudoFullscreen) {
      setIsPseudoFullscreen(false);
      return;
    }

    // si hay native fullscreen, salimos
    if (document.fullscreenElement) {
      try {
        await document.exitFullscreen();
      } catch (e) {
        console.error("No se pudo salir de pantalla completa", e);
      }
      return;
    }

    // intentar native fullscreen; si falla (iOS Safari), usar pseudo
    try {
      const req = (el as any).requestFullscreen;
      if (typeof req === "function") {
        // navigationUI hide no siempre existe, pero si está, mejor
        await (el as any).requestFullscreen?.({ navigationUI: "hide" });
      } else {
        setIsPseudoFullscreen(true);
      }
    } catch (e) {
      setIsPseudoFullscreen(true);
    }
  };

  // ---- centrado / bounds ----
  const mapCenter: google.maps.LatLngLiteral = useMemo(() => defaultCenter, []);

  const lastFollowTsRef = useRef<number | null>(null);

  useEffect(() => {
    if (!mapRef || !isLoaded) return;

    if (hasLiveMode && !selectedSessionId) {
      const allPoints = Object.values(sessionPoints).flat();
      if (!allPoints.length) return;
      const bounds = new google.maps.LatLngBounds();
      allPoints.forEach((p) => bounds.extend({ lat: p.lat, lng: p.lon }));
      mapRef.fitBounds(bounds);
      return;
    }

    if (!hasLiveMode && points && points.length > 0) {
      const bounds = new google.maps.LatLngBounds();
      points.forEach((p) => bounds.extend({ lat: p.lat, lng: p.lon }));
      mapRef.fitBounds(bounds);
    }
  }, [mapRef, isLoaded, hasLiveMode, selectedSessionId, sessionPoints, points]);

useEffect(() => {
  if (!mapRef || !isLoaded || !hasLiveMode) return;
  if (!selectedSessionId) return;
  if (!followSelected) return;
  if (isFs) return; // en fullscreen lo controlas con scrub

  if (!selectedTrack.length) return;
  const last = selectedTrack[selectedTrack.length - 1];

  if (lastFollowTsRef.current != null && last.t <= lastFollowTsRef.current) return;
  lastFollowTsRef.current = last.t;

  mapRef.panTo({ lat: last.lat, lng: last.lon });

  const z = mapRef.getZoom() ?? 0;
  if (z < 16) mapRef.setZoom(18);
}, [mapRef, isLoaded, hasLiveMode, selectedSessionId, followSelected, isFs, selectedTrack]);

const panRafRef = useRef<number | null>(null)
  // pan al scrubPoint en fullscreen
useEffect(() => {
  if (!isFs) return;
  if (!mapRef || !isLoaded || !scrubPoint) return;

  if (panRafRef.current) cancelAnimationFrame(panRafRef.current);

  panRafRef.current = requestAnimationFrame(() => {
    mapRef.panTo({ lat: scrubPoint.lat, lng: scrubPoint.lon });

    const z = mapRef.getZoom() ?? 0;
    if (z < 16) mapRef.setZoom(18);
  });

  return () => {
    if (panRafRef.current) cancelAnimationFrame(panRafRef.current);
  };
}, [isFs, mapRef, isLoaded, scrubPoint?.t]); // 👈 clave




  // ---- paths helpers ----
const selectedPathFull = useMemo(
  () => scrubPointsRender.map((p) => ({ lat: p.lat, lng: p.lon })),
  [scrubPointsRender]
);

const playedPointsRender = useMemo(() => {
      if (!isFs) return [];
  if (!scrubPointsRaw.length) return [];

  const idx = Math.min(Math.max(0, playedIdx), scrubPointsRaw.length - 1);
  let slice = scrubPointsRaw.slice(0, idx + 1);

  const cur = interpByIndex(scrubPointsRaw, playPosRef.current);
  if (cur) slice = [...slice, cur];

  return slice.length > PLAYED_CAP ? decimate(slice, PLAYED_CAP) : slice;
}, [isFs, scrubPointsRaw, playedIdx]);

const selectedPathPlayed = useMemo(
  () => playedPointsRender.map((p) => ({ lat: p.lat, lng: p.lon })),
  [playedPointsRender]
);

 
  if (loadError) {
    return <div className="fields-map-loading">No se pudo cargar Google Maps.</div>;
  }
  if (!isLoaded) {
    return <div className="fields-map-loading">Cargando mapa…</div>;
  }


  return (
    <div
      ref={containerRef}
      className={[
        "tracker-map-shell",
        isFs ? "tracker-map-shell--fullscreen" : "",
        isMobile ? "tracker-map-shell--mobile" : "",
      ].join(" ")}
      style={{ position: "relative" }}
    >
      {/* fullscreen button */}
      <button
        type="button"
        className="tracker-map-fullscreen-btn"
        onClick={toggleFullscreen}
        title={isFs ? "Salir de pantalla completa" : "Pantalla completa"}
      >
        {isFs ? "Salir" : "Pantalla completa"}
      </button>

      <GoogleMap
        onLoad={(map) => setMapRef(map)}
        center={mapCenter}
        zoom={14}
        mapContainerClassName={isFs ? "tracker-map-canvas tracker-map-canvas--fullscreen" : "tracker-map-canvas"}
        options={{
          mapTypeId: "hybrid",
          streetViewControl: false,
          fullscreenControl: false,
          mapTypeControl: false,
          clickableIcons: false,
        }}
        onDragStart={() => onUserInteract?.()}
        onClick={() => onUserInteract?.()}
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
            const isSelected = selectedSessionId === s.id;

            if (showOnlySelectedTrack && selectedSessionId && !isSelected) return null;

            const base = isSelected ? selectedTrack : (sessionPoints[s.id] || []);
            const track = isSelected ? (base.length > 15000 ? decimate(base, 15000) : base) : base;

            if (track.length < 2) return null;

            const dimOthers = !!selectedSessionId && !isSelected;

            // ✅ en fullscreen + seleccionado: dibuja “completo tenue” + “reproducido”
          if (isFs && isSelected && selectedPathFull.length > 1) {
  return (
    <Fragment key={`sel-${s.id}-${renderNonce}`}>
      <Polyline
        path={selectedPathFull}
        options={{ strokeColor: "#94a3b8", strokeOpacity: 0.45, strokeWeight: 4 }}
      />
      {selectedPathPlayed.length > 1 && (
        <Polyline
          path={selectedPathPlayed}
          options={{ strokeColor: "#f97316", strokeOpacity: 0.95, strokeWeight: 6 }}
        />
      )}
    </Fragment>
  );
}


            const path = track.map((p) => ({ lat: p.lat, lng: p.lon }));
            return (
              <Polyline
                key={`line-${s.id}-${renderNonce}`}
                path={path}
                options={{
                  strokeColor: isSelected ? "#f97316" : "#38bdf8",
                  strokeOpacity: dimOthers ? 0.25 : 0.9,
                  strokeWeight: isSelected ? 5 : 3,
                }}
              />
            );
          })}

        {/* LIVE markers */}
        {hasLiveMode &&
          activeSessions!.map((s) => {
            const isSelected = selectedSessionId === s.id;
            if (showOnlySelectedTrack && selectedSessionId && !isSelected) return null;

           if (isFs && isSelected) {
              return null; // ya estás mostrando el scrub-marker naranja
            }

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
            position={{ lat: points[points.length - 1].lat, lng: points[points.length - 1].lon }}
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

        {isFs && selectedSessionId && scrubPoint && (
  <Marker
    key={`scrub-marker-${selectedSessionId}`}
    position={{ lat: scrubPoint.lat, lng: scrubPoint.lon }}
    icon={{
      path: google.maps.SymbolPath.CIRCLE,
      scale: 9,
      strokeColor: "#f97316",
      strokeWeight: 3,
      fillColor: "#ffffff",
      fillOpacity: 1,
    }}
    zIndex={999}
  />
)}

      </GoogleMap>

      {/* HUD bottom (solo fullscreen + live + selected) */}
      {isFs && hasLiveMode && selectedSessionId && scrubMinMax && (
        <div className="tracker-map-hud">
          <div className="tracker-map-hud__panel">
            <div className="tracker-map-hud__row">
              <button
                type="button"
                className={`hud-btn ${isPlaying ? "is-active" : ""}`}
                onClick={() => setIsPlaying((v) => !v)}
                disabled={!scrubPoints.length}
              >
                {isPlaying ? "Pausar" : "Play"}
              </button>

              <button
                type="button"
                className={`hud-btn ${isRealtime ? "is-active" : ""}`}
                onClick={() => setIsRealtime((v) => !v)}
                title="Si está ON, refresca puntos periódicamente"
              >
                {isRealtime ? "En vivo: ON" : "En vivo: OFF"}
              </button>

              <button
                type="button"
                className="hud-btn"
                onClick={() => selectedSessionId && loadSessionPoints(selectedSessionId, isRealtime ? "live" : "historical").catch(console.error)}
              >
                Actualizar
              </button>

              <div className="hud-spacer" />

              <select
                className="hud-select"
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
                className="hud-btn"
                onClick={() => {
                  setIsPlaying(false);
                  setScrubTs(scrubMinMax.min);
                }}
                title="Reiniciar"
              >
                ⟲
              </button>
            </div>

            <div className="tracker-map-hud__time">
              <span>Tiempo:</span>{" "}
              <strong>
                {new Date(scrubTs ?? scrubMinMax.max).toLocaleString("es-CL", { hour12: false })}
              </strong>
            </div>

            <input
              type="range"
              className="hud-range"
              min={scrubMinMax.min}
              max={scrubMinMax.max}
              step={1000}
              value={scrubTs ?? scrubMinMax.max}
              onChange={(e) => onScrubChange(Number(e.target.value))}
            />

            {dayOptions.length > 0 && (
              <div className="tracker-map-hud__row tracker-map-hud__row--day">
                <div className="hud-label">Día</div>
                <select
                  className="hud-select hud-select--grow"
                  value={selectedDayKey ?? ""}
                  onChange={(e) => setSelectedDayKey(e.target.value || null)}
                >
                  {dayOptions.map((d) => (
                    <option key={d.key} value={d.key}>
                      {d.label} ({d.count})
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div className="tracker-map-hud__hint">Ventana: últimas {SCRUB_HOURS} horas</div>
          </div>
        </div>
      )}
    </div>
  );

  
};

export default TrackerMap;
