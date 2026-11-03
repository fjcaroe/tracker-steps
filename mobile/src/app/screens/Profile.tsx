import { useEffect, useState } from 'react';
import { useRuntime, useSession, useSyncState } from '../context';
import { messageFor } from '../messages';
import { APP_VERSION } from '../version';
import type { DeviceOut } from '../../shared/contracts';
import { Banner, Button, Card, Chip, Confirm } from '../../shared/ui';
import WatchSettings from './WatchSettings';

const PRIVACY_URL = (import.meta.env.VITE_PRIVACY_URL as string | undefined) || '';

export default function Profile() {
  const { session } = useRuntime();
  const { me, orgUid, catalog } = useSession();
  const sync = useSyncState();
  const [devices, setDevices] = useState<DeviceOut[] | null>(null);
  const [msg, setMsg] = useState('');
  const [confirm, setConfirm] = useState<'logout' | 'delete' | null>(null);
  const active = me?.memberships.filter((m) => m.state === 'active') ?? [];

  const load = () => session.api.devices().then((r) => setDevices(r.devices)).catch((e) => setMsg(messageFor(e)));
  useEffect(() => { void load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const warning = [sync.pending ? `Hay ${sync.pending} elementos sin enviar: quedan guardados en este teléfono y se enviarán cuando vuelvas a entrar con esta cuenta.` : '', sync.rejected ? `${sync.rejected} operaciones rechazadas se conservan para revisión.` : ''].filter(Boolean).join(' ');

  return (
    <div className="ui-screen">
      <Card label="Cuenta">
        <h2>{me?.person.name}</h2>
        <p className="muted">{me?.person.email} · {me?.providers.join(', ')}</p>
        {me && !me.email_verified && <Banner tone="warn">Tu correo aún no está confirmado.</Banner>}
        <small>Versión {APP_VERSION}</small>
      </Card>

      {active.length > 1 && (
        <Card label="Empresa">
          <h3>Empresa activa</h3>
          <ul className="ui-list">{active.map((m) => (
            <li key={m.org_uid}><span>{m.name}</span>{m.org_uid === orgUid ? <Chip tone="ok">Activa</Chip> : <Button onClick={() => void session.selectOrg(m.org_uid)}>Cambiar</Button>}</li>))}</ul>
          <small>Al cambiar de empresa se vuelven a validar tus permisos. Lo pendiente de cada empresa se guarda por separado.</small>
        </Card>
      )}
      {catalog && <Card label="Permisos"><h3>Tus accesos en {catalog.organization.name}</h3>
        <ul className="ui-list">{catalog.modules.map((m) => <li key={m.code}><span>{m.name}</span><small>{m.roles.join(', ')}</small></li>)}</ul></Card>}

      <Card label="Dispositivos">
        <h3>Dispositivos con tu sesión</h3>
        {devices === null ? <small>Cargando…</small> : <ul className="ui-list">{devices.map((d) => (
          <li key={d.id}><span>{d.label || d.platform || 'Dispositivo'}{d.current && ' (este)'}<small>{d.last_seen_at ? `Visto: ${new Date(d.last_seen_at).toLocaleString('es-CL')}` : ''}</small></span>
            {d.revoked ? <Chip tone="bad">Revocado</Chip> : !d.current && <Button onClick={() => void session.api.revokeDevice(d.id).then(load).catch((e) => setMsg(messageFor(e)))}>Cerrar sesión ahí</Button>}</li>))}</ul>}
        {msg && <Banner tone="bad">{msg}</Banner>}
      </Card>

      <WatchSettings />
      <Card label="Privacidad">
        <h3>Privacidad y datos</h3>
        {PRIVACY_URL ? <a className="btnlink" href={PRIVACY_URL} target="_blank" rel="noreferrer">Política de privacidad</a> : <small>La política de privacidad se publicará con el lanzamiento en tiendas.</small>}
        <small>Eliminar tu cuenta retira tu acceso y tu identidad. Los registros de la empresa (colaciones, servicios) se conservan según su política.</small>
        <Button variant="danger" onClick={() => setConfirm('delete')}>Solicitar eliminación de mi cuenta</Button>
      </Card>
      <Button onClick={() => setConfirm('logout')}>Cerrar sesión</Button>

      {confirm === 'logout' && <Confirm title="¿Cerrar sesión?" body={<p>{warning || 'No hay nada pendiente de envío.'}</p>} confirmLabel="Cerrar sesión" onCancel={() => setConfirm(null)} onConfirm={() => { setConfirm(null); void session.logout(); }} />}
      {confirm === 'delete' && <Confirm danger title="¿Eliminar tu cuenta?" body={<p>Se cerrará tu sesión en todos tus dispositivos y no podrás volver a entrar. {warning}</p>} confirmLabel="Sí, eliminar mi cuenta" onCancel={() => setConfirm(null)}
        onConfirm={() => { setConfirm(null); void session.api.deleteAccount().then(() => session.logout()).catch((e) => setMsg(messageFor(e))); }} />}
    </div>
  );
}
