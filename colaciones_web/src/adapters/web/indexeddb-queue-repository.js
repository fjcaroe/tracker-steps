/**
 * `QueueRepository` de la PWA sobre IndexedDB.
 *
 * IndexedDB soporta mucho más volumen que `localStorage` y sobrevive a un
 * cierre forzado del navegador. Si el entorno no la expone —modo privado de
 * algunos navegadores, WebView reducido— se degrada a `localStorage` sin
 * perder el contrato.
 */
const DB_NAME = "steps_colaciones";
const DB_VERSION = 1;
const STORE = "queue";

function openDatabase(indexedDB) {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: "clientUuid" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
    request.onblocked = () => reject(new Error("IndexedDB bloqueada por otra pestaña."));
  });
}

function promisify(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export function createLocalStorageQueueRepository({ storage = globalThis.localStorage, key } = {}) {
  const storageKey = key || "steps_colaciones_queue_v2";
  function read() {
    try {
      const parsed = JSON.parse(storage.getItem(storageKey) || "[]");
      return Array.isArray(parsed) ? parsed : [];
    } catch (_) {
      return [];
    }
  }
  function write(records) {
    storage.setItem(storageKey, JSON.stringify(records));
  }
  return {
    kind: "localStorage",
    async list() {
      return read();
    },
    async put(record) {
      const records = read().filter((item) => item.clientUuid !== record.clientUuid);
      records.push(record);
      write(records);
    },
    async remove(clientUuid) {
      write(read().filter((item) => item.clientUuid !== clientUuid));
    },
    async clear() {
      storage.removeItem(storageKey);
    },
  };
}

export async function createQueueRepository({
  indexedDB = globalThis.indexedDB,
  storage = globalThis.localStorage,
} = {}) {
  if (!indexedDB) return createLocalStorageQueueRepository({ storage });
  let db;
  try {
    db = await openDatabase(indexedDB);
  } catch (_) {
    return createLocalStorageQueueRepository({ storage });
  }

  function transaction(mode) {
    return db.transaction(STORE, mode).objectStore(STORE);
  }

  return {
    kind: "indexedDB",
    async list() {
      return (await promisify(transaction("readonly").getAll())) || [];
    },
    async put(record) {
      await promisify(transaction("readwrite").put(record));
    },
    async remove(clientUuid) {
      await promisify(transaction("readwrite").delete(clientUuid));
    },
    async clear() {
      await promisify(transaction("readwrite").clear());
    },
  };
}
