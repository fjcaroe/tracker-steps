(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const prefix = `steps_packing_${document.body.dataset.userId}_`;
  const queueKey = `${prefix}queue`;
  const ordersKey = `${prefix}orders`;
  let queue = read(queueKey, []);
  let orders = read(ordersKey, []);
  let stream = null;
  let scanning = false;

  function read(key, fallback) {
    try { return JSON.parse(localStorage.getItem(key)) || fallback; }
    catch (_) { return fallback; }
  }
  function persist() {
    localStorage.setItem(queueKey, JSON.stringify(queue));
    $("queue-count").textContent = queue.length;
    const list = $("queue-list");
    list.replaceChildren();
    for (const item of queue) {
      const li = document.createElement("li");
      li.textContent = `${item.payload.kind} ${item.payload.code}`;
      const remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "Quitar";
      remove.addEventListener("click", () => {
        queue = queue.filter((row) => row.id !== item.id);
        persist();
      });
      li.appendChild(remove);
      list.appendChild(li);
    }
  }
  function message(text, type = "") {
    $("message").textContent = text;
    $("message").className = type;
  }
  function connection() {
    $("connection").textContent = navigator.onLine ? "Conectado" : "Sin conexión: los registros quedarán pendientes";
  }
  async function rpc(operation, payload = {}) {
    const response = await fetch("/packing/mobile/api", {
      method: "POST", credentials: "same-origin",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({jsonrpc: "2.0", method: "call", params: {operation, ...payload}, id: Date.now()}),
    });
    if (!response.ok) throw new Error(`Servidor no disponible (${response.status})`);
    const data = await response.json();
    if (data.error) {
      const text = data.error.data && data.error.data.message || data.error.message || "Error al guardar";
      throw new Error(text);
    }
    return data.result;
  }
  function showOrders() {
    const select = $("production");
    const selected = select.value || localStorage.getItem(`${prefix}production`) || "";
    select.replaceChildren();
    const blank = document.createElement("option");
    blank.value = "";
    blank.textContent = "Seleccione una OT";
    select.appendChild(blank);
    for (const order of orders) {
      const option = document.createElement("option");
      option.value = String(order.id);
      option.textContent = `${order.name} · ${order.product}`;
      select.appendChild(option);
    }
    select.value = selected;
    if (!select.value) select.value = "";
    showOrderDetail();
  }
  function showOrderDetail() {
    const selected = orders.find((order) => String(order.id) === $("production").value);
    $("order-detail").textContent = selected ? `${selected.producer} · ${selected.variety}` : "";
    localStorage.setItem(`${prefix}production`, $("production").value);
  }
  async function refreshOrders() {
    try {
      orders = await rpc("orders");
      localStorage.setItem(ordersKey, JSON.stringify(orders));
      showOrders();
      message("Órdenes actualizadas", "success");
    } catch (error) {
      showOrders();
      message(`Se muestran órdenes guardadas en el dispositivo. ${error.message}`, "error");
    }
  }
  function showKindFields() {
    const kind = $("kind").value;
    $("new-tag-fields").hidden = kind === "C";
    $("national-fields").hidden = kind === "C";
  }
  async function synchronize() {
    if (!queue.length) { message("No hay registros pendientes."); return; }
    if (!navigator.onLine) { message("Sin conexión. Intente cuando vuelva la señal.", "error"); return; }
    $("sync-button").disabled = true;
    try {
      while (queue.length) {
        const current = queue[0];
        const result = await rpc("scan", current.payload);
        queue.shift();
        persist();
        const link = document.createElement("a");
        link.href = result.report_url;
        link.target = "_blank";
        link.rel = "noopener";
        link.textContent = `Imprimir tarja ${result.code} con QR`;
        $("print-link").replaceChildren(link);
      }
      message("Todas las tarjas quedaron sincronizadas.", "success");
    } catch (error) {
      message(`Pendiente ${queue[0].payload.code}: ${error.message}`, "error");
    } finally {
      $("sync-button").disabled = false;
    }
  }
  function submit(event) {
    event.preventDefault();
    const productionId = Number($("production").value);
    const code = $("code").value.trim();
    if (!productionId || !code) { message("Seleccione OT y número de tarja.", "error"); return; }
    const payload = {
      production_id: productionId, code, kind: $("kind").value,
      quantity: $("quantity").value, boxes: $("boxes").value,
      kilos: $("kilos").value, product_code: $("product-code").value.trim(),
      result: $("result").value,
    };
    if (queue.some((item) => item.payload.production_id === productionId && item.payload.code === code)) {
      message("Esa tarja ya está pendiente de sincronizar.", "error");
      return;
    }
    queue.push({id: `${Date.now()}-${Math.random()}`, payload});
    persist();
    $("code").value = "";
    $("code").focus();
    message("Tarja guardada en el dispositivo.", "success");
    if (navigator.onLine) synchronize();
  }
  function stopCamera() {
    scanning = false;
    if (stream) stream.getTracks().forEach((track) => track.stop());
    stream = null;
    $("camera").hidden = true;
    $("camera-button").textContent = "Escanear";
  }
  async function camera() {
    if (stream) { stopCamera(); return; }
    if (!("BarcodeDetector" in window) || !navigator.mediaDevices?.getUserMedia) {
      message("Este navegador no permite escanear. Ingrese el código manualmente.", "error");
      return;
    }
    try {
      const detector = new BarcodeDetector({formats: ["qr_code", "code_128", "code_39"]});
      stream = await navigator.mediaDevices.getUserMedia({video: {facingMode: "environment"}});
      const video = $("camera");
      video.srcObject = stream;
      video.hidden = false;
      await video.play();
      $("camera-button").textContent = "Detener cámara";
      scanning = true;
      const scan = async () => {
        if (!scanning) return;
        try {
          const found = await detector.detect(video);
          if (found.length) {
            $("code").value = found[0].rawValue;
            stopCamera();
            message("Código leído. Revise y guarde la tarja.", "success");
            return;
          }
        } catch (_) { /* El operador puede ingresar el código manualmente. */ }
        requestAnimationFrame(scan);
      };
      requestAnimationFrame(scan);
    } catch (error) {
      stopCamera();
      message(`No se pudo abrir la cámara: ${error.message}`, "error");
    }
  }

  $("production").addEventListener("change", showOrderDetail);
  $("refresh-orders").addEventListener("click", refreshOrders);
  $("kind").addEventListener("change", showKindFields);
  $("scan-form").addEventListener("submit", submit);
  $("sync-button").addEventListener("click", synchronize);
  $("camera-button").addEventListener("click", camera);
  window.addEventListener("online", () => { connection(); synchronize(); });
  window.addEventListener("offline", connection);
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/packing/mobile/sw.js").catch(() => {});
  connection();
  showKindFields();
  showOrders();
  persist();
  if (navigator.onLine) { refreshOrders(); if (queue.length) synchronize(); }
})();
