import { useMemo } from "react";
import type { DemoSession, DemoVehicle } from "../demo/scenario";
import AdvancedAnalytics, { type AdvancedAnalyticsSession } from "./AdvancedAnalytics";

type Props = {
  vehicles: DemoVehicle[];
  sessions: DemoSession[];
  regionId: string;
  regionName: string;
  onOpenSession?: (sessionId: string) => void;
};

export default function AnalyticsCharts({ sessions, onOpenSession }: Props) {
  const normalized = useMemo<AdvancedAnalyticsSession[]>(() => sessions.map((session) => ({
    id: session.id,
    machineId: session.machine,
    machine: session.machine,
    driver: session.driver,
    location: session.field,
    labor: session.labor,
    startedAt: session.startedAtIso,
    status: session.status === "completed" ? "closed" : "open",
    hours: session.durationHours,
    distanceKm: session.distanceKm,
    areaHa: session.coveredHa,
    fuelLiters: session.fuelLiters,
    avgSpeedKmh: session.avgSpeedKmh,
    points: Math.max(1, Math.round(session.durationHours * 60)),
    stale: false,
  })), [sessions]);

  return <AdvancedAnalytics sessions={normalized} source="demo" onOpenSession={onOpenSession} />;
}
