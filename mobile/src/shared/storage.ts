// Puerto de almacenamiento local. Todas las operaciones son asíncronas y VERIFICADAS: `set` devuelve false si el dato no quedó guardado.
// Adaptadores: localStorage (web y piloto nativo) y memoria (pruebas). El adaptador SQLite nativo queda pendiente (ver docs/STEPS_APP_ESTADO.md).
export interface KeyValueStore {
  get(key: string): Promise<string | null>;
  /** true solo si el valor se escribió y se pudo leer de vuelta. */
  set(key: string, value: string): Promise<boolean>;
  remove(key: string): Promise<boolean>;
  keys(prefix: string): Promise<string[]>;
}

export class StorageError extends Error {
  constructor(message = 'No se pudo guardar en el teléfono. Libera espacio e inténtalo de nuevo.') { super(message); this.name = 'StorageError'; }
}

export const localKv: KeyValueStore = {
  async get(key) { try { return localStorage.getItem(key); } catch { return null; } },
  async set(key, value) { try { localStorage.setItem(key, value); return localStorage.getItem(key) === value; } catch { return false; } },
  async remove(key) { try { localStorage.removeItem(key); return true; } catch { return false; } },
  async keys(prefix) {
    try { return Array.from({ length: localStorage.length }, (_, i) => localStorage.key(i) ?? '').filter((k) => k.startsWith(prefix)); } catch { return []; }
  },
};

export function memoryKv(): KeyValueStore & { failWrites: (predicate: ((key: string) => boolean) | null) => void; dump: () => Record<string, string> } {
  const data = new Map<string, string>();
  let failing: ((key: string) => boolean) | null = null;
  return {
    async get(key) { return data.get(key) ?? null; },
    async set(key, value) { if (failing?.(key)) return false; data.set(key, value); return true; },
    async remove(key) { data.delete(key); return true; },
    async keys(prefix) { return [...data.keys()].filter((k) => k.startsWith(prefix)); },
    failWrites(predicate) { failing = predicate; },
    dump() { return Object.fromEntries(data); },
  };
}

export async function readJson<T>(kv: KeyValueStore, key: string, fallback: T): Promise<T> {
  const raw = await kv.get(key);
  if (!raw) return fallback;
  try { return JSON.parse(raw) as T; } catch { return fallback; }
}

/** Escribe JSON y lanza StorageError si no hubo persistencia real: nunca se anuncia éxito sin guardar. */
export async function writeJson(kv: KeyValueStore, key: string, value: unknown): Promise<void> {
  if (!(await kv.set(key, JSON.stringify(value)))) throw new StorageError();
}
