type Env = {
  VITE_API_BASE_URL?: string;
  VITE_GOOGLE_MAPS_API_KEY?: string;
  VITE_ENV_NAME?: string;
};

const raw = import.meta.env as unknown as Env;

export const env = {
  apiBaseUrl: (raw.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/+$/, ""),
  googleMapsApiKey: raw.VITE_GOOGLE_MAPS_API_KEY || "",
  envName: raw.VITE_ENV_NAME || "local",
} as const;
