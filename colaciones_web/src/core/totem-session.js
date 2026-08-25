import { ERROR_KIND } from "./constants.js";
import { ApiError } from "./errors.js";
import { readCapabilities } from "./api-client.js";

/**
 * Sesión del tótem: asociación, configuración vigente y estado del servidor.
 *
 * Un `TokenStore` guarda el token del dispositivo (localStorage en la web,
 * Keychain/Keystore en móvil) y un `ConfigStore` la última configuración
 * válida, para poder arrancar sin conexión.
 */
export function createTotemSession({ api, tokenStore, configStore, clock = () => new Date() } = {}) {
  if (!api || !tokenStore || !configStore) {
    throw new TypeError("createTotemSession necesita api, tokenStore y configStore");
  }

  let capabilities = { batchSync: false, maxBatchRecords: 1, apiVersion: 1, supported: true };
  let config = null;
  let offlineConfig = false;
  let clockSkewMs = 0;

  /** Extrae el token de una URL de asociación (`#token=` o `?token=`). */
  function tokenFromUrl(href) {
    if (!href) return "";
    let url;
    try {
      url = new URL(href, "https://placeholder.invalid");
    } catch (_) {
      return "";
    }
    const hash = new URLSearchParams((url.hash || "").replace(/^#/, ""));
    return (hash.get("token") || url.searchParams.get("token") || "").trim();
  }

  return {
    tokenFromUrl,

    /** Guarda el token si la URL trae uno nuevo y devuelve el vigente. */
    async associateFromUrl(href) {
      const incoming = tokenFromUrl(href);
      if (incoming) await tokenStore.set(incoming);
      return tokenStore.get();
    },

    token() {
      return tokenStore.get();
    },

    async forget() {
      await tokenStore.clear();
      await configStore.clear();
      config = null;
    },

    get config() {
      return config;
    },

    get usingCachedConfig() {
      return offlineConfig;
    },

    get capabilities() {
      return capabilities;
    },

    /** Diferencia entre el reloj del equipo y el del servidor, en milisegundos. */
    get clockSkewMs() {
      return clockSkewMs;
    },

    /** Consulta capacidades. Un servidor antiguo sin /health no es un error. */
    async probe() {
      try {
        const health = await api.health();
        capabilities = readCapabilities(health);
        if (health?.server_time) {
          const serverTime = Date.parse(health.server_time);
          if (!Number.isNaN(serverTime)) clockSkewMs = clock().getTime() - serverTime;
        }
      } catch (error) {
        if (error instanceof ApiError && error.kind === ERROR_KIND.TERMINAL) {
          capabilities = { batchSync: false, maxBatchRecords: 1, apiVersion: 1, supported: true };
        }
      }
      return capabilities;
    },

    /**
     * Carga la configuración del tótem. Sin conexión reutiliza la última
     * guardada; con token revocado (404) borra la caché y bloquea el equipo.
     */
    async load() {
      const token = await tokenStore.get();
      if (!token) {
        config = null;
        return { status: "unpaired" };
      }
      try {
        const fresh = await api.totem(token);
        config = fresh;
        offlineConfig = false;
        await configStore.set(fresh);
        return { status: "online", config: fresh };
      } catch (error) {
        if (error instanceof ApiError && error.kind === ERROR_KIND.TERMINAL) {
          config = null;
          await configStore.clear();
          return { status: "revoked", message: error.message };
        }
        const cached = await configStore.get();
        if (cached) {
          config = cached;
          offlineConfig = true;
          return { status: "cached", config: cached };
        }
        return { status: "unavailable", message: error.message };
      }
    },
  };
}
