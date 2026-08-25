import {
  QueueFullError,
  buildDiagnostics,
  createApiClient,
  createQueue,
  createSyncEngine,
  createTotemSession,
  createUuid,
  migrateLegacyQueue,
} from "../core/index.js";
import { createFetchTransport } from "../adapters/web/fetch-transport.js";
import { createQueueRepository } from "../adapters/web/indexeddb-queue-repository.js";
import {
  createLegacyQueueSource,
  createWebConfigStore,
  createWebTokenStore,
} from "../adapters/web/web-stores.js";
import { createWebDeviceInfo } from "../adapters/web/web-device-info.js";
import { createWebNetworkMonitor } from "../adapters/web/web-network-monitor.js";
import { createWebScanner } from "../adapters/web/web-scanner.js";
import { render, elements } from "./view.js";

export const APP_VERSION = "2026.08.21.4";

const METHODS = {
  barcode: {
    title: "Escanee su credencial",
    help: "Acerque el código de barras al lector.",
    label: "Código de credencial",
    inputMode: "text",
    icon: "▥",
  },
  pin: {
    title: "Ingrese su NIP",
    help: "Digite su clave personal y confirme.",
    label: "NIP del trabajador",
    inputMode: "numeric",
    icon: "⌨",
  },
  nfc: {
    title: "Acerque su pulsera",
    help: "Use NFC del dispositivo o un lector USB configurado como teclado.",
    label: "Identificador NFC",
    inputMode: "text",
    icon: "✳",
  },
};

async function boot() {
  const transport = createFetchTransport();
  const api = createApiClient({ transport });
  const repository = await createQueueRepository();
  const tokenStore = createWebTokenStore();
  const configStore = createWebConfigStore();
  const deviceInfo = createWebDeviceInfo({ appVersion: APP_VERSION, platform: "pwa" });

  // Un equipo que se actualiza desde la versión 1 no debe perder marcaciones.
  const migration = await migrateLegacyQueue({
    legacySource: createLegacyQueueSource(),
    repository,
  });

  const queue = createQueue({ repository });
  const session = createTotemSession({ api, tokenStore, configStore });
  const scanner = createWebScanner();
  const network = createWebNetworkMonitor({ probe: () => api.health() });
  const engine = createSyncEngine({
    api,
    queue,
    token: () => tokenStore.get(),
    device: () => deviceInfoPayload,
    capabilities: () => session.capabilities,
  });

  let deviceInfoPayload = await deviceInfo.payload();
  let busy = false;
  let blocked = false;
  let installPrompt = null;
  let pendingWorker = null;
  let messageTimer = null;

  const state = {
    status: "loading",
    config: null,
    cached: false,
    stats: null,
    online: null,
    migration,
    repositoryKind: repository.kind,
  };

  // ------------------------------------------------------------------
  function showMessage(kind, title, body, { sticky = false } = {}) {
    clearTimeout(messageTimer);
    render.message({ kind, title, body });
    if (sticky) return;
    messageTimer = setTimeout(() => {
      render.message(null);
      focusInput();
    }, kind === "success" ? 4500 : 7000);
  }

  function focusInput() {
    if (blocked || elements.input.disabled) return;
    // El tótem se usa con lector: el foco debe volver siempre al campo.
    elements.input.focus();
  }

  async function refreshQueue() {
    state.stats = await queue.stats();
    render.queue(state.stats);
    return state.stats;
  }

  function applyConfig(config, { cached = false } = {}) {
    state.config = config;
    state.cached = cached;
    const method = METHODS[config.identification_method] || METHODS.barcode;
    document.title = `${config.name} · Colaciones`;
    render.config(config, method);
    elements.nfc.hidden = !(config.identification_method === "nfc" && scanner.nfcAvailable);
    setBlocked(false);
    focusInput();
  }

  function setBlocked(value, payload) {
    blocked = value;
    render.blocker(value ? payload : null);
    elements.input.disabled = value || !state.config;
    elements.submit.disabled = value || !state.config;
    elements.app.setAttribute("aria-busy", value ? "false" : String(!state.config));
  }

  // ------------------------------------------------------------------
  async function loadConfiguration() {
    await session.probe();
    const result = await session.load();
    state.status = result.status;
    if (result.status === "unpaired") {
      setBlocked(true, {
        symbol: "🔗",
        title: "Equipo no asociado",
        body: "Este equipo todavía no está vinculado a un tótem de Colaciones.",
        steps: [
          "Abra Odoo y entre a Colaciones → Tótems.",
          "Seleccione el tótem de este equipo y pulse Abrir tótem.",
          "La aplicación quedará asociada y podrá usarse sin conexión.",
        ],
      });
      render.totemName("Sin configurar");
      return;
    }
    if (result.status === "revoked") {
      setBlocked(true, {
        symbol: "⛔",
        title: "Acceso revocado",
        body: "El token de este equipo ya no es válido. No se aceptarán nuevas capturas.",
        steps: [
          "Solicite al administrador un enlace nuevo desde Colaciones → Tótems.",
          "Las capturas ya confirmadas por el servidor no se pierden.",
        ],
        action: { label: "Comprobar de nuevo", handler: () => loadConfiguration() },
      });
      render.totemName("Acceso revocado");
      return;
    }
    if (result.status === "unavailable") {
      setBlocked(true, {
        symbol: "📡",
        title: "Sin configuración disponible",
        body: "La primera apertura necesita conexión para descargar la configuración del tótem.",
        steps: ["Conecte el equipo a internet.", "Pulse Reintentar."],
        action: { label: "Reintentar", handler: () => loadConfiguration() },
      });
      render.totemName("Sin conexión");
      return;
    }
    applyConfig(result.config, { cached: result.status === "cached" });
    if (result.status === "cached") {
      showMessage("offline", "Modo sin conexión", "Se usó la última configuración guardada del tótem.");
    }
  }

  // ------------------------------------------------------------------
  async function flush({ announce = false } = {}) {
    if (blocked) return null;
    const before = await queue.stats();
    if (!before.open) return before;
    const summary = await engine.flush();
    network.report(!summary.stopped || summary.revoked);
    const after = await refreshQueue();
    if (summary.revoked) {
      // El servidor ya no reconoce este equipo: bloquear antes de seguir
      // aceptando capturas que nunca podrán registrarse.
      await loadConfiguration();
      return after;
    }
    if (summary.rejected) {
      showMessage(
        "error",
        "Capturas rechazadas",
        `${summary.rejected} captura(s) no fueron aceptadas por el servidor. Revise el diagnóstico.`,
      );
    } else if (announce && !after.open && (summary.registered || summary.duplicate)) {
      showMessage("success", "Sincronización terminada", "Los registros pendientes llegaron al servidor.");
    }
    if (!summary.stopped && session.usingCachedConfig) {
      // El servidor volvió a responder: refrescar la configuración para que el
      // tótem no siga días mostrando la copia guardada.
      await loadConfiguration();
    }
    render.syncStatus(after, session);
    return after;
  }

  async function register(rawIdentifier) {
    const identifier = String(rawIdentifier || "").trim();
    if (busy || blocked || !identifier || !state.config) return;
    busy = true;
    elements.submit.disabled = true;
    const record = {
      clientUuid: createUuid(),
      identifier,
      eventDatetime: new Date().toISOString(),
      offline: false,
    };
    try {
      if (!network.usable) throw new Error("offline");
      const response = await api.register({
        token: await session.token(),
        record,
        device: deviceInfoPayload,
      });
      network.report(true);
      if (response.duplicate) {
        showMessage("warning", "Registro existente", response.message);
      } else {
        showMessage("success", `¡Listo, ${response.employee}!`, response.message);
      }
    } catch (error) {
      await handleRegisterFailure(error, record);
    } finally {
      elements.input.value = "";
      busy = false;
      elements.submit.disabled = blocked || !state.config;
      await refreshQueue();
      render.syncStatus(state.stats, session);
      focusInput();
    }
  }

  async function handleRegisterFailure(error, record) {
    const terminal = error?.terminal === true;
    if (terminal) {
      if (error.status === 404) {
        // El tótem dejó de existir o su token fue revocado durante el turno.
        await loadConfiguration();
        return;
      }
      showMessage("error", "No fue posible registrar", error.message);
      return;
    }
    network.report(false);
    if (!state.config.allow_offline) {
      showMessage("error", "Sin conexión", "Este tótem requiere conexión para registrar.");
      return;
    }
    try {
      await queue.enqueue({ ...record, offline: true });
    } catch (queueError) {
      if (queueError instanceof QueueFullError) {
        showMessage("error", "Memoria del equipo llena", queueError.message, { sticky: true });
        return;
      }
      throw queueError;
    }
    const stats = await refreshQueue();
    if (stats.staleOffline) {
      showMessage(
        "offline",
        "Registro guardado",
        `Este equipo lleva más de ${queue.settings.warnOfflineHours} h sin sincronizar. Avise al administrador.`,
        { sticky: true },
      );
    } else if (stats.nearlyFull) {
      showMessage("offline", "Registro guardado", `Quedan ${queue.settings.maxQueueRecords - stats.open} capturas de memoria.`);
    } else {
      showMessage("offline", "Registro guardado", "Se enviará automáticamente al recuperar conexión.");
    }
  }

  // ------------------------------------------------------------------
  async function openDiagnostics() {
    const report = await buildDiagnostics({
      queue,
      session: {
        token: () => tokenStore.get(),
        config: state.config,
        capabilities: session.capabilities,
        clockSkewMs: session.clockSkewMs,
      },
      deviceInfo,
      appVersion: APP_VERSION,
      online: network.usable,
    });
    report.storage = state.repositoryKind;
    report.migrated_from_v1 = state.migration.migrated;
    render.diagnostics(report);
  }

  // ------------------------------------------------------------------
  elements.form.addEventListener("submit", (event) => {
    event.preventDefault();
    register(elements.input.value);
  });

  // Un lector de código de barras escribe el código y envía Enter. La sumisión
  // implícita del formulario no es fiable en todos los navegadores ni con
  // todos los lectores, así que la tecla se maneja explícitamente.
  elements.input.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== "Tab") return;
    event.preventDefault();
    register(elements.input.value);
  });

  elements.nfc.addEventListener("click", async () => {
    try {
      await scanner.scanNfc({
        onReading: (value) => register(value),
        onError: (error) => showMessage("error", "Lectura NFC fallida", error.message),
      });
      showMessage("offline", "Lector preparado", "Acerque la pulsera al dispositivo.");
    } catch (error) {
      showMessage("warning", "NFC no disponible", error.message);
    }
  });

  elements.install.addEventListener("click", async () => {
    if (!installPrompt) return;
    installPrompt.prompt();
    await installPrompt.userChoice;
    installPrompt = null;
    elements.install.hidden = true;
  });

  elements.diagnosticsButton.addEventListener("click", openDiagnostics);
  elements.diagnosticsRetry.addEventListener("click", async () => {
    await network.check();
    await flush({ announce: true });
    await openDiagnostics();
  });
  elements.diagnosticsCopy.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(elements.diagnosticsContent.textContent);
      elements.diagnosticsCopy.textContent = "Copiado";
      setTimeout(() => {
        elements.diagnosticsCopy.textContent = "Copiar";
      }, 2000);
    } catch (_) {
      elements.diagnosticsCopy.textContent = "No se pudo copiar";
    }
  });

  window.addEventListener("online", async () => {
    await network.check();
    await loadConfiguration();
    await flush({ announce: true });
  });
  window.addEventListener("offline", () => network.report(false));

  document.addEventListener("visibilitychange", async () => {
    if (document.visibilityState !== "visible") return;
    // Volver a primer plano es el momento natural para reintentar.
    await network.check();
    await flush({ announce: true });
  });

  network.onChange((snapshot) => {
    state.online = snapshot;
    render.network(snapshot);
  });

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    installPrompt = event;
    elements.install.hidden = false;
  });

  // Actualización controlada: nunca se recarga sola con capturas en vuelo.
  if ("serviceWorker" in navigator) {
    const registration = await navigator.serviceWorker.register(`./sw.js?v=${APP_VERSION}`, { scope: "./" });
    registration.addEventListener("updatefound", () => {
      const worker = registration.installing;
      if (!worker) return;
      worker.addEventListener("statechange", async () => {
        if (worker.state !== "installed" || !navigator.serviceWorker.controller) return;
        pendingWorker = worker;
        const stats = await queue.stats();
        render.banner({
          text: stats.open
            ? `Hay una versión nueva. Se aplicará cuando terminen de sincronizar ${stats.open} captura(s).`
            : "Hay una versión nueva de la aplicación.",
          action: stats.open ? null : { label: "Actualizar ahora", handler: applyUpdate },
        });
      });
    });
  }

  async function applyUpdate() {
    const stats = await queue.stats();
    if (stats.syncing) {
      showMessage("warning", "Sincronización en curso", "Espere a que terminen de enviarse las capturas.");
      return;
    }
    pendingWorker?.postMessage({ type: "SKIP_WAITING" });
    window.location.reload();
  }

  setInterval(() => render.clock(new Date()), 1000);
  render.clock(new Date());

  // ------------------------------------------------------------------
  await session.associateFromUrl(window.location.href);
  if (window.location.hash.includes("token=")) {
    // El token ya quedó guardado: se limpia de la barra para que no aparezca
    // en capturas de pantalla ni quede en el historial del navegador.
    history.replaceState(null, "", window.location.pathname + window.location.search);
  }
  await queue.recoverInterrupted();
  await refreshQueue();
  await network.check();
  await loadConfiguration();
  await flush({ announce: false });
  render.syncStatus(state.stats, session);
  if (migration.migrated) {
    showMessage(
      "offline",
      "Capturas recuperadas",
      `${migration.migrated} captura(s) de la versión anterior se conservaron y se enviarán al servidor.`,
    );
  }

  // Reintento periódico por si la red vuelve sin que el navegador lo informe.
  setInterval(() => {
    if (!blocked && network.usable) flush({ announce: true });
  }, 60_000);
}

boot().catch((error) => {
  // Un fallo de arranque no debe dejar una pantalla en blanco en el tótem.
  console.error("No fue posible iniciar la aplicación de Colaciones", error);
  render.fatal(error);
});
