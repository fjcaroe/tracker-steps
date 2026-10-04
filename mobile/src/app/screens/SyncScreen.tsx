import { useEffect, useState } from 'react';
import { useRuntime, useSyncState } from '../context';
import { DurableQueue, type QueueOp } from '../../sync/queue';
import { Banner, Button, Card, Chip, Empty } from '../../shared/ui';
import RejectedPoints from '../../modules/tracker/screens/RejectedPoints';

export const STATE_LABEL: Record<QueueOp['state'], { text: string; tone: 'info' | 'ok' | 'warn' | 'bad' }> = {
  pending: { text: 'Pendiente', tone: 'warn' }, sending: { text: 'Enviando', tone: 'warn' }, confirmed: { text: 'Confirmada', tone: 'ok' },
  auth_required: { text: 'Requiere acceso', tone: 'bad' }, rejected: { text: 'Rechazada', tone: 'bad' },
};

function download(name: string, text: string) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text], { type: 'application/json' }));
  a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

/** Estado de sincronización: pendientes, problemas, reintento real, copia para soporte y colas de otras cuentas. */
export default function SyncScreen() {
  const runtime = useRuntime();
  const sync = useSyncState();
  const [ops, setOps] = useState<QueueOp[]>([]);
  useEffect(() => { void runtime.ops().then(setOps); }, [runtime, sync.version]);
  const problems = ops.filter((o) => o.state === 'rejected' || o.state === 'auth_required');
  const waiting = ops.filter((o) => o.state === 'pending' || o.state === 'sending');

  return (
    <div className="ui-screen">
      <Card label="Resumen">
        <h2>Sincronización</h2>
        <div className="ui-row"><span>Por enviar</span><Chip tone={sync.pending ? 'warn' : 'ok'}>{sync.pending}</Chip></div>
        <div className="ui-row"><span>Con problema</span><Chip tone={problems.length ? 'bad' : 'ok'}>{problems.length}</Chip></div>
        <small>{sync.lastSyncAt ? `Último envío: ${new Date(sync.lastSyncAt).toLocaleString('es-CL')}` : 'Aún no se ha enviado nada en esta sesión.'}</small>
        {sync.lastHalt === 'network' && <Banner tone="warn">Sin conexión con el servidor: se reintentará solo al volver la señal.</Banner>}
        {sync.lastHalt === 'auth' && <Banner tone="bad">Tu sesión o tus permisos necesitan atención. Lo guardado no se perdió.</Banner>}
        <Button variant="primary" disabled={sync.syncing} onClick={() => void runtime.retry()}>{sync.syncing ? 'Enviando…' : 'Reintentar ahora'}</Button>
      </Card>

      {problems.length > 0 && (
        <Card label="Con problema">
          <h3>Con problema</h3>
          <p className="muted">Estas operaciones no se borran. Puedes reintentarlas o guardar una copia para soporte.</p>
          <ul className="ui-list">{problems.map((o) => (
            <li key={o.id}><div><strong>{o.module} · {o.kind}</strong><small>{o.error ?? o.code}</small></div><Chip tone="bad">{STATE_LABEL[o.state].text}</Chip></li>))}</ul>
          <div className="ui-grid">
            <Button onClick={() => void runtime.retry(problems.map((o) => o.id))}>Reintentar con problema</Button>
            <Button onClick={async () => { const q = runtime.queue(); if (q) download(`steps-pendientes-${new Date().toISOString().slice(0, 10)}.json`, await q.exportJson()); }}>Guardar copia</Button>
          </div>
        </Card>
      )}

      <Card label="Pendientes">
        <h3>Por enviar</h3>
        {waiting.length === 0 ? <Empty title="No hay nada pendiente" /> : <ul className="ui-list">{waiting.map((o) => <li key={o.id}><span>{o.module} · {o.kind}</span><Chip tone="warn">{o.attempts ? `Reintentos: ${o.attempts}` : 'Pendiente'}</Chip></li>)}</ul>}
      </Card>

      {sync.foreign.length > 0 && (
        <Card label="Datos de otras cuentas">
          <h3>Datos de otra cuenta en este teléfono</h3>
          <p className="muted">Hay registros guardados por otra persona o empresa. No se envían con tu sesión ni se borran: entra con esa cuenta para enviarlos, o guarda una copia.</p>
          <ul className="ui-list">{sync.foreign.map((f) => (
            <li key={`${f.scope.personId}.${f.scope.orgUid}`}><span>Cuenta {f.scope.personId} · {f.scope.orgUid}<small>{f.pending} pendientes · {f.rejected} rechazadas</small></span>
              <Button onClick={async () => download(`steps-otra-cuenta-${f.scope.personId}.json`, await new DurableQueue(runtime.kv, f.scope).exportJson())}>Guardar copia</Button></li>))}</ul>
        </Card>
      )}
      <RejectedPoints />
    </div>
  );
}
