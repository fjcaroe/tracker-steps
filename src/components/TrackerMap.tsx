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

type TrackerMapProps = {
  /** Polígonos de los campos (ambos modos) */
  fields: FieldPolygon[];

  /** Modo LIVE: flota completa */
  activeSessions?: ActiveSession[];
  selectedSessionId?: string | null;

  /** Modo detalle de sesión (SessionsPage) */
  points?: TrackPoint[];
};

const apiBaseUrl =
  ((import.meta.env.VITE_API_BASE_URL as string | undefined) ||
    "http://localhost:8000").replace(/\/+$/, "");

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
}) => {
  const { isLoaded, loadError } = useJsApiLoader({
    id: MAPS_LOADER_ID,
    googleMapsApiKey: import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string,
    libraries: MAPS_LIBRARIES,
  });

  const [mapRef, setMapRef] = useState<google.maps.Map | null>(null);
  const [sessionPoints, setSessionPoints] = useState<
    Record<string, SessionPoint[]>
  >({});

  const hasLiveMode = !!(activeSessions && activeSessions.length > 0);

  // cargar puntos de todas las sesiones activas (solo LIVE)
  useEffect(() => {
    if (!activeSessions || !activeSessions.length) {
      // ya no limpiamos sessionPoints aquí para no gatillar el warning del linter
      return;
    }

    const sessionIds = activeSessions.map((s) => s.id);
    let cancelled = false;

    const loadAll = async () => {
      try {
        const accum: Record<string, SessionPoint[]> = {};

        await Promise.all(
          sessionIds.map(async (id) => {
            try {
             const json = await apiJson<SessionPoint[]>(`/sessions/${id}/points`);
              accum[id] = json;

            } catch (err) {
              console.error("Error cargando puntos de sesión", id, err);
            }
          })
        );

        if (!cancelled) {
          setSessionPoints(accum);
        }
      } catch (err) {
        console.error("Error cargando puntos de sesiones activas", err);
      }
    };

    loadAll();

    return () => {
      cancelled = true;
    };
  }, [activeSessions]);

  const mapCenter: google.maps.LatLngLiteral = useMemo(
    () => defaultCenter,
    []
  );

  // Ajustar bounds:
  // - LIVE sin selección: a todas las sesiones.
  // - Detalle (sin LIVE): a los puntos de la sesión.
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
    <GoogleMap
      onLoad={(map) => setMapRef(map)}
      center={mapCenter}
      zoom={14}
      mapContainerStyle={mapContainerStyle}
      options={{
        mapTypeId: "hybrid",
        streetViewControl: false,
        fullscreenControl: false,
        mapTypeControl: false,
      }}
    >
      {/* Polígonos de campos */}
      {fields.map((f) => {
        const path = f.polygon.map((p) => ({
          lat: p.lat,
          lng: p.lon,
        }));
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

      {/* MODO LIVE: recorridos de todas las sesiones activas */}
      {hasLiveMode &&
        activeSessions!.map((s) => {
          const track = sessionPoints[s.id] || [];
          if (track.length < 2) return null;

          const path = track.map((p) => ({
            lat: p.lat,
            lng: p.lon,
          }));
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

      {/* MODO DETALLE: una sola sesión usando points (SessionsPage) */}
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
  );
};

export default TrackerMap;
