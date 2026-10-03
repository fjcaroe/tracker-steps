import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { catalogs, mobile, sessions, type AssignedRoute, type Task, type SessionSummary, type CostCenter, type Driver, type Field, type Implement, type Labor, type Machine } from '../lib/api';
import { acceptFix, haversineMeters, keepAwake, watchPosition, type Fix } from '../lib/geo';
import { activeStore, formatDuration, parseNumber, pointQueue, syncStore, type Active } from '../lib/queue';
import { buildActive, reconcile } from '../lib/reconcile';
import { isNetworkError, startPending, type FinishBody, type Op } from '../lib/outbox';
import { outboxStore, syncAll } from '../lib/sync';
import { continuousDrivingMs, routeStore, summarize, type RoutePoint, type Summary } from '../lib/route';
import { beep, loadSettings } from '../lib/settings';
import { directionsUrl, formatDistance, nextWaypoint, routeDeviationM, routeLengthM } from '../lib/nav';
import MapView from '../components/MapView';
import { ChecklistSheet, ExpenseSheet, IncidentSheet, SosSheet, SummarySheet } from './Sheets';

type Finished = { machine: string; summary: Summary; points: RoutePoint[] };

const CATALOG_CACHE = 'steps_movil_catalogs';
const cachedCatalogs = (): Catalogs | null => { try { const raw = localStorage.getItem(CATALOG_CACHE); return raw ? (JSON.parse(raw) as Catalogs) : null; } catch { return null; } };

type Catalogs = { machines: Machine[]; labors: Labor[]; drivers: Driver[]; implementsList: Implement[]; fields: Field[]; costCenters: CostCenter[] };

export default function Journey({ online, preset, onPresetUsed }: { online: boolean; preset: Task | null; onPresetUsed: () => void }) {
  const [finished, setFinished] = useState<Finished | null>(null);
  const [active, setActive] = useState<Active | null>(activeStore.get);
  const [notice, setNotice] = useState('');
  const [open, setOpen] = useState<SessionSummary[]>([]);
  const [resuming, setResuming] = useState('');
  const [ops, setOps] = useState<Op[]>(outboxStore.ops);
  const [syncing, setSyncing] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const change = (a: Active | null) => { activeStore.set(a); setActive(a); setOps(outboxStore.ops()); };

  const sync = useCallback(async () => {
    setSyncing(true);
    try { await syncAll(); } finally { setSyncing(false); setOps(outboxStore.ops()); const a = activeStore.get(); if (a) setActive((cur) => (cur && cur.workOrderId !== a.workOrderId ? a : cur)); }
  }, []);
  const retry = () => { outboxStore.clearErrors(); void sync(); };
  useEffect(() => { if (online) void sync(); }, [online, sync]);
  useEffect(() => {
    const onVisible = () => { if (document.visibilityState === 'visible') void sync(); };
    document.addEventListener('visibilitychange', onVisible);
    const timer = setInterval(() => { if (outboxStore.ops().length) void sync(); }, 20000);
    return () => { document.removeEventListener('visibilitychange', onVisible); clearInterval(timer); };
  }, [sync]);

  // Al abrir (y al recuperar red) se consulta al servidor: retomar jornada abierta o limpiar una ya cerrada.
  const check = useCallback(async () => {
    try {
      const local = activeStore.get();
      // Una jornada local se consulta por ID: no asumir cierre por quedar fuera de una lista limitada.
      if (local && startPending(outboxStore.ops(), local.sessionId)) return;
      const remote = local ? [await sessions.get(local.sessionId) as SessionSummary] : await sessions.open();
      const r = reconcile(local, remote);
      if (r.kind === 'closed' && local) {
        activeStore.set(null); setActive(null);
        setConfirmed(false);
        setNotice('La jornada que tenías abierta ya fue cerrada en el servidor. Se limpió este teléfono.');
      }
      setOpen(r.kind === 'choose' ? r.candidates : []);
    } catch { /* sin red: se reintenta al volver */ }
  }, []);
  useEffect(() => { if (online) void check(); }, [online, check]);
  useEffect(() => {
    const visible = () => { if (document.visibilityState === 'visible') void sync().then(check); };
    document.addEventListener('visibilitychange', visible);
    return () => document.removeEventListener('visibilitychange', visible);
  }, [sync, check]);

  const resume = async (s: SessionSummary) => {
    setResuming(s.id);
    try {
      const [machines, wos] = await Promise.all([
        catalogs.machines().catch(() => []),
        sessions.workOrdersOn(s.started_at.slice(0, 10)),
      ]);
      setConfirmed(false);
      change(buildActive(s, wos.find((w) => w.id === s.work_order_id) ?? null, machines.find((m) => m.id === s.machine_id) ?? null));
      setNotice(''); setOpen([]);
    } catch (err) { setNotice((err as Error).message); } finally { setResuming(''); }
  };

  return (
    <>
      {notice && <p className="banner" role="status">{notice}</p>}
      {finished && <SummarySheet machine={finished.machine} summary={finished.summary} points={finished.points} onClose={() => setFinished(null)} />}
      {ops.length > 0 && <PendingOps ops={ops} syncing={syncing} online={online} onRetry={retry} />}
      {active
        ? (confirmed
            ? <Tracking active={active} online={online} onChange={change} onSync={sync} onFinished={setFinished} />
            : <ResumeGate active={active} onContinue={() => setConfirmed(true)} />)
        : <>
            {open.length > 0 && (
              <section className="card stack" aria-label="Jornadas abiertas">
                <h2>Tienes jornadas abiertas</h2>
                {open.map((s) => (
                  <div key={s.id} className="row">
                    <div><strong>{s.machine_name ?? `Máquina ${s.machine_id}`}</strong><small>{new Date(s.started_at).toLocaleString('es-CL', { dateStyle: 'medium', timeStyle: 'short' })}</small></div>
                    <button className="primary" onClick={() => void resume(s)} disabled={!!resuming}>{resuming === s.id ? 'Abriendo…' : 'Retomar'}</button>
                  </div>
                ))}
              </section>
            )}
            <StartForm onStarted={(a) => { onPresetUsed(); setConfirmed(true); change(a); }} preset={preset} />
          </>}
    </>
  );
}

/** Una jornada que ya estaba abierta (otro teléfono, app reabierta) no registra GPS hasta que la persona decide continuar. */
function ResumeGate({ active, onContinue }: { active: Active; onContinue: () => void }) {
  return (
    <section className="card gate" aria-label="Jornada pendiente">
      <span className="chip">Jornada pendiente</span>
      <h1>{active.machineName}</h1>
      <p>Iniciada el {new Date(active.startedAt).toLocaleString('es-CL', { dateStyle: 'medium', timeStyle: 'short' }).replace(/\.$/, '')}. La app aún no está registrando tu ruta.</p>
      <button className="primary big" onClick={onContinue}>Continuar jornada y registrar ruta</button>
      <small className="muted">El seguimiento GPS parte solo cuando tú lo confirmas.</small>
    </section>
  );
}

function StartForm({ onStarted, preset }: { onStarted: (a: Active) => void; preset: Task | null }) {
  const [data, setData] = useState<Catalogs | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [f, setF] = useState({ machine: '', labor: '', cc: '', field: '', implement: '', driver: '', hm: '', tank: '' });
  const set = (k: keyof typeof f) => (v: string) => setF((p) => ({ ...p, [k]: v }));

  const load = useCallback(() => {
    setError('');
    Promise.all([catalogs.machines(), catalogs.labors(), catalogs.drivers(), catalogs.implements(), catalogs.fields(), catalogs.costCenters()])
      .then(([machines, labors, drivers, implementsList, fields, costCenters]) => {
        const fresh = { machines, labors, drivers: drivers.filter((d) => d.is_active), implementsList: implementsList.filter((i) => i.is_active), fields, costCenters };
        try { localStorage.setItem(CATALOG_CACHE, JSON.stringify(fresh)); } catch { /* sin espacio */ }
        setData(fresh);
      })
      .catch((e: Error) => { const cached = cachedCatalogs(); if (cached) setData(cached); else setError(e.message); });
  }, []);
  useEffect(load, [load]);

  // Tarea asignada: el formulario llega precargado; solo faltan horómetro y litros.
  useEffect(() => {
    if (!preset || !data) return;
    setF((p) => ({ ...p, machine: String(preset.machine_id ?? ''), labor: String(preset.labor_id), cc: String(preset.cost_center_id ?? ''), field: String(preset.field_id ?? ''), implement: String(preset.implement_id ?? '') }));
    const m = data.machines.find((x) => x.id === preset.machine_id);
    if (m) catalogs.fuelStatus(m.id).then((st) => { if (st.last_liters != null) setF((p) => (p.tank ? p : { ...p, tank: String(st.last_liters) })); }).catch(() => {});
  }, [preset, data]);

  const machine = data?.machines.find((m) => String(m.id) === f.machine);
  const pickMachine = (id: string) => {
    const m = data?.machines.find((x) => String(x.id) === id);
    setF((p) => ({ ...p, machine: id, labor: m?.default_labor_id ? String(m.default_labor_id) : p.labor, cc: m?.cost_center_id ? String(m.cost_center_id) : p.cc, tank: '' }));
    if (m) catalogs.fuelStatus(m.id).then((s) => { if (s.last_liters != null) setF((p) => (p.machine === id && !p.tank ? { ...p, tank: String(s.last_liters) } : p)); }).catch(() => {});
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!data || !machine) return;
    const labor = data.labors.find((l) => String(l.id) === f.labor);
    const hm = parseNumber(f.hm), tank = parseNumber(f.tank);
    const problem = !labor ? 'Selecciona la labor.' : !f.cc ? 'Selecciona el centro de costo.' : hm == null || hm < 0 ? 'Indica el horómetro inicial.'
      : tank == null || tank < 0 ? 'Indica los litros actuales del estanque.' : machine.tank_capacity_liters != null && tank > machine.tank_capacity_liters ? `El estanque admite hasta ${machine.tank_capacity_liters} L.` : '';
    if (problem || !labor || hm == null || tank == null) { setError(problem); return; }
    setBusy(true); setError('');
    const now = new Date();
    const day = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
    const sessionId = crypto.randomUUID();
    const startedAt = now.toISOString();
    const woBody = {
      code: `WO-${day}-M${machine.id}-CC${f.cc}-L${labor.id}-${now.getTime().toString(36)}`, work_date: day, season: String(now.getFullYear()),
      machine_id: machine.id, activity_id: labor.activity_id, labor_id: labor.id, cost_center_id: Number(f.cc), field_id: f.field ? Number(f.field) : null,
      implement_id: f.implement ? Number(f.implement) : null, hourmeter_initial: hm, fuel_tank_start_liters: tank,
    };
    const startBody = { machine_id: machine.id, driver_id: f.driver ? Number(f.driver) : null, cost_center_id: Number(f.cc) };
    const base = { sessionId, machineId: machine.id, machineName: machine.name, startedAt: now.getTime(), hourmeterStart: hm, tankStart: tank, tankCapacity: machine.tank_capacity_liters, distanceM: 0 };
    let woId: number | null = preset ? preset.id : null;
    try {
      if (woId == null) woId = (await sessions.createWorkOrder(woBody)).id;
      else void mobile.updateTask(woId, { mobile_status: 'in_progress', hourmeter_initial: hm, fuel_tank_start_liters: tank }).catch(() => {});
      await sessions.start({ ...startBody, id: sessionId, work_order_id: woId, started_at: startedAt });
      onStarted({ ...base, workOrderId: woId, fromTask: !!preset });
    } catch (err) {
      if (!isNetworkError(err)) { setError((err as Error).message); }
      else {
        // Sin señal: la jornada se crea en el teléfono y se sincroniza al volver la red.
        const ops: Op[] = woId == null ? [{ kind: 'wo_create', sessionId, body: woBody }] : [];
        ops.push({ kind: 'session_start', sessionId, body: startBody, startedAt, ...(woId != null ? { workOrderId: woId } : {}) });
        outboxStore.add(...ops);
        onStarted({ ...base, workOrderId: woId ?? 0, fromTask: !!preset });
      }
    } finally { setBusy(false); }
  };

  if (error && !data) return <section className="card"><p className="error" role="alert">{error}</p><button onClick={load}>Reintentar</button></section>;
  if (!data) return <p role="status" className="muted">Cargando máquinas y labores…</p>;
  if (!data.costCenters.length) return <section className="card empty"><h2>Sin centros de costo</h2><p>Tu usuario aún no tiene centros de costo asignados, por eso no puedes iniciar jornadas. Pide acceso al administrador de Steps de tu empresa indicando tu nombre de usuario; apenas lo asigne, vuelve a abrir esta pantalla.</p></section>;

  const fields = data.fields.filter((x) => !f.cc || x.cost_center_id == null || String(x.cost_center_id) === f.cc);
  return (
    <form className="stack" onSubmit={submit}>
      <h1>Iniciar jornada</h1>
      {preset && <p className="banner" role="status">Tarea {preset.code}{preset.scheduled_time ? ` · ${preset.scheduled_time}` : ''}{preset.notes ? ` — ${preset.notes}` : ''}</p>}
      <Select label="Máquina" value={f.machine} onChange={pickMachine} options={data.machines.map((m) => [String(m.id), m.plate ? `${m.name} · ${m.plate}` : m.name])} required />
      <Select label="Labor" value={f.labor} onChange={set('labor')} options={data.labors.map((l) => [String(l.id), l.name])} required />
      <Select label="Centro de costo" value={f.cc} onChange={set('cc')} options={data.costCenters.map((c) => [String(c.id), c.name])} required />
      <Select label="Campo / potrero" value={f.field} onChange={set('field')} options={fields.map((x) => [String(x.id), x.name])} />
      <Select label="Implemento" value={f.implement} onChange={set('implement')} options={data.implementsList.map((i) => [String(i.id), i.name])} />
      <Select label="Conductor" value={f.driver} onChange={set('driver')} options={data.drivers.map((d) => [String(d.id), d.name])} />
      <div className="grid2">
        <label>Horómetro inicial<input inputMode="decimal" value={f.hm} onChange={(e) => set('hm')(e.target.value)} placeholder="0,0" required /></label>
        <label>Litros en el estanque<input inputMode="decimal" value={f.tank} onChange={(e) => set('tank')(e.target.value)} placeholder={machine?.tank_capacity_liters ? `máx. ${machine.tank_capacity_liters}` : '0'} required /></label>
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      <button className="primary big" disabled={busy || !f.machine}>{busy ? 'Iniciando…' : 'Iniciar jornada'}</button>
    </form>
  );
}

function Select({ label, value, onChange, options, required }: { label: string; value: string; onChange: (v: string) => void; options: [string, string][]; required?: boolean }) {
  return <label>{label}<select value={value} onChange={(e) => onChange(e.target.value)} required={required}><option value="">{required ? 'Seleccionar…' : 'Sin especificar'}</option>{options.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select></label>;
}

function Tracking({ active, online, onChange, onSync, onFinished }: { active: Active; online: boolean; onChange: (a: Active | null) => void; onSync: () => Promise<void>; onFinished: (f: Finished) => void }) {
  const settings = useRef(loadSettings());
  const lastAlert = useRef(0);
  const [sheet, setSheet] = useState<'' | 'check' | 'incident' | 'theft' | 'expense' | 'sos'>('');
  const [toast, setToast] = useState('');
  const [speedAlert, setSpeedAlert] = useState(false);
  const [drivingMin, setDrivingMin] = useState(0);
  const lastBreakBeep = useRef(0);
  const [route, setRoute] = useState<AssignedRoute | null>(null);
  const [reached, setReached] = useState(0);
  const [offRoute, setOffRoute] = useState<number | null>(null);
  const [track, setTrack] = useState<RoutePoint[]>(() => routeStore.get(active.sessionId));
  const lastOff = useRef(0);
  const routeRef = useRef<AssignedRoute | null>(null);
  routeRef.current = route;
  const checkedKey = `steps_movil_checked_${active.sessionId}`;
  const [checked, setChecked] = useState(() => { try { return localStorage.getItem(checkedKey) === '1'; } catch { return false; } });
  const [now, setNow] = useState(Date.now());
  const [fix, setFix] = useState<Fix | null>(null);
  const [geoError, setGeoError] = useState('');
  const [pending, setPending] = useState(pointQueue.size(active.sessionId));
  const [finishing, setFinishing] = useState(false);
  const [lastSync, setLastSync] = useState<number | null>(syncStore.get);
  const last = useRef<Fix | null>(null);
  const lastSaved = useRef(0);
  const activeRef = useRef(active);
  activeRef.current = active;

  // Ruta asignada a esta máquina (se guarda en el teléfono para seguirla sin señal).
  useEffect(() => {
    const key = `steps_movil_route_${active.machineId}`;
    try { const raw = localStorage.getItem(key); if (raw) setRoute(JSON.parse(raw) as AssignedRoute); } catch { /* nada */ }
    mobile.routes(active.machineId).then((rs) => {
      const r = rs.find((x) => x.status === 'in_progress') ?? rs.find((x) => x.status === 'assigned') ?? null;
      setRoute(r);
      try { if (r) localStorage.setItem(key, JSON.stringify(r)); else localStorage.removeItem(key); } catch { /* nada */ }
      if (r && r.status === 'assigned') void mobile.setRoute(r.id, 'in_progress').catch(() => {});
    }).catch(() => {});
  }, [active.machineId]);

  const flush = useCallback(async () => {
    await onSync();
    setPending(pointQueue.size(active.sessionId));
    setLastSync(syncStore.get());
  }, [active.sessionId, onSync]);

  useEffect(() => {
    const tick = setInterval(() => setNow(Date.now()), 1000);
    const sync = setInterval(() => { void flush(); }, 15000);
    let stop = () => {}; let release = () => {}; let cancelled = false;
    void watchPosition((next) => {
      setGeoError(''); setFix(next);
      if (!acceptFix(last.current, next)) return;
      if (next.ts - lastSaved.current < 4000) return;
      if (last.current) {
        const d = haversineMeters(last.current, next);
        if (d > 1) { const a = { ...activeRef.current, distanceM: activeRef.current.distanceM + d }; activeRef.current = a; onChange(a); }
      }
      last.current = next; lastSaved.current = next.ts;
      routeStore.push(active.sessionId, { ts: next.ts, lat: next.lat, lon: next.lon, speed_mps: next.speed_mps });
      const limit = settings.current.speedLimitKmh;
      if (next.speed_mps != null && limit > 0 && next.speed_mps * 3.6 > limit) { setSpeedAlert(true); if (next.ts - lastAlert.current > 60000) { lastAlert.current = next.ts; beep(settings.current.sound); } } else setSpeedAlert(false);
      const dMin = Math.floor(continuousDrivingMs(routeStore.get(active.sessionId)) / 60000);
      setDrivingMin(dMin);
      const after = settings.current.breakAfterMin;
      if (after > 0 && dMin >= after && next.ts - lastBreakBeep.current > 30 * 60000) { lastBreakBeep.current = next.ts; beep(settings.current.sound); }
      pointQueue.push(active.sessionId, { ts: new Date(next.ts).toISOString(), lat: next.lat, lon: next.lon, speed_mps: next.speed_mps, accuracy_m: next.accuracy_m });
      setPending(pointQueue.size(active.sessionId));
      setTrack(routeStore.get(active.sessionId));
      const r = routeRef.current;
      if (r) {
        const wps = r.waypoints;
        setReached((cur) => {
          const nxt = nextWaypoint(next, wps, cur);
          if (nxt >= wps.length && cur < wps.length) { beep(settings.current.sound); void mobile.setRoute(r.id, 'done').catch(() => {}); }
          return nxt;
        });
        const dev = routeDeviationM(next, wps);
        setOffRoute(dev != null && dev > 150 ? dev : null);
        if (dev != null && dev > 150 && next.ts - lastOff.current > 120000) { lastOff.current = next.ts; beep(settings.current.sound); }
      }
    }, (e) => setGeoError(e === 'denied' ? 'Permiso de ubicación denegado: actívalo para registrar la ruta.' : 'No se pudo obtener la ubicación. ¿Tienes GPS activo?'))
      .then((s) => { if (cancelled) s(); else stop = s; });
    void keepAwake().then((r) => { if (cancelled) r(); else release = r; });
    void flush();
    return () => { cancelled = true; clearInterval(tick); clearInterval(sync); stop(); release(); };
  }, [active.sessionId, flush]);

  useEffect(() => { if (online) void flush(); }, [online, flush]);
  useEffect(() => {
    const onVisible = () => { if (document.visibilityState === 'visible') void flush(); };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
  }, [flush]);

  const km = (activeRef.current.distanceM || active.distanceM) / 1000;
  const wps = route?.waypoints ?? [];
  const routeDone = !!route && reached >= wps.length;
  const target = route && !routeDone ? wps[reached] : null;
  const toTarget = target && fix ? haversineMeters(fix, target) : null;
  const fields = (cachedCatalogs()?.fields ?? []).flatMap((f) => (f.polygon && f.polygon.length > 2 ? [{ name: f.name, polygon: f.polygon }] : []));
  const speed = fix?.speed_mps != null ? fix.speed_mps * 3.6 : null;

  return (
    <section className="stack">
      <article className="card live">
        <span className="chip chip--open">● En curso</span>
        <h1>{active.machineName}</h1>
        <p className="clock" aria-label="Tiempo transcurrido">{formatDuration(now - active.startedAt)}</p>
        <div className="grid3">
          <div><strong>{km.toFixed(2)}</strong><small>km</small></div>
          <div><strong>{speed == null ? '—' : speed.toFixed(0)}</strong><small>km/h</small></div>
          <div><strong>{fix?.accuracy_m != null ? `±${Math.round(fix.accuracy_m)}` : '—'}</strong><small>m precisión</small></div>
        </div>
      </article>
      <MapView me={fix} track={track} route={wps} reached={reached} fields={fields} height={280} />
      {geoError && <p className="error" role="alert">{geoError}</p>}
      {settings.current.breakAfterMin > 0 && drivingMin >= settings.current.breakAfterMin && <p className="banner" role="status">Llevas {Math.floor(drivingMin / 60)} h {drivingMin % 60} min conduciendo sin pausa. Detente a descansar al menos 15 minutos.</p>}
      {speedAlert && <p className="error" role="alert">Vas sobre el límite de {settings.current.speedLimitKmh} km/h. Reduce la velocidad.</p>}
      {toast && <p className="banner" role="status">{toast}</p>}
      {route && (
        <article className={`card stack routecard ${offRoute ? 'routecard--off' : ''}`}>
          <div className="row"><div><strong>Ruta asignada: {route.name}</strong>
            <small>{routeDone ? 'Ruta completada' : `Punto ${reached + 1} de ${wps.length}${toTarget != null ? ` · a ${formatDistance(toTarget)}` : ''} · total ${formatDistance(routeLengthM(wps))}`}</small></div>
            <span className="chip chip--open">{routeDone ? 'Hecha' : 'En curso'}</span></div>
          {route.note && <p>{route.note}</p>}
          {offRoute && <p className="error" role="alert">Te alejaste {formatDistance(offRoute)} del trazado asignado.</p>}
          {target && <a className="btnlink" href={directionsUrl(target)} target="_blank" rel="noreferrer">Navegar al siguiente punto</a>}
        </article>
      )}
      <div className="grid2">
        <button className={checked ? '' : 'primary'} onClick={() => setSheet('check')}>{checked ? 'Revisión previa ✓' : 'Revisión previa'}</button>
        <button onClick={() => setSheet('incident')}>Reportar incidente</button>
        <button onClick={() => setSheet('expense')}>Combustible / gastos</button>
        <button onClick={() => setSheet('theft')}>Reportar robo</button>
      </div>
      <button className="sos" onClick={() => setSheet('sos')}>SOS · Emergencia</button>
      {sheet === 'check' && <ChecklistSheet active={active} fix={fix} onClose={() => setSheet('')} onSaved={(m) => { try { localStorage.setItem(checkedKey, '1'); } catch { /* nada */ } setChecked(true); setSheet(''); setToast(m); void onSync(); }} />}
      {(sheet === 'incident' || sheet === 'theft') && <IncidentSheet initial={sheet === 'theft' ? 'theft' : undefined} active={active} fix={fix} onClose={() => setSheet('')} onSaved={(m) => { setSheet(''); setToast(m); void onSync(); }} />}
      {sheet === 'expense' && <ExpenseSheet active={active} fix={fix} onClose={() => setSheet('')} onSaved={(m) => { setSheet(''); setToast(m); void onSync(); }} />}
      {sheet === 'sos' && <SosSheet active={active} fix={fix} onClose={() => setSheet('')} onSaved={(m) => { setSheet(''); setToast(m); void onSync(); }} />}
      <p className="muted center" role="status">
        {pending ? `${pending} puntos por enviar${online ? '' : ' (sin conexión)'}` : 'Ruta al día con el servidor'}
        {' · '}Último envío: {lastSync ? new Date(lastSync).toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' }) : 'aún no'}
      </p>
      <button className="danger big" onClick={() => setFinishing(true)}>Finalizar jornada</button>
      {startPending(outboxStore.ops(), active.sessionId) && <p className="muted center" role="status">Jornada creada en este teléfono: se enviará al servidor cuando haya señal.</p>}
      {finishing && <FinishSheet active={active} flush={flush} onCancel={() => setFinishing(false)} onDone={(f) => { onChange(null); onFinished(f); }} />}
    </section>
  );
}

function FinishSheet({ active, flush, onCancel, onDone }: { active: Active; flush: () => Promise<void>; onCancel: () => void; onDone: (f: Finished) => void }) {
  const [hm, setHm] = useState(String(active.hourmeterStart));
  const [tank, setTank] = useState(String(active.tankStart));
  const [refill, setRefill] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const hmEnd = parseNumber(hm), tankEnd = parseNumber(tank), ref = refill ? parseNumber(refill) : null;
    const problem = hmEnd == null || hmEnd < active.hourmeterStart ? 'El horómetro final debe ser mayor o igual al inicial.'
      : tankEnd == null || tankEnd < 0 ? 'Indica los litros finales del estanque.' : active.tankCapacity != null && tankEnd > active.tankCapacity ? `El estanque admite hasta ${active.tankCapacity} L.`
      : refill && (ref == null || ref < 0) ? 'Litros recargados inválidos.' : '';
    if (problem) { setError(problem); return; }
    setBusy(true); setError('');
    try {
      const body: FinishBody = { hourmeter_final: hmEnd, fuel_refill_liters: ref, fuel_tank_end_liters: tankEnd, ...(active.fromTask ? { mobile_status: 'done', progress_pct: 100 } : {}) };
      const endedAt = new Date().toISOString();
      const points = routeStore.get(active.sessionId);
      const finished: Finished = { machine: active.machineName, points, summary: summarize(points, active.startedAt, Date.now(), { start: active.tankStart, end: tankEnd as number, refill: ref }) };
      const done = () => { routeStore.clear(active.sessionId); try { localStorage.removeItem(`steps_movil_checked_${active.sessionId}`); } catch { /* nada */ } onDone(finished); };
      // Guardar ambas operaciones antes de enviarlas: un fallo después del cierre no pierde el parte final.
      outboxStore.add(
        { kind: 'session_close', sessionId: active.sessionId, endedAt },
        { kind: 'wo_finish', sessionId: active.sessionId, body, ...(active.workOrderId ? { workOrderId: active.workOrderId } : {}) },
      );
      await flush();
      done();
    } catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  };

  return (
    <div className="sheet" role="dialog" aria-modal="true" aria-label="Finalizar jornada">
      <form className="sheet__panel stack" onSubmit={submit}>
        <h2>Cerrar jornada</h2>
        <label>Horómetro final<input inputMode="decimal" value={hm} onChange={(e) => setHm(e.target.value)} required /></label>
        <label>Litros en el estanque al terminar<input inputMode="decimal" value={tank} onChange={(e) => setTank(e.target.value)} required /></label>
        <label>Litros recargados (opcional)<input inputMode="decimal" value={refill} onChange={(e) => setRefill(e.target.value)} placeholder="0" /></label>
        {error && <p className="error" role="alert">{error}</p>}
        <button className="primary big" disabled={busy}>{busy ? 'Cerrando…' : 'Confirmar y cerrar'}</button>
        <button type="button" onClick={onCancel} disabled={busy}>Seguir en jornada</button>
      </form>
    </div>
  );
}

const LABEL: Record<Op['kind'], string> = { wo_create: 'Crear parte de trabajo', session_start: 'Iniciar jornada', session_close: 'Cerrar jornada', wo_finish: 'Registrar horómetro y combustible final', post: 'Registro de campo' };
const POST_LABEL: Record<string, string> = { checklists: 'Revisión previa', incidents: 'Incidente', expenses: 'Gasto / combustible' };
const labelOf = (o: Op) => (o.kind === 'post' ? POST_LABEL[o.path] ?? LABEL.post : LABEL[o.kind]);

function PendingOps({ ops, syncing, online, onRetry }: { ops: Op[]; syncing: boolean; online: boolean; onRetry: () => void }) {
  return (
    <section className="card stack" aria-label="Pendientes de sincronizar">
      <h2>Pendientes de sincronizar ({ops.length})</h2>
      {ops.map((o, i) => (
        <div key={`${o.sessionId}-${o.kind}-${i}`} className="row">
          <div><strong>{labelOf(o)}</strong><small>{o.error ? `Rechazada: ${o.error}` : online ? 'En espera' : 'Sin conexión'}</small></div>
        </div>
      ))}
      <button onClick={onRetry} disabled={syncing}>{syncing ? 'Sincronizando…' : 'Reintentar ahora'}</button>
    </section>
  );
}
