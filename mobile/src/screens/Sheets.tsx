import { useEffect, useState, type FormEvent, type ReactNode } from 'react';
import { mobile, type IncidentCategory } from '../lib/api';
import type { Fix } from '../lib/geo';
import { compressPhoto } from '../lib/photo';
import { parseNumber, type Active } from '../lib/queue';
import { projectRoute, summaryText, type RoutePoint, type Summary } from '../lib/route';
import { outboxStore } from '../lib/sync';

const DEFAULT_ITEMS = [
  { key: 'lights', label: 'Luces y señalización' }, { key: 'brakes', label: 'Frenos' }, { key: 'tires', label: 'Neumáticos (presión y desgaste)' },
  { key: 'oil', label: 'Nivel de aceite y refrigerante' }, { key: 'leaks', label: 'Sin fugas de aceite o combustible' }, { key: 'extinguisher', label: 'Extintor vigente' },
];

export function Sheet({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return (
    <div className="sheet" role="dialog" aria-modal="true" aria-label={title}>
      <div className="sheet__panel stack">
        <div className="row"><h2>{title}</h2><button type="button" onClick={onClose} aria-label="Cerrar">Cerrar</button></div>
        {children}
      </div>
    </div>
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
export function IncidentSheet({ active, fix, onClose, onSaved }: Props) {
  const [category, setCategory] = useState<IncidentCategory>('breakdown');
  const [note, setNote] = useState('');
  const [photo, setPhoto] = useState('');
  const save = (e: FormEvent) => {
    e.preventDefault();
    outboxStore.add({ kind: 'post', path: 'incidents', sessionId: active.sessionId, body: { id: crypto.randomUUID(), category, note: note || null, machine_id: active.machineId, session_id: active.sessionId, lat: fix?.lat ?? null, lon: fix?.lon ?? null, occurred_at: new Date().toISOString(), photo_b64: photo || null } });
    onSaved('Incidente registrado. Se enviará apenas haya señal.');
  };
  return (
    <Sheet title="Reportar incidente" onClose={onClose}>
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

/** I12 · SOS: confirmación explícita y envío inmediato con ubicación. */
export function SosSheet({ active, fix, onClose, onSaved }: Props) {
  const send = () => {
    outboxStore.add({ kind: 'post', path: 'incidents', sessionId: active.sessionId, body: { id: crypto.randomUUID(), category: 'sos', note: 'SOS del conductor', machine_id: active.machineId, session_id: active.sessionId, lat: fix?.lat ?? null, lon: fix?.lon ?? null, occurred_at: new Date().toISOString() } });
    onSaved('SOS enviado con tu ubicación. Si es una emergencia, llama también al 133 (Carabineros) o 131 (Ambulancia).');
  };
  return (
    <Sheet title="Emergencia" onClose={onClose}>
      <p>Se avisará de inmediato a la oficina con tu ubicación y la hora.</p>
      <button className="danger big" onClick={send}>Enviar SOS</button>
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
