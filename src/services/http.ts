// src/services/http.ts
const apiBaseUrl =
  ((import.meta.env.VITE_API_BASE_URL as string | undefined) ||
    "http://localhost:8000").replace(/\/+$/, "");

const TOKEN_KEY = "tracker_token";

let authToken: string | null = null;

export class ApiError extends Error {
  status: number;
  bodyText?: string;

  constructor(message: string, status: number, bodyText?: string) {
    super(message);
    this.status = status;
    this.bodyText = bodyText;
  }
}

/** Lee token desde memoria o localStorage (fallback). */
export function getToken(): string | null {
  if (authToken) return authToken;
  try {
    const t = localStorage.getItem(TOKEN_KEY);
    authToken = t;
    return t;
  } catch {
    return authToken;
  }
}

/** Setea token en memoria + localStorage, y lo usa para Authorization header. */
export function setToken(token: string | null) {
  authToken = token;

  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // ignore storage errors (modo incógnito/privacidad)
  }
}

function buildHeaders(init?: HeadersInit, body?: BodyInit | null) {
  const h = new Headers(init || {});

  const t = authToken ?? getToken();
  if (t && !h.has("Authorization")) {
    h.set("Authorization", `Bearer ${t}`);
  }

  // Solo setear JSON si corresponde
  const isFormData = typeof FormData !== "undefined" && body instanceof FormData;
  if (!isFormData && body != null && !h.has("Content-Type")) {
    h.set("Content-Type", "application/json");
  }

  return h;
}

export async function apiFetch(path: string, init: RequestInit = {}) {
  const url = path.startsWith("http") ? path : `${apiBaseUrl}${path}`;
  const headers = buildHeaders(init.headers, init.body);

  const res = await fetch(url, { ...init, headers });

  if (res.status === 401) {
    // Centraliza expiración/autorización
    window.dispatchEvent(new Event("auth:expired"));
  }

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError(`HTTP ${res.status} en ${path}`, res.status, text);
  }

  return res;
}

export async function apiJson<T>(path: string, init: RequestInit = {}) {
  const res = await apiFetch(path, init);
  return (await res.json()) as T;
}

export function setApiAuthToken(token: string | null) {
  authToken = token;
}

