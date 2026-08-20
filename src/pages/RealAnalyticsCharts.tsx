import AdvancedAnalytics, { type AdvancedAnalyticsSession } from "./AdvancedAnalytics";

export type RealAnalyticsSession = Omit<AdvancedAnalyticsSession, "areaHa"> & { areaHa?: number };

export default function RealAnalyticsCharts({
  sessions,
  onOpenSession,
}: {
  sessions: RealAnalyticsSession[];
  onOpenSession?: (sessionId: string) => void;
}) {
  return (
    <AdvancedAnalytics
      sessions={sessions.map((session) => ({ ...session, areaHa: session.areaHa ?? 0 }))}
      source="real"
      onOpenSession={onOpenSession}
    />
  );
}
