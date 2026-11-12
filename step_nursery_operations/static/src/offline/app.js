const byId = id => document.getElementById(id);
const company = byId("company"), order = byId("order"), kind = byId("kind");
const setStatus = value => { byId("status").textContent = value; };
let db, profile, session, busy = false, lastErrors = new Map();

function openStore() {
    return new Promise((resolve, reject) => {
        const req = indexedDB.open("steps-nursery-offline", 1);
        req.onupgradeneeded = () => {
            req.result.createObjectStore("profile");
            req.result.createObjectStore("outbox", {keyPath: "id"});
        };
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
    });
}
function request(store, mode, work) {
    return new Promise((resolve, reject) => {
        const tx = db.transaction(store, mode), req = work(tx.objectStore(store));
        tx.oncomplete = () => resolve(req.result);
        tx.onabort = () => reject(tx.error);
    });
}
async function getJSON(path, options = {}) {
    const response = await fetch("/nursery-offline/" + path, {cache:"no-store", ...options});
    if (!response.ok || !response.headers.get("Content-Type")?.includes("application/json")) throw new Error("Sesión no disponible");
    return response.json();
}
const ownRows = async () => profile ? (await request("outbox", "readonly", s => s.getAll()))
    .filter(item => item.uid === profile.uid && item.company === profile.company) : [];
const option = (label, value) => new Option(label, value);

async function show() {
    const conflict = profile && session && profile.uid !== session.uid;
    const allowed = profile && (!session || session.companies.some(c => c.id === profile.company));
    const rows = conflict ? [] : await ownRows();
    const orders = !conflict && allowed ? profile.orders : [];
    const chosen = order.value;
    order.replaceChildren(option("Seleccione orden", ""), ...orders.map(item => option(item.name, item.id)));
    order.value = orders.some(item => String(item.id) === chosen) ? chosen : "";
    byId("entry").disabled = !orders.length;
    byId("workspace").textContent = !profile ? "Descargue las órdenes con internet antes de salir." : conflict ?
        "Hay otra sesión. Vuelva a ingresar con el usuario que preparó el dispositivo." :
        profile.name + " · " + orders.length + " órdenes descargadas.";
    byId("queue-count").textContent = rows.length + " por sincronizar";
    byId("pending").replaceChildren(...rows.slice(0, 30).map(item => {
        const li = document.createElement("li");
        li.textContent = item.order_name + " · " + ({germination:"Germinación",watering:"Riego",observation:"Observación"}[item.kind])
            + (lastErrors.has(item.id) ? " · " + lastErrors.get(item.id) : "");
        return li;
    }));
    byId("prepare").disabled = busy || !session || !company.value || !!conflict;
    byId("sync").disabled = busy || !rows.length || !session || !!conflict || !allowed;
}
async function reconnect() {
    try {
        session = await getJSON("session");
        company.replaceChildren(...session.companies.map(item => option(item.name, item.id)));
        if (profile && session.companies.some(item => item.id === profile.company)) company.value = String(profile.company);
        company.disabled = !session.companies.length;
        setStatus("Conectado. Puede descargar órdenes y sincronizar capturas.");
    } catch {
        session = null;
        company.disabled = true;
        setStatus(navigator.onLine ? "Inicie sesión en Odoo para actualizar o sincronizar." : "Sin conexión. Las capturas se guardan en este dispositivo.");
    }
    await show();
}
async function sync() {
    if (busy || !profile || !session || session.uid !== profile.uid) return;
    busy = true;
    await show();
    try {
        const rows = (await ownRows()).slice(0, 30);
        if (!rows.length) return;
        const body = new FormData();
        body.set("csrf_token", session.csrf); body.set("uid", String(profile.uid));
        body.set("company", String(profile.company));
        body.set("batch", JSON.stringify(rows.map(({id, order_id, performed_at, kind, sample, germinated, note}) =>
            ({id, order_id, performed_at, kind, sample, germinated, note}))));
        const results = await getJSON("sync", {method:"POST", body});
        const submitted = new Set(rows.map(row => row.id));
        let sent = 0;
        for (const item of results) {
            if (!submitted.has(item.id)) continue;
            if (item.ok) {
                await request("outbox", "readwrite", s => s.delete(item.id));
                sent++; lastErrors.delete(item.id);
            } else lastErrors.set(item.id, item.error);
        }
        setStatus(sent + " sincronizadas. " + (await ownRows()).length + " pendientes.");
    } catch {
        setStatus("No se pudo sincronizar. Las capturas siguen guardadas.");
    } finally {
        busy = false;
        await show();
    }
}
byId("prepare").addEventListener("click", async () => {
    if (!session || busy) return;
    busy = true;
    await show();
    try {
        const chosen = session.companies.find(item => item.id === Number(company.value));
        if (!chosen) return;
        if (profile && profile.company !== chosen.id && (await ownRows()).length)
            throw new Error("Sincronice las capturas pendientes antes de cambiar de empresa.");
        const orders = await getJSON("orders/" + chosen.id);
        profile = {uid:session.uid, company:chosen.id, name:chosen.name, orders};
        await request("profile", "readwrite", s => s.put(profile, "selected"));
        setStatus("Órdenes descargadas. Puede registrar labores sin internet.");
    } catch (error) { setStatus(error.message); }
    finally { busy = false; await show(); }
});
function toggle() {
    const needsSample = kind.value === "germination";
    byId("sample-fields").hidden = !needsSample;
    byId("sample").required = byId("germinated").required = needsSample;
    byId("note").required = !needsSample;
}
kind.addEventListener("change", toggle);
company.addEventListener("change", show);
byId("sync").addEventListener("click", sync);
byId("capture").addEventListener("submit", async event => {
    event.preventDefault();
    if (!profile || (session && session.uid !== profile.uid)) return;
    const chosen = profile.orders.find(item => item.id === Number(order.value));
    if (!chosen) return;
    const sample = kind.value === "germination" ? Number(byId("sample").value) : 0;
    const germinated = kind.value === "germination" ? Number(byId("germinated").value) : 0;
    if (germinated > sample) { setStatus("Las germinadas no pueden superar la muestra."); return; }
    try {
        await request("outbox", "readwrite", s => s.add({
            id:crypto.randomUUID(), uid:profile.uid, company:profile.company,
            order_id:chosen.id, order_name:chosen.name, kind:kind.value, sample, germinated,
            performed_at:new Date().toISOString().slice(0,19).replace("T"," "),
            note:byId("note").value.trim(),
        }));
        byId("sample").value = byId("germinated").value = byId("note").value = "";
        setStatus("Captura guardada en el dispositivo.");
        await show();
    } catch { setStatus("No se pudo guardar. Revise el almacenamiento del navegador."); }
});
try {
    db = await openStore();
    profile = await request("profile", "readonly", s => s.get("selected"));
    toggle();
    await reconnect();
    if ("serviceWorker" in navigator) {
        try { await navigator.serviceWorker.register("/nursery-offline/sw.js"); }
        catch { setStatus("Sin caché de la aplicación. Mantenga esta pestaña abierta durante el piloto."); }
    }
    window.addEventListener("offline", reconnect);
    window.addEventListener("online", async () => { await reconnect(); await sync(); });
} catch { setStatus("El navegador no permite guardar capturas offline."); }
