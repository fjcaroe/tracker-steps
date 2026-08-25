/**
 * `ScannerAdapter` de la PWA.
 *
 * Primera opción estable: lector USB o Bluetooth configurado como teclado, que
 * simplemente escribe en el campo y envía un Enter. Además, en Chrome para
 * Android, Web NFC permite leer una pulsera sin lector externo.
 *
 * La App móvil implementa el mismo contrato con un plugin NFC nativo.
 */
export function createWebScanner({ window: win = globalThis } = {}) {
  let abort = null;

  return {
    /** `true` si el navegador expone Web NFC en este contexto seguro. */
    get nfcAvailable() {
      return typeof win.NDEFReader === "function";
    },

    /**
     * Escucha una lectura NFC. Devuelve una función para cancelar.
     * No promete lectura en segundo plano: Web NFC solo funciona con la
     * pestaña en primer plano.
     */
    async scanNfc({ onReading, onError } = {}) {
      if (!this.nfcAvailable) {
        throw new Error("Este dispositivo o navegador no expone Web NFC.");
      }
      this.stopNfc();
      abort = new AbortController();
      const reader = new win.NDEFReader();
      await reader.scan({ signal: abort.signal });
      reader.addEventListener("reading", (event) => {
        // El identificador de negocio puede venir en un registro de texto del
        // tag; si no existe, se usa el número de serie como último recurso.
        const fromRecords = readTextRecord(event.message);
        onReading?.(fromRecords || event.serialNumber || "");
      });
      reader.addEventListener("readingerror", () => {
        onError?.(new Error("No fue posible leer la pulsera. Inténtelo otra vez."));
      });
      return () => this.stopNfc();
    },

    stopNfc() {
      if (abort) {
        abort.abort();
        abort = null;
      }
    },
  };
}

function readTextRecord(message) {
  for (const record of message?.records || []) {
    if (record.recordType !== "text") continue;
    try {
      const decoder = new TextDecoder(record.encoding || "utf-8");
      const value = decoder.decode(record.data).trim();
      if (value) return value;
    } catch (_) {
      // Un registro ilegible no invalida los demás del mismo tag.
    }
  }
  return "";
}
