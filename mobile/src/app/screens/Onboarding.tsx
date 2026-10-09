import { useState } from 'react';
import { useRuntime, useSession } from '../context';
import { messageFor } from '../messages';
import { Banner, Button, Card, Field } from '../../shared/ui';

/** Estado de incorporación: cuenta creada, todavía sin empresa. Aquí no hay datos empresariales. */
export default function Onboarding() {
  const { session } = useRuntime();
  const { me } = useSession();
  const [invite, setInvite] = useState('');
  const [orgCode, setOrgCode] = useState('');
  const [note, setNote] = useState('');
  const [code, setCode] = useState('');
  const [msg, setMsg] = useState<{ tone: 'ok' | 'bad'; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const run = async (job: () => Promise<string | void>) => {
    setBusy(true); setMsg(null);
    try { const text = await job(); if (text) setMsg({ tone: 'ok', text }); await session.refreshAccess(); }
    catch (e) { setMsg({ tone: 'bad', text: messageFor(e) }); } finally { setBusy(false); }
  };
  const state = me?.onboarding ?? 'no_organization';
  const pending = me?.memberships.filter((m) => m.state === 'requested' || m.state === 'invited') ?? [];

  return (
    <div className="ui-screen">
      <Card label="Tu cuenta">
        <h2>Hola, {me?.person.name}</h2>
        <p className="muted">Tu cuenta está creada, pero todavía no tienes acceso a una empresa. Aquí no se muestran datos de ninguna empresa hasta que se te habilite.</p>
      </Card>
      {msg && <Banner tone={msg.tone}>{msg.text}</Banner>}

      {me && !me.email_verified && (
        <Card label="Confirmar correo">
          <h3>Confirma tu correo</h3>
          <p className="muted">Para aceptar una invitación, confirma {me.person.email} con el código recibido. Si no recibes un código, pide a tu administrador que revise tu cuenta.</p>
          <Field label="Código de verificación"><input value={code} onChange={(e) => setCode(e.target.value)} autoCapitalize="none" /></Field>
          <Button disabled={busy || !code} onClick={() => void run(async () => { await session.api.verifyEmail({ email: me.person.email ?? '', code: code.trim() }); setCode(''); return 'Correo confirmado.'; })}>Confirmar</Button>
        </Card>
      )}

      {state === 'request_pending' || state === 'invitation_pending' ? (
        <Card label="Esperando aprobación">
          <h3>{state === 'invitation_pending' ? 'Tienes una invitación pendiente' : 'Tu solicitud está en revisión'}</h3>
          {pending.map((m) => <p key={m.org_uid}><strong>{m.name}</strong></p>)}
          <p className="muted">Cuando el administrador la apruebe verás tus módulos aquí.</p>
          <Button disabled={busy} onClick={() => void run(async () => undefined)}>Revisar de nuevo</Button>
        </Card>
      ) : null}

      <Card label="Tengo una invitación">
        <h3>Tengo un código de invitación</h3>
        <Field label="Código" hint="Lo entrega tu administrador."><input value={invite} onChange={(e) => setInvite(e.target.value)} autoCapitalize="none" /></Field>
        <Button variant="primary" disabled={busy || !invite} onClick={() => void run(async () => { await session.api.acceptInvitation(invite.trim()); setInvite(''); return 'Invitación aceptada.'; })}>Aceptar invitación</Button>
      </Card>

      <Card label="Solicitar acceso">
        <h3>Solicitar acceso a una empresa</h3>
        <Field label="Código de empresa" hint="Pídeselo a tu administrador. El código no te da acceso: solo lo solicita."><input value={orgCode} onChange={(e) => setOrgCode(e.target.value.toUpperCase())} autoCapitalize="characters" maxLength={8} /></Field>
        <Field label="Mensaje (opcional)"><input value={note} onChange={(e) => setNote(e.target.value)} maxLength={200} placeholder="Ej.: conductor de la ruta 3" /></Field>
        <Button disabled={busy || orgCode.length < 8} onClick={() => void run(async () => { await session.api.requestAccess(orgCode, note); setOrgCode(''); return 'Solicitud enviada. Te avisaremos al aprobarla.'; })}>Enviar solicitud</Button>
      </Card>
    </div>
  );
}
