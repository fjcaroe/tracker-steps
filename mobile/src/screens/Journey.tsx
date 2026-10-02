import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { catalogs, sessions, type CostCenter, type Driver, type Field, type Implement, type Labor, type Machine } from '../lib/api';
import { acceptFix, haversineMeters, keepAwake, watchPosition, type Fix } from '../lib/geo';
import { activeStore, formatDuration, parseNumber, pointQueue, type Active } from '../lib/queue';

type Catalogs = { machines: Machine[]; labors: Labor[]; drivers: Driver[]; implementsList: Implement[]; fields: Field[]; costCenters: CostCenter[] };

export default function Journey({ online }: { online: boolean }) {
  const [active, setActive] = useState<Active | null>(activeStore.get);
  return active
    ? <Tracking active={active} online={online} onChange={(a) => { activeStore.set(a); setActive(a); }} />
    : <StartForm onStarted={(a) => { activeStore.set(a); setActive(a); }} />;
}

function StartForm({ onStarted }: { onStarted: (a: Active) => void }) {
  const [data, setData] = useState<Catalogs | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [f, setF] = useState({ machine: '', labor: '', cc: '', field: '', implement: '', driver: '', hm: '', tank: '' });
  const set = (k: keyof typeof f) => (v: string) => setF((p) => ({ ...p, [k]: v }));

  const load = useCallback(() => {
    setError('');
    Promise.all([catalogs.machines(), catalogs.labors(), catalogs.drivers(), catalogs.implements(), catalogs.fields(), catalogs.costCenters()])
      .then(([machines, labors, drivers, implementsList, fields, costCenters]) => setData({ machines, labors, drivers: drivers.filter((d) => d.is_active), implementsList: implementsList.filter((i) => i.is_active), fields, costCenters }))
      .catch((e: Error) => setError(e.message));
  }, []);
  useEffect(load, [load]);

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
    try {
      const now = new Date();
      const day = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
      const wo = await sessions.createWorkOrder({
        code: `WO-${day}-M${machine.id}-CC${f.cc}-L${labor.id}-${now.getTime().toString(36)}`, work_date: day, season: String(now.getFullYear()),
        machine_id: machine.id, activity_id: labor.activity_id, labor_id: labor.id, cost_center_id: Number(f.cc), field_id: f.field ? Number(f.field) : null,
        implement_id: f.implement ? Number(f.implement) : null, hourmeter_initial: hm, fuel_tank_start_liters: tank,
      });
      const session = await sessions.start({ machine_id: machine.id, driver_id: f.driver ? Number(f.driver) : null, cost_center_id: Number(f.cc), work_order_id: wo.id });
      onStarted({ sessionId: session.id, workOrderId: wo.id, machineId: machine.id, machineName: machine.name, startedAt: Date.now(), hourmeterStart: hm, tankStart: tank, tankCapacity: machine.tank_capacity_liters, distanceM: 0 });
    } catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  };

  if (error && !data) return <section className="card"><p className="error" role="alert">{error}</p><button onClick={load}>Reintentar</button></section>;
  if (!data) return <p role="status" className="muted">Cargando máquinas y labores…</p>;
  if (!data.costCenters.length) return <section className="card empty"><h2>Sin centros de costo</h2><p>Tu usuario aún no tiene centros de costo asignados. Pide a un administrador que te los asigne para registrar jornadas.</p></section>;

  const fields = data.fields.filter((x) => !f.cc || x.cost_center_id == null || String(x.cost_center_id) === f.cc);
  return (
    <form className="stack" onSubmit={submit}>
      <h1>Iniciar jornada</h1>
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

function Tracking({ active, online, onChange }: { active: Active; online: boolean; onChange: (a: Active | null) => void }) {
  const [now, setNow] = useState(Date.now());
  const [fix, setFix] = useState<Fix | null>(null);
  const [geoError, setGeoError] = useState('');
  const [pending, setPending] = useState(pointQueue.size(active.sessionId));
  const [finishing, setFinishing] = useState(false);
  const last = useRef<Fix | null>(null);
  const lastSaved = useRef(0);
  const activeRef = useRef(active);
  activeRef.current = active;

  const flush = useCallback(async () => {
    await pointQueue.flush(active.sessionId, (p) => sessions.points(active.sessionId, p));
    setPending(pointQueue.size(active.sessionId));
  }, [active.sessionId]);

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
        if (d > 1) { const a = { ...activeRef.current, distanceM: activeRef.current.distanceM + d }; activeStore.set(a); }
      }
      last.current = next; lastSaved.current = next.ts;
      pointQueue.push(active.sessionId, { ts: new Date(next.ts).toISOString(), lat: next.lat, lon: next.lon, speed_mps: next.speed_mps, accuracy_m: next.accuracy_m });
      setPending(pointQueue.size(active.sessionId));
    }, (e) => setGeoError(e === 'denied' ? 'Permiso de ubicación denegado: actívalo para registrar la ruta.' : 'No se pudo obtener la ubicación. ¿Tienes GPS activo?'))
      .then((s) => { if (cancelled) s(); else stop = s; });
    void keepAwake().then((r) => { if (cancelled) r(); else release = r; });
    void flush();
    return () => { cancelled = true; clearInterval(tick); clearInterval(sync); stop(); release(); };
  }, [active.sessionId, flush]);

  useEffect(() => { if (online) void flush(); }, [online, flush]);

  const km = (activeRef.current.distanceM || active.distanceM) / 1000;
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
      {geoError && <p className="error" role="alert">{geoError}</p>}
      <p className="muted center">{pending ? `${pending} puntos por enviar${online ? '' : ' (sin conexión)'}` : 'Ruta al día con el servidor'}</p>
      <button className="danger big" onClick={() => setFinishing(true)}>Finalizar jornada</button>
      {finishing && <FinishSheet active={active} flush={flush} onCancel={() => setFinishing(false)} onDone={() => onChange(null)} />}
    </section>
  );
}

function FinishSheet({ active, flush, onCancel, onDone }: { active: Active; flush: () => Promise<void>; onCancel: () => void; onDone: () => void }) {
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
      await flush();
      if (pointQueue.size(active.sessionId) > 0) throw new Error('Aún hay puntos GPS sin enviar. Conéctate a internet y reintenta: no se perderán.');
      await sessions.close(active.sessionId);
      await sessions.finishWorkOrder(active.workOrderId, { hourmeter_final: hmEnd, fuel_refill_liters: ref, fuel_tank_end_liters: tankEnd });
      onDone();
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
