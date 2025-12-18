/* eslint-disable @typescript-eslint/no-explicit-any */
import { useCallback, useEffect, useRef, useState } from "react";
import type { TrackPoint } from "@/types";
import { trackerApi } from "@/services/trackerApi";

export type TrackerMode = "machine" | "manual";

type TrackerStatus =
  | "idle"
  | "starting"
  | "tracking"
  | "stopping"
  | "error";

type StartPayload = {
  machineId: number;
  driverId?: number | null;
  costCenterId?: number | null;
  workOrderId?: number | null;
};

const GEO_OPTIONS: PositionOptions = {
  enableHighAccuracy: true,
  timeout: 10000,
  maximumAge: 0,
};

export function useTracker(mode: TrackerMode = "machine") {
  const [status, setStatus] = useState<TrackerStatus>("idle");
  const [points, setPoints] = useState<TrackPoint[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [machineId, setMachineId] = useState<number | null>(null);

  const watchIdRef = useRef<number | null>(null);
  const nextPointIdRef = useRef(1);

  // buffer simple para batching futuro
  const pendingPointsRef = useRef<TrackPoint[]>([]);

  /** Limpieza garantizada */
  useEffect(() => {
    return () => {
      if (watchIdRef.current !== null) {
        navigator.geolocation.clearWatch(watchIdRef.current);
      }
    };
  }, []);

  const start = useCallback(
    async ({ machineId, driverId, costCenterId }: StartPayload) => {
      if (status === "starting" || status === "tracking") return;

      if (!navigator.geolocation) {
        setError("Este navegador no soporta geolocalización.");
        setStatus("error");
        return;
      }

      try {
        setStatus("starting");
        setError(null);
        setPoints([]);
        pendingPointsRef.current = [];
        nextPointIdRef.current = 1;
        setMachineId(machineId);

        const session = await trackerApi.startSession({
          machine_id: machineId,
          driver_id: driverId ?? null,
          cost_center_id: costCenterId ?? null,
        });

        setSessionId(session.id);
        setStatus("tracking");

        const watchId = navigator.geolocation.watchPosition(
          (pos) => {
            const { latitude, longitude, accuracy, speed } = pos.coords;
            const ts = pos.timestamp || Date.now();

            const point: TrackPoint = {
              id: nextPointIdRef.current++,
              timestamp: ts,
              lat: latitude,
              lon: longitude,
              accuracy: accuracy ?? undefined,
              speed: speed ?? undefined,
            };

            setPoints((prev) => [...prev, point]);
            pendingPointsRef.current.push(point);

            // envío inmediato (luego se puede batch)
            void trackerApi
              .sendPoints(session.id, [
                {
                  ts: new Date(ts).toISOString(),
                  lat: point.lat,
                  lon: point.lon,
                  accuracy_m: point.accuracy ?? null,
                  speed_mps: point.speed ?? null,
                  extra: { mode },
                },
              ])
              .catch((err: any) => {
                console.error("Error enviando punto", err);
              });
          },
          (geoErr) => {
            console.error(geoErr);
            setError(geoErr.message || "Error obteniendo ubicación.");
            setStatus("error");
          },
          GEO_OPTIONS
        );

        watchIdRef.current = watchId;
      } catch (e: any) {
        console.error(e);
        setError(e?.message || "No se pudo iniciar el tracking.");
        setStatus("error");
      }
    },
    [mode, status]
  );

  const stop = useCallback(async () => {
    if (status !== "tracking") return;

    setStatus("stopping");

    if (watchIdRef.current !== null) {
      navigator.geolocation.clearWatch(watchIdRef.current);
      watchIdRef.current = null;
    }

    if (sessionId) {
      try {
        await trackerApi.closeSession(sessionId);
      } catch (err) {
        console.error("Error cerrando sesión", err);
      }
    }

    setStatus("idle");
  }, [sessionId, status]);

  const totalPoints = points.length;
  const lastPoint = points[points.length - 1];
  const firstTs = points[0]?.timestamp ?? null;
  const lastTs = points[points.length - 1]?.timestamp ?? null;
  const durationMinutes =
    firstTs && lastTs ? (lastTs - firstTs) / 1000 / 60 : null;

  return {
    // estado
    status,
    isTracking: status === "tracking",
    error,

    // datos
    points,
    sessionId,
    machineId,
    totalPoints,
    durationMinutes,
    lastPoint,

    // acciones
    start,
    stop,
  };
}
