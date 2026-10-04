import { useCallback, useEffect, useState, type FormEvent } from 'react';
import type { ModuleProps } from '../registry';
import { useSession, useSyncState } from '../../app/context';
import { messageFor } from '../../app/messages';
import type { ColacionesMe, Totem } from '../../shared/contracts';
import type { QueueOp } from '../../sync/queue';
import { Banner, Button, Card, Chip, Empty, Field, TopBar } from '../../shared/ui';
import ScanField from '../../shared/ui/ScanField';
import { buildRegistration, colacionesApi, groupFor, MODULE, rejectionText, type RegisterPayload } from './service';

type View = 'persona' | 'operador';

export default function Colaciones({ runtime, onExit, view: initial }: ModuleProps) {
  useSession(); // re-render si cambian los permisos
  const { session } = runtime;
  const canPerson = session.can('colaciones.read_own'), canOp = session.can('colaciones.register');
  const [view, setView] = useState<View>(initial === 'registrar' && canOp ? 'operador' : canPerson ? 'persona' : 'operador');
  return (
    <div className="ui-shell">
      <TopBar title="Colaciones" onBack={onExit} />
      <main className="ui-main"><div className="ui-screen">
        {canPerson && canOp && (
          <div className="ui-seg" role="group" aria-label="Vista">
            <Button aria-pressed={view === 'persona'} onClick={() => setView('persona')}>Mis colaciones</Button>
            <Button aria-pressed={view === 'operador'} onClick={() => setView('operador')}>Registrar entrega</Button>
          </div>)}
        {!canPerson && !canOp && <Banner tone="bad">Tu acceso a Colaciones no está vigente. Conéctate para validarlo o consulta a tu administrador.</Banner>}
        {view === 'persona' && canPerson && <PersonView runtime={runtime} />}
        {view === 'operador' && canOp && <OperatorView runtime={runtime} />}
      </div></main>
    </div>
  );
}

function PersonView({ runtime }: Pick<ModuleProps, 'runtime'>) {
  const api = colacionesApi(runtime.session.api);
  const [data, setData] = useState<ColacionesMe | null>(null);
  const [error, setError] = useState('');
  const load = useCallback(() => { setError(''); api.me().then(setData).catch((e) => setError(messageFor(e))); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(load, [load]);

  if (error) return <><Banner tone="bad">{error}</Banner><Button onClick={load}>Reintentar</Button></>;
  if (!data) return <p role="status" className="muted">Cargando…</p>;
  if (!data.linked) return <Card><Empty title="Tu cuenta aún no está vinculada a un trabajador" hint="Pide a tu administrador que la vincule en Odoo. Mientras tanto no hay datos que mostrar." /></Card>;
  return (
    <>
      <Card label="Hoy">
        <div className="ui-row"><div><small>Trabajador</small><h2>{data.employee}</h2></div><Chip tone={data.eligible ? 'ok' : 'bad'}>{data.eligible ? 'Habilitado' : 'No habilitado'}</Chip></div>
        <p>{data.today.registered ? `Hoy ya recibiste tu colación (${data.today.registration}).` : data.eligible ? 'Hoy aún no registras colación.' : 'Tu empresa no te tiene habilitada la colación.'}</p>
      </Card>
      <Card label="Historial"><h3>Tus últimos registros</h3>
        {data.recent.length === 0 ? <Empty title="Sin registros todavía" /> : <ul className="ui-list">{data.recent.map((r) => <li key={r.registration}><span>{r.product}<small>{r.registration}</small></span><span>{r.meal_date}</span></li>)}</ul>}
      </Card>
    </>
  );
}

function OperatorView({ runtime }: Pick<ModuleProps, 'runtime'>) {
  const api = colacionesApi(runtime.session.api);
  const sync = useSyncState();
  const { access } = useSession();
  const [totems, setTotems] = useState<Totem[] | null>(null);
  const [totemId, setTotemId] = useState<number | null>(() => { try { return Number(localStorage.getItem('steps.colaciones.totem')) || null; } catch { return null; } });
  const [identifier, setIdentifier] = useState('');
  const [error, setError] = useState('');
  const [saved, setSaved] = useState('');
  const [ops, setOps] = useState<QueueOp[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.totems().then((r) => { setTotems(r.totems); setTotemId((cur) => (r.totems.some((t) => t.id === cur) ? cur : r.totems[0]?.id ?? null)); }).catch((e) => { setTotems([]); setError(messageFor(e)); }); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { void runtime.ops(MODULE).then((all) => setOps(all.slice(-20).reverse())); }, [runtime, sync.version]);
  useEffect(() => { try { if (totemId) localStorage.setItem('steps.colaciones.totem', String(totemId)); } catch { /* sin almacenamiento */ } }, [totemId]);

  const totem = totems?.find((t) => t.id === totemId);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!totem || !identifier.trim() || busy) return;
    setBusy(true); setError(''); setSaved('');
    try {
      const cap = buildRegistration(totem, identifier);
      // Se guarda ANTES de decir nada: si no se pudo guardar, se muestra el error y no hay falso éxito.
      await runtime.enqueue({ module: MODULE, kind: 'register', group: groupFor(totem.id), payload: cap.payload, id: cap.id });
      setIdentifier(''); setSaved('Guardado en el teléfono. Se envía solo; revisa el estado abajo.');
    } catch (err) { setError(messageFor(err)); } finally { setBusy(false); }
  };

  if (access === 'offline_expired') return <Banner tone="bad">Pasó el plazo sin conexión: conéctate para validar tu acceso antes de registrar nuevas entregas.</Banner>;
  if (totems === null) return <p role="status" className="muted">Cargando tótems…</p>;
  if (!totems.length) return <Card><Empty title="No tienes tótems autorizados" hint={error || 'Pide a tu administrador que te asigne un tótem.'} /></Card>;

  return (
    <>
      <form className="ui-card" onSubmit={submit}>
        <h2>Registrar entrega</h2>
        {totems.length > 1 && <Field label="Tótem"><select value={totemId ?? ''} onChange={(e) => setTotemId(Number(e.target.value))}>{totems.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></Field>}
        <small>{totem?.product} · identificación por {totem?.identification_method === 'pin' ? 'NIP' : totem?.identification_method === 'nfc' ? 'NFC' : 'código de barras'}</small>
        <ScanField label="Código del trabajador" hint="Escribe, usa un lector o, si tu teléfono lo permite, la cámara." value={identifier} onChange={setIdentifier} />
        {error && <Banner tone="bad">{error}</Banner>}
        {saved && <Banner tone="ok">{saved}</Banner>}
        <button className="ui-btn ui-btn--primary" disabled={busy || !identifier.trim()}>{busy ? 'Guardando…' : 'Registrar'}</button>
      </form>
      <Card label="Últimos registros">
        <h3>Últimos registros de este teléfono</h3>
        {ops.length === 0 ? <Empty title="Aún no registras entregas" /> : <ul className="ui-list">{ops.map((o) => <OpRow key={o.id} op={o} />)}</ul>}
      </Card>
    </>
  );
}

function OpRow({ op }: { op: QueueOp }) {
  const p = op.payload as RegisterPayload;
  const result = op.result as { employee?: string; registration?: string; duplicate?: boolean } | undefined;
  const time = new Date(p.record.event_datetime).toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' });
  if (op.state === 'confirmed') return <li><span>{result?.employee ?? 'Entrega'}<small>{time} · {p.totemName}{result?.duplicate ? ' · ya estaba registrada' : ''}</small></span><Chip tone="ok">Confirmada</Chip></li>;
  if (op.state === 'rejected') return <li><span>Entrega de las {time}<small>{rejectionText(op.error)}</small></span><Chip tone="bad">Rechazada</Chip></li>;
  if (op.state === 'auth_required') return <li><span>Entrega de las {time}<small>Requiere que vuelvas a entrar o que se revise tu acceso.</small></span><Chip tone="bad">Requiere acceso</Chip></li>;
  if (op.state === 'blocked') return <li><span>Entrega de las {time}<small>Se detuvo tras varios intentos. Toca «Reintentar» en Sincronización.</small></span><Chip tone="bad">Detenida</Chip></li>;
  return <li><span>Entrega de las {time}<small>{p.totemName} · se enviará al volver la señal</small></span><Chip tone="warn">Pendiente</Chip></li>;
}
