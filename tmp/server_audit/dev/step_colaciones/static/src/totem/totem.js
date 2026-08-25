(function () {
    "use strict";

    const root = document.getElementById("meal-totem");
    if (!root) return;

    const config = {
        token: root.dataset.token,
        method: root.dataset.method,
        product: root.dataset.product,
        supplier: root.dataset.supplier,
        allowOffline: root.dataset.allowOffline === "1",
    };
    const queueKey = `step_colaciones_queue_${config.token}`;
    const form = document.getElementById("registration-form");
    const input = document.getElementById("identifier");
    const submitButton = document.getElementById("register-button");
    const nfcButton = document.getElementById("nfc-button");
    const networkStatus = document.getElementById("network-status");
    const queueStatus = document.getElementById("queue-status");
    const message = document.getElementById("message");
    const messageTitle = document.getElementById("message-title");
    const messageBody = document.getElementById("message-body");
    let busy = false;
    let clearMessageTimer;

    const methodLabels = {
        barcode: {
            title: "Escanee su credencial",
            help: "Acerque el código de barras al lector.",
            label: "Código de credencial",
            inputMode: "text",
        },
        pin: {
            title: "Ingrese su NIP",
            help: "Digite su clave personal y confirme.",
            label: "NIP del trabajador",
            inputMode: "numeric",
        },
        nfc: {
            title: "Acerque su pulsera",
            help: "Use el lector NFC o acerque la pulsera al equipo.",
            label: "Identificador NFC",
            inputMode: "text",
        },
    };

    function uuid() {
        if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID();
        return `${Date.now()}-${Math.random().toString(16).slice(2)}-${Math.random().toString(16).slice(2)}`;
    }

    function loadQueue() {
        try {
            return JSON.parse(localStorage.getItem(queueKey) || "[]");
        } catch (_) {
            return [];
        }
    }

    function saveQueue(queue) {
        localStorage.setItem(queueKey, JSON.stringify(queue));
        updateQueueStatus();
    }

    function updateQueueStatus() {
        const count = loadQueue().length;
        queueStatus.textContent = count ? `${count} pendiente${count === 1 ? "" : "s"} de sincronizar` : "Sin registros pendientes";
        queueStatus.classList.toggle("pending", count > 0);
    }

    function updateNetworkStatus() {
        const online = navigator.onLine;
        networkStatus.classList.toggle("online", online);
        networkStatus.classList.toggle("offline", !online);
        networkStatus.querySelector("b").textContent = online ? "En línea" : "Sin conexión";
    }

    function showMessage(kind, title, body) {
        clearTimeout(clearMessageTimer);
        message.hidden = false;
        message.className = `meal-message ${kind}`;
        messageTitle.textContent = title;
        messageBody.textContent = body;
        clearMessageTimer = setTimeout(() => {
            message.hidden = true;
            input.focus();
        }, kind === "success" ? 4500 : 6500);
    }

    async function sendRecord(record) {
        const response = await fetch("/colaciones/api/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ token: config.token, ...record }),
        });
        const result = await response.json();
        if (!response.ok && !result.duplicate) {
            const error = new Error(result.message || "No fue posible registrar la colación.");
            error.terminal = Boolean(result.terminal);
            throw error;
        }
        return result;
    }

    async function flushQueue() {
        if (!navigator.onLine || busy) return;
        let queue = loadQueue();
        if (!queue.length) return;
        const pending = [];
        for (const record of queue) {
            try {
                const result = await sendRecord({ ...record, offline: true });
                if (!result.terminal && !result.ok) pending.push(record);
            } catch (_) {
                pending.push(record);
                pending.push(...queue.slice(queue.indexOf(record) + 1));
                break;
            }
        }
        saveQueue(pending);
    }

    async function register(identifier) {
        if (busy || !identifier.trim()) return;
        busy = true;
        submitButton.disabled = true;
        const record = {
            identifier: identifier.trim(),
            client_uuid: uuid(),
            event_datetime: new Date().toISOString(),
            offline: false,
        };
        try {
            if (!navigator.onLine) throw new TypeError("offline");
            const result = await sendRecord(record);
            if (result.ok) {
                showMessage("success", `¡Listo, ${result.employee}!`, result.message);
            } else if (result.duplicate) {
                showMessage("warning", "Registro existente", result.message);
            } else {
                showMessage("error", "No fue posible registrar", result.message);
            }
        } catch (error) {
            if (!navigator.onLine || error instanceof TypeError) {
                if (!config.allowOffline) {
                    showMessage("error", "Sin conexión", "Este tótem requiere conexión para registrar.");
                } else {
                    const queue = loadQueue();
                    queue.push({ ...record, offline: true });
                    saveQueue(queue);
                    showMessage("offline", "Registro guardado", "Se enviará automáticamente cuando vuelva la conexión.");
                }
            } else {
                showMessage("error", "No fue posible registrar", error.message || "Solicite ayuda al administrador.");
            }
        } finally {
            input.value = "";
            busy = false;
            submitButton.disabled = false;
            input.focus();
        }
    }

    async function scanNfc() {
        if (!("NDEFReader" in window)) {
            showMessage("warning", "NFC no disponible", "Use un lector NFC USB configurado como teclado.");
            return;
        }
        try {
            const reader = new NDEFReader();
            await reader.scan();
            showMessage("offline", "Lector preparado", "Acerque la pulsera al dispositivo.");
            reader.addEventListener("reading", (event) => {
                let identifier = event.serialNumber || "";
                for (const record of event.message.records) {
                    if (record.recordType === "text") {
                        identifier = new TextDecoder(record.encoding || "utf-8").decode(record.data);
                        break;
                    }
                }
                if (identifier) register(identifier);
            }, { once: true });
        } catch (error) {
            showMessage("error", "No se pudo iniciar NFC", error.message || "Revise los permisos del navegador.");
        }
    }

    const labels = methodLabels[config.method] || methodLabels.barcode;
    document.getElementById("method-title").textContent = labels.title;
    document.getElementById("method-help").textContent = labels.help;
    document.getElementById("identifier-label").textContent = labels.label;
    input.inputMode = labels.inputMode;
    if (config.method === "pin") input.type = "password";
    if (config.method === "nfc") nfcButton.hidden = false;

    form.addEventListener("submit", (event) => {
        event.preventDefault();
        register(input.value);
    });
    nfcButton.addEventListener("click", scanNfc);
    window.addEventListener("online", () => { updateNetworkStatus(); flushQueue(); });
    window.addEventListener("offline", updateNetworkStatus);

    setInterval(() => {
        document.getElementById("clock").textContent = new Intl.DateTimeFormat("es-CL", {
            dateStyle: "medium", timeStyle: "medium",
        }).format(new Date());
    }, 1000);

    if ("serviceWorker" in navigator) {
        navigator.serviceWorker.register("/colaciones/sw.js", { scope: "/colaciones/" }).then(async () => {
            try {
                const cache = await caches.open("step-colaciones-v1");
                await cache.add(window.location.href);
            } catch (_) { /* La aplicación sigue funcionando en línea. */ }
        });
    }
    updateNetworkStatus();
    updateQueueStatus();
    flushQueue();
    input.focus();
})();
