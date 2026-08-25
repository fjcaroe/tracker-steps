/**
 * `TokenStore`, `ConfigStore` y origen de la cola antigua para la PWA.
 *
 * En la web el token vive en `localStorage`: el navegador no ofrece un almacén
 * cifrado y el token ya es revocable desde Odoo. La App móvil implementa el
 * mismo contrato sobre Keychain/Keystore.
 */
const TOKEN_KEY = "steps_colaciones_totem_token";
const CONFIG_KEY = "steps_colaciones_config";
const LEGACY_QUEUE_PREFIX = "steps_colaciones_queue_";
const LEGACY_CONFIG_PREFIX = "steps_colaciones_config_";

export function createWebTokenStore({ storage = globalThis.localStorage } = {}) {
  return {
    async get() {
      return storage.getItem(TOKEN_KEY) || "";
    },
    async set(token) {
      storage.setItem(TOKEN_KEY, String(token || "").trim());
    },
    async clear() {
      storage.removeItem(TOKEN_KEY);
    },
  };
}

export function createWebConfigStore({ storage = globalThis.localStorage } = {}) {
  return {
    async get() {
      try {
        return JSON.parse(storage.getItem(CONFIG_KEY) || "null");
      } catch (_) {
        return null;
      }
    },
    async set(config) {
      storage.setItem(CONFIG_KEY, JSON.stringify(config));
    },
    async clear() {
      storage.removeItem(CONFIG_KEY);
    },
  };
}

/**
 * Origen de la cola de la versión 1, que usaba una clave por token.
 * Se leen todas las claves con el prefijo para no depender del token vigente.
 */
export function createLegacyQueueSource({ storage = globalThis.localStorage } = {}) {
  function legacyKeys() {
    const keys = [];
    for (let index = 0; index < storage.length; index += 1) {
      const key = storage.key(index);
      if (key && key.startsWith(LEGACY_QUEUE_PREFIX)) keys.push(key);
    }
    return keys;
  }
  return {
    async read() {
      const records = [];
      for (const key of legacyKeys()) {
        try {
          const parsed = JSON.parse(storage.getItem(key) || "[]");
          if (Array.isArray(parsed)) records.push(...parsed);
        } catch (_) {
          // Una clave corrupta no debe impedir migrar el resto.
        }
      }
      return records;
    },
    async clear() {
      for (const key of legacyKeys()) storage.removeItem(key);
      for (let index = storage.length - 1; index >= 0; index -= 1) {
        const key = storage.key(index);
        if (key && key.startsWith(LEGACY_CONFIG_PREFIX)) storage.removeItem(key);
      }
    },
  };
}
