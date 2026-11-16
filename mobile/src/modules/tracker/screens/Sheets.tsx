import { useEffect, useId, useLayoutEffect, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from 'react';
import { mobile, type IncidentCategory } from '../lib/api';
import type { Fix } from '../lib/geo';
import { compressPhoto } from '../lib/photo';
import { parseNumber, type Active } from '../lib/queue';
import { projectRoute, summaryText, type RoutePoint, type Summary } from '../lib/route';
import { emergencyReceived, outboxStore } from '../lib/sync';
import { emergencySmsLink, getEmergencyContacts } from '../lib/emergencyContacts';

const DEFAULT_ITEMS = [
  { key: 'lights', label: 'Luces y señalización' }, { key: 'brakes', label: 'Frenos' }, { key: 'tires', label: 'Neumáticos (presión y desgaste)' },
  { key: 'oil', label: 'Nivel de aceite y refrigerante' }, { key: 'leaks', label: 'Sin fugas de aceite o combustible' }, { key: 'extinguisher', label: 'Extintor vigente' },
];

export function Sheet({ title, onClose, children, closeLabel = 'Cerrar', closingLocked = false }: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  closeLabel?: string;
  closingLocked?: boolean;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const legacy = useRef<HTMLDivElement>(null);
  const headingId = useId();
  const nativeDialog = typeof HTMLDialogElement !== 'undefined' && typeof HTMLDialogElement.prototype.showModal === 'function';
  useLayoutEffect(() => {
    const element = dialog.current;
    if (element) {
      element.showModal();
      return () => element.close();
    }

    const opener = document.activeElement;
    legacy.current?.querySelector<HTMLButtonElement>('button:not(:disabled)')?.focus();
    return () => { if (opener instanceof HTMLElement) opener.focus(); };
  }, []);

  const panel = (
    <div className="sheet__panel stack">
      <div className="row"><h2 id={headingId}>{title}</h2><button type="button" onClick={onClose} disabled={closingLocked}>{closeLabel}</button></div>
      {children}
    </div>
  );

  // Older iOS WebViews have no modal dialog element.
  const onLegacyKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      if (!closingLocked) onClose();
      return;
    }
    if (event.key !== 'Tab') return;
    const controls = [...event.currentTarget.querySelectorAll<HTMLElement>('button, input, select, textarea, a[href]')]
      .filter((control) => control.tabIndex >= 0 && !control.matches(':disabled') && control.getClientRects().length);
    const first = controls[0];
    const last = controls[controls.length - 1];
    if (document.activeElement !== (event.shiftKey ? first : last)) return;
    event.preventDefault();
    (event.shiftKey ? last : first)?.focus();
  };

  if (!nativeDialog) {
    return <div ref={legacy} className="sheet-legacy" role="dialog" aria-modal="true"
      aria-labelledby={headingId} onKeyDown={onLegacyKeyDown}>{panel}</div>;
  }

  return (
    <dialog ref={dialog} className="sheet" aria-labelledby={headingId} onCancel={(event) => {
      event.preventDefault();
      if (!closingLocked) onClose();
    }}>
      {panel}
    </dialog>
  );
}

/** Foto opcional: abre la cámara en el teléfono; la imagen se reduce antes de guardarla. */
function PhotoField({ value, onChange, label }: { value: string; onChange: (b64: string) => void; label: string }) {
  const [busy, setBusy] = useState(false);
  return (
    <label>{label}
      <input type="file" accept="image/*" capture="environment" onChange={async (e) => {
        const file = e.target.files?.[0]; if (!file) return;
        setBusy(true); try { onChange(await compressPhoto(file)); } catch { onChange(''); } finally { setBusy(false); }
      }} />
      {busy && <small>Procesando foto…</small>}
      {value && !busy && <small>Foto lista ({Math.round(value.length * 0.75 / 1024)} KB)</small>}
    </label>
  );
}

type Props = { active: Active; fix: Fix | null; onClose: () => void; onSaved: (message: string) => void };

/** I5 · Revisión previa: cada punto se marca Bien o Con falla; los fallos pueden llevar una nota. */
export function ChecklistSheet({ active, onClose, onSaved }: Props) {
  const [items, setItems] = useState(DEFAULT_ITEMS.map((i) => ({ ...i, ok: true, note: '' })));
  useEffect(() => { mobile.checklistTemplate(active.machineId).then((t) => setItems(t.items.map((i) => ({ ...i, ok: true, note: '' })))).catch(() => {}); }, [active.machineId]);
  const set = (key: string, patch: Partial<(typeof items)[number]>) => setItems((p) => p.map((i) => (i.key === key ? { ...i, ...patch } : i)));
  const save = (e: FormEvent) => {
    e.preventDefault();
    const id = crypto.randomUUID();
    outboxStore.add({ kind: 'post', path: 'checklists', sessionId: active.sessionId, body: { id, machine_id: active.machineId, session_id: active.sessionId, occurred_at: new Date().toISOString(), items: items.map((i) => ({ key: i.key, label: i.label, ok: i.ok, note: i.note || null })) } });
    onSaved(items.every((i) => i.ok) ? 'Revisión previa registrada: todo en orden.' : 'Revisión registrada con fallas. Considera reportar un incidente.');
  };
  return (
    <Sheet title="Revisión previa" onClose={onClose}>
      <form className="stack" onSubmit={save}>
        {items.map((i) => (
          <div key={i.key} className="stack">
            <div className="row"><span>{i.label}</span>
              <span className="seg" role="group" aria-label={i.label}>
                <button type="button" className={i.ok ? 'is-on' : ''} aria-pressed={i.ok} onClick={() => set(i.key, { ok: true })}>Bien</button>
                <button type="button" className={!i.ok ? 'is-on is-bad' : ''} aria-pressed={!i.ok} onClick={() => set(i.key, { ok: false })}>Falla</button>
              </span></div>
            {!i.ok && <input placeholder="¿Qué falla?" value={i.note} onChange={(e) => set(i.key, { note: e.target.value })} aria-label={`Nota de ${i.label}`} />}
          </div>
        ))}
        <button className="primary big">Guardar revisión</button>
      </form>
    </Sheet>
  );
}

const CATEGORIES: [IncidentCategory, string][] = [['breakdown', 'Falla mecánica'], ['accident', 'Accidente'], ['damage', 'Daño'], ['theft', 'Robo'], ['other', 'Otro']];

/** I5 · Incidente con categoría, nota, foto, ubicación y hora (cola sin conexión). */
export function IncidentSheet({ active, fix, onClose, onSaved, initial }: Props & { initial?: IncidentCategory }) {
  const [category, setCategory] = useState<IncidentCategory>(initial ?? 'breakdown');
  const [note, setNote] = useState('');
  const [photo, setPhoto] = useState('');
  const save = (e: FormEvent) => {
    e.preventDefault();
    outboxStore.add({ kind: 'post', path: 'incidents', sessionId: active.sessionId, body: { id: crypto.randomUUID(), category, note: note || null, machine_id: active.machineId, session_id: active.sessionId, lat: fix?.lat ?? null, lon: fix?.lon ?? null, occurred_at: new Date().toISOString(), photo_b64: photo || null } });
    onSaved('Incidente registrado. Se enviará apenas haya señal.');
  };
  return (
    <Sheet title={initial === 'theft' ? 'Reportar robo' : 'Reportar incidente'} onClose={onClose}>
      <form className="stack" onSubmit={save}>
        <label>Tipo<select value={category} onChange={(e) => setCategory(e.target.value as IncidentCategory)}>{CATEGORIES.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select></label>
        <label>Qué pasó<input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Describe brevemente" /></label>
        <PhotoField label="Foto (opcional)" value={photo} onChange={setPhoto} />
        <small>{fix ? 'Se adjuntará tu ubicación actual y la hora.' : 'Sin ubicación GPS por ahora: se adjuntará solo la hora.'}</small>
        <button className="primary big">Enviar incidente</button>
      </form>
    </Sheet>
  );
}

/** I6 · Combustible y gastos de la jornada, con foto de la boleta. */
export function ExpenseSheet({ active, onClose, onSaved }: Props) {
  const [kind, setKind] = useState<'fuel' | 'toll' | 'other'>('fuel');
  const [f, setF] = useState({ liters: '', amount: '', station: '', odometer: '', note: '' });
  const [photo, setPhoto] = useState('');
  const [error, setError] = useState('');
  const set = (k: keyof typeof f) => (v: string) => setF((p) => ({ ...p, [k]: v }));
  const save = (e: FormEvent) => {
    e.preventDefault();
    const liters = parseNumber(f.liters), amount = parseNumber(f.amount);
    if (kind === 'fuel' && (!liters || liters <= 0)) { setError('Indica los litros cargados.'); return; }
    if (kind !== 'fuel' && (!amount || amount <= 0)) { setError('Indica el monto.'); return; }
    outboxStore.add({ kind: 'post', path: 'expenses', sessionId: active.sessionId, body: {
      id: crypto.randomUUID(), kind, session_id: active.sessionId, work_order_id: active.workOrderId || null, machine_id: active.machineId,
      liters: kind === 'fuel' ? liters : null, amount: amount ?? null, station: f.station || null, odometer: parseNumber(f.odometer), note: f.note || null,
      occurred_at: new Date().toISOString(), photo_b64: photo || null } });
    onSaved(kind === 'fuel' ? `Carga de ${liters} L registrada.` : 'Gasto registrado.');
  };
  return (
    <Sheet title="Combustible y gastos" onClose={onClose}>
      <form className="stack" onSubmit={save}>
        <label>Tipo<select value={kind} onChange={(e) => setKind(e.target.value as typeof kind)}><option value="fuel">Carga de combustible</option><option value="toll">Peaje</option><option value="other">Otro gasto</option></select></label>
        <div className="grid2">
          {kind === 'fuel' && <label>Litros<input inputMode="decimal" value={f.liters} onChange={(e) => set('liters')(e.target.value)} /></label>}
          <label>Monto ($)<input inputMode="decimal" value={f.amount} onChange={(e) => set('amount')(e.target.value)} /></label>
        </div>
        {kind === 'fuel' && <div className="grid2">
          <label>Estación<input value={f.station} onChange={(e) => set('station')(e.target.value)} /></label>
          <label>Odómetro / horómetro<input inputMode="decimal" value={f.odometer} onChange={(e) => set('odometer')(e.target.value)} /></label>
        </div>}
        <label>Nota<input value={f.note} onChange={(e) => set('note')(e.target.value)} /></label>
        <PhotoField label="Foto de la boleta" value={photo} onChange={setPhoto} />
        {error && <p className="error" role="alert">{error}</p>}
        <button className="primary big">Guardar</button>
      </form>
    </Sheet>
  );
}

export function SosSheet({ active, fix, userId, online, onClose, onSync }: Omit<Props, 'onSaved'> & {
  userId: number; online: boolean; onSync: () => Promise<void>;
}) {
  const [contacts] = useState(() => getEmergencyContacts(userId));
  const [status, setStatus] = useState<'ready' | 'sending' | 'queued' | 'sent' | 'rejected' | 'storage'>('ready');
  const [incidentId, setIncidentId] = useState<string | null>(null);

  useEffect(() => {
    if (status !== 'queued' || !incidentId) return;
    const refresh = () => {
      if (emergencyReceived(incidentId)) setStatus('sent');
      else if (outboxStore.ops().some(op => op.kind === 'post' && op.body.id === incidentId && op.error)) setStatus('rejected');
    };
    refresh();
    const timer = window.setInterval(refresh, 1000);
    return () => window.clearInterval(timer);
  }, [incidentId, status]);

  const send = async () => {
    if (status !== 'ready' && status !== 'storage') return;
    const id = crypto.randomUUID();
    outboxStore.add({
      kind: 'post', path: 'incidents', sessionId: active.sessionId,
      body: { id, category: 'sos', note: 'SOS del conductor', machine_id: active.machineId, session_id: active.sessionId,
        lat: fix?.lat ?? null, lon: fix?.lon ?? null, occurred_at: new Date().toISOString() },
    });
    const findPending = () => outboxStore.ops().find(op => op.kind === 'post' && op.body.id === id);
    if (!findPending()) { setStatus('storage'); return; }
    setIncidentId(id);
    if (!online) { setStatus('queued'); return; }
    setStatus('sending');
    try {
      await onSync();
      const pending = findPending();
      if (pending && !pending.error && !emergencyReceived(id)) await onSync();
    } catch {
      setStatus('queued');
      return;
    }
    const pending = findPending();
    setStatus(emergencyReceived(id) ? 'sent' : pending?.error ? 'rejected' : pending ? 'queued' : 'storage');
  };

  return (
    <Sheet title="Emergencia" onClose={onClose}>
      <p>Envía un aviso a la oficina. {fix ? 'Se adjuntará la última ubicación del teléfono.' : 'La ubicación aún no está disponible.'}</p>
      <button className="danger big" onClick={() => void send()} disabled={status !== 'ready' && status !== 'storage'}>
        {status === 'sending' ? 'Enviando SOS…' : 'Enviar SOS'}
      </button>
      {status === 'sent' && <p role="status">La oficina recibió el SOS.</p>}
      {status === 'queued' && <p role="status">SOS pendiente. La app reintentará cuando pueda conectarse.</p>}
      {status === 'rejected' && <p role="alert">El servidor no recibió el aviso. Usa los contactos de emergencia y revisa los pendientes.</p>}
      {status === 'storage' && <p role="alert">El aviso no se pudo guardar. Usa los contactos de emergencia.</p>}
      {contacts.length > 0 && <section className="stack" aria-label="Contactos de emergencia">
        {contacts.map(({ name, phone }) => <div className="stack" key={phone}>
          <strong>{name || phone}</strong>
          <div className="grid2">
            <a className="btnlink" href={'tel:' + phone} aria-label={'Llamar a ' + (name || phone)}>Llamar</a>
            <a className="btnlink" href={emergencySmsLink(phone, fix)} aria-label={'Abrir SMS para ' + (name || phone)}>Abrir SMS</a>
          </div>
        </div>)}
      </section>}
      <small className="center">Emergencias: Carabineros 133 · Ambulancia 131 · Bomberos 132</small>
    </Sheet>
  );
}

/** I8 · Ruta dibujada sin depender de mapas en línea (funciona sin señal). */
export function RouteMap({ points, height = 220 }: { points: RoutePoint[]; height?: number }) {
  const w = 320;
  const xy = projectRoute(points, w, height);
  if (xy.length < 2) return <p className="muted center">La ruta aparecerá cuando haya al menos dos puntos GPS.</p>;
  const d = xy.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ');
  const [sx, sy] = xy[0], [ex, ey] = xy[xy.length - 1];
  return (
    <svg className="routemap" viewBox={`0 0 ${w} ${height}`} role="img" aria-label="Ruta recorrida">
      <path d={d} fill="none" stroke="var(--route)" strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={sx} cy={sy} r="6" fill="#2e9e4f" /><circle cx={ex} cy={ey} r="6" fill="#d2402f" />
    </svg>
  );
}

export function SummarySheet({ machine, summary, points, onClose }: { machine: string; summary: Summary; points: RoutePoint[]; onClose: () => void }) {
  const text = summaryText(machine, summary);
  const share = async () => { try { if (navigator.share) await navigator.share({ title: 'Jornada Steps', text }); else await navigator.clipboard.writeText(text); } catch { /* cancelado */ } };
  const h = Math.floor(summary.durationMs / 3600000), m = Math.round((summary.durationMs % 3600000) / 60000);
  return (
    <Sheet title="Resumen de la jornada" onClose={onClose}>
      <RouteMap points={points} />
      <div className="grid3">
        <div><strong>{h}:{String(m).padStart(2, '0')}</strong><small>horas</small></div>
        <div><strong>{summary.km.toFixed(1)}</strong><small>km</small></div>
        <div><strong>{summary.fuelUsedL != null ? summary.fuelUsedL.toFixed(0) : '—'}</strong><small>litros</small></div>
        <div><strong>{summary.stops}</strong><small>paradas</small></div>
        <div><strong>{summary.avgKmh.toFixed(1)}</strong><small>km/h medios</small></div>
        <div><strong>{summary.maxKmh.toFixed(0)}</strong><small>km/h máx.</small></div>
      </div>
      <small className="center">Las cifras de km provienen de los puntos GPS de este teléfono; la web puede diferir ligeramente al filtrar puntos.</small>
      <button onClick={() => void share()}>Compartir resumen</button>
      <button className="primary" onClick={onClose}>Listo</button>
    </Sheet>
  );
}
