/**
 * `NetworkMonitor` de la PWA.
 *
 * `navigator.onLine` solo indica que hay una interfaz activa: un tótem
 * conectado a un Wi-Fi sin salida a internet lo informa como "en línea". Por
 * eso el estado real se confirma con una consulta liviana al propio servidor.
 */
export function createWebNetworkMonitor({
  probe,
  target = globalThis,
  navigatorImpl = globalThis.navigator,
  intervalMs = 30_000,
  setIntervalImpl = globalThis.setInterval,
} = {}) {
  const listeners = new Set();
  let reachable = null;
  let checking = null;

  function state() {
    return {
      // Sin interfaz de red no hace falta comprobar nada.
      online: Boolean(navigatorImpl?.onLine ?? true),
      reachable,
    };
  }

  function emit() {
    const snapshot = state();
    for (const listener of listeners) listener(snapshot);
  }

  async function check() {
    if (checking) return checking;
    if (!(navigatorImpl?.onLine ?? true)) {
      reachable = false;
      emit();
      return false;
    }
    checking = (async () => {
      try {
        await probe();
        reachable = true;
      } catch (_) {
        reachable = false;
      }
      emit();
      return reachable;
    })().finally(() => {
      checking = null;
    });
    return checking;
  }

  target.addEventListener?.("online", () => {
    reachable = null;
    emit();
    check();
  });
  target.addEventListener?.("offline", () => {
    reachable = false;
    emit();
  });
  if (typeof setIntervalImpl === "function" && intervalMs > 0) {
    setIntervalImpl(() => {
      if (navigatorImpl?.onLine) check();
    }, intervalMs);
  }

  return {
    get state() {
      return state();
    },
    /** `true` solo si además el servidor respondió alguna vez sin error. */
    get usable() {
      return (navigatorImpl?.onLine ?? true) && reachable !== false;
    },
    check,
    onChange(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    /** Se llama tras cada intento real para no depender solo del sondeo. */
    report(success) {
      const changed = reachable !== success;
      reachable = success;
      if (changed) emit();
    },
  };
}
