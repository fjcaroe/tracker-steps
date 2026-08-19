// src/types.ts
export type TrackPoint = {
  id: number;
  timestamp: number;
  lat: number;
  lon: number;
  accuracy?: number | null;
  speed_mps?: number | null;
  extra?: Record<string, unknown>;

};

export type ApiLivePoint = {
  id: number;
  ts: string; 
  lat: number;
  lon: number;
  speed_mps?: number | null;
  accuracy_m?: number | null;
  extra?: Record<string, unknown>;
};
export type SessionId = string;

export type SessionSummary = {
  id: SessionId;
  machine_id: number;
  machine_name?: string | null;
  driver_name?: string | null;
  cost_center_name?: string | null;
  started_at: string;
  ended_at?: string | null;
  status: "open" | "closed";
  points_count: number;
};

export type Machine = {
  id: number;
  name: string;
  plate?: string | null;
  tank_capacity_liters?: number | null;
  fuel_consumption_lph?: number | null;
  fuel_consumption_lpkm?: number | null;
};
