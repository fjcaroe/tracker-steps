/**
 * Capa de presentación de la PWA.
 *
 * Está separada del núcleo a propósito: aquí solo hay DOM y textos, sin
 * decisiones de negocio. La App móvil reutiliza el núcleo con su propia vista.
 */
const $ = (selector) => document.querySelector(selector);

export const elements = {
  app: $("#app"),
  form: $("#registration-form"),
  input: $("#identifier"),
  submit: $("#register-button"),
  nfc: $("#nfc-button"),
  install: $("#install-button"),
  diagnosticsButton: $("#diagnostics-button"),
  diagnosticsDialog: $("#diagnostics-dialog"),
  diagnosticsContent: $("#diagnostics-content"),
  diagnosticsCopy: $("#diagnostics-copy"),
  diagnosticsRetry: $("#diagnostics-retry"),
  network: $("#network-status"),
  banner: $("#banner"),
  bannerText: $("#banner-text"),
  bannerAction: $("#banner-action"),
  queue: $("#queue-status"),
  sync: $("#sync-status"),
  message: $("#message"),
  messageSymbol: $("#message-symbol"),
  messageTitle: $("#message-title"),
  messageBody: $("#message-body"),
  clock: $("#clock"),
  content: $("#content"),
  blocker: $("#blocker"),
  blockerSymbol: $("#blocker-symbol"),
  blockerTitle: $("#blocker-title"),
  blockerBody: $("#blocker-body"),
  blockerSteps: $("#blocker-steps"),
  blockerAction: $("#blocker-action"),
  totemName: $("#totem-name"),
  totemCode: $("#totem-code"),
  product: $("#product-name"),
  supplier: $("#supplier-name"),
  methodIcon: $("#method-icon"),
  methodTitle: $("#method-title"),
  methodHelp: $("#method-help"),
  identifierLabel: $("#identifier-label"),
};

const timeFormat = new Intl.DateTimeFormat("es-CL", { dateStyle: "medium", timeStyle: "medium" });
const shortFormat = new Intl.DateTimeFormat("es-CL", { dateStyle: "short", timeStyle: "short" });

let blockerHandler = null;
let bannerHandler = null;

elements.blockerAction.addEventListener("click", () => blockerHandler?.());
elements.bannerAction.addEventListener("click", () => bannerHandler?.());

export const render = {
  clock(date) {
    elements.clock.textContent = timeFormat.format(date);
  },

  totemName(text) {
    elements.totemName.textContent = text;
  },

  config(config, method) {
    elements.totemName.textContent = config.name;
    elements.totemCode.textContent = config.code;
    elements.product.textContent = config.product;
    elements.supplier.textContent = config.supplier;
    elements.methodIcon.textContent = method.icon;
    elements.methodTitle.textContent = method.title;
    elements.methodHelp.textContent = method.help;
    elements.identifierLabel.textContent = method.label;
    elements.input.inputMode = method.inputMode;
    elements.input.type = config.identification_method === "pin" ? "password" : "text";
    elements.input.disabled = false;
    elements.submit.disabled = false;
    elements.app.setAttribute("aria-busy", "false");
  },

  network(snapshot) {
    const usable = snapshot.online && snapshot.reachable !== false;
    elements.network.classList.toggle("online", usable);
    elements.network.classList.toggle("offline", !usable);
    elements.network.querySelector("b").textContent = !snapshot.online
      ? "Sin conexión"
      : snapshot.reachable === false
        ? "Servidor no disponible"
        : "En línea";
  },

  queue(stats) {
    const count = stats.open;
    elements.queue.textContent = count
      ? `${count} pendiente${count === 1 ? "" : "s"} de sincronizar`
      : "Sin registros pendientes";
    elements.queue.classList.toggle("pending", count > 0);
    elements.queue.classList.toggle("warning", Boolean(stats.nearlyFull || stats.staleOffline));
    if (stats.terminal_error) {
      elements.queue.textContent += ` · ${stats.terminal_error} rechazada(s)`;
    }
  },

  syncStatus(stats, session) {
    if (!stats) return;
    const parts = [];
    parts.push(stats.lastSyncedAt
      ? `Última sincronización ${shortFormat.format(new Date(stats.lastSyncedAt))}`
      : "Sin sincronizar aún");
    if (session?.usingCachedConfig) parts.push("configuración guardada");
    elements.sync.textContent = parts.join(" · ");
  },

  message(payload) {
    if (!payload) {
      elements.message.hidden = true;
      return;
    }
    const { kind, title, body } = payload;
    elements.message.hidden = false;
    elements.message.className = `message ${kind}`;
    elements.messageSymbol.textContent =
      kind === "success" ? "✓" : kind === "error" ? "!" : kind === "warning" ? "!" : "↻";
    elements.messageTitle.textContent = title;
    elements.messageBody.textContent = body;
  },

  banner(payload) {
    if (!payload) {
      elements.banner.hidden = true;
      bannerHandler = null;
      return;
    }
    elements.banner.hidden = false;
    elements.bannerText.textContent = payload.text;
    if (payload.action) {
      elements.bannerAction.hidden = false;
      elements.bannerAction.textContent = payload.action.label;
      bannerHandler = payload.action.handler;
    } else {
      elements.bannerAction.hidden = true;
      bannerHandler = null;
    }
  },

  blocker(payload) {
    if (!payload) {
      elements.blocker.hidden = true;
      elements.content.hidden = false;
      blockerHandler = null;
      return;
    }
    elements.blocker.hidden = false;
    elements.content.hidden = true;
    elements.blockerSymbol.textContent = payload.symbol;
    elements.blockerTitle.textContent = payload.title;
    elements.blockerBody.textContent = payload.body;
    elements.blockerSteps.replaceChildren(
      ...(payload.steps || []).map((step) => {
        const item = document.createElement("li");
        item.textContent = step;
        return item;
      }),
    );
    if (payload.action) {
      elements.blockerAction.hidden = false;
      elements.blockerAction.textContent = payload.action.label;
      blockerHandler = payload.action.handler;
      elements.blockerAction.focus();
    } else {
      elements.blockerAction.hidden = true;
      blockerHandler = null;
    }
  },

  diagnostics(report) {
    elements.diagnosticsContent.textContent = JSON.stringify(report, null, 2);
    if (typeof elements.diagnosticsDialog.showModal === "function") {
      if (!elements.diagnosticsDialog.open) elements.diagnosticsDialog.showModal();
    } else {
      elements.diagnosticsDialog.setAttribute("open", "open");
    }
  },

  fatal(error) {
    elements.app.setAttribute("aria-busy", "false");
    render.blocker({
      symbol: "⚠",
      title: "La aplicación no pudo iniciarse",
      body: String(error?.message || error || "Error desconocido."),
      steps: ["Recargue la página.", "Si persiste, informe al administrador con el mensaje anterior."],
      action: { label: "Recargar", handler: () => window.location.reload() },
    });
  },
};
