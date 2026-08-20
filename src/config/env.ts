type Env = {
  VITE_API_BASE_URL?: string;
  VITE_GOOGLE_MAPS_API_KEY?: string;
  VITE_ENV_NAME?: string;
  VITE_COSECHA_ODOO_URL?: string;
};

const raw = import.meta.env as unknown as Env;

export const env = {
  apiBaseUrl: (raw.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/+$/, ""),
  googleMapsApiKey: raw.VITE_GOOGLE_MAPS_API_KEY || "",
  envName: raw.VITE_ENV_NAME || "local",
  cosechaOdooUrl: raw.VITE_COSECHA_ODOO_URL || "https://desarrollo.stepsapp.cl/odoo?db=LAB_TAREAS#action=step_cosecha.action_step_cosecha_dashboard",
} as const;
