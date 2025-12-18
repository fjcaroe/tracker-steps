import { env } from "@/config/env";
import { apiJson, apiFetch } from "@/services/http";

export type StartSessionPayload = {
  machine_id: number;
  driver_id?: number | null;
  cost_center_id?: number | null;

  // NUEVO: amarra la sesión a un parte/orden de trabajo
  work_order_id?: number | null;

  // OPCIONAL: si quieres iniciar en un timestamp específico (demo/import)
  started_at?: string | null; // ISO string
};

export type Session = {
  id: string;
};

export type BackendPointPayload = {
  ts: string;
  lat: number;
  lon: number;
  accuracy_m?: number | null;
  speed_mps?: number | null;
  extra?: Record<string, unknown>;
};

export const trackerApi = {
  startSession(payload: StartSessionPayload) {
    return apiJson<Session>(`${env.apiBaseUrl}/sessions/start`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  sendPoints(sessionId: string, points: BackendPointPayload[]) {
    return apiJson<{ inserted: number }>(`${env.apiBaseUrl}/sessions/${sessionId}/points`, {
      method: "POST",
      body: JSON.stringify({ points }),
    });
  },

  closeSession(sessionId: string) {
    return apiFetch(`${env.apiBaseUrl}/sessions/${sessionId}/close`, {
      method: "POST",
    });
  },
};
