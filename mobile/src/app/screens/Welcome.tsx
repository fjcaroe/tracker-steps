import { useEffect, useState, type FormEvent } from 'react';
import { useRuntime, useSession } from '../context';
import { messageFor } from '../messages';
import { Banner, Button, Field } from '../../shared/ui';
import type { HealthOut } from '../../shared/contracts';
import { googleIdToken } from '../../platform/google';

/** Bienvenida: ingresar o crear cuenta. Una cuenta nueva NO da acceso a ninguna empresa. */
export default function Welcome() {
  const { session } = useRuntime();
  const { notice } = useSession();
  const [mode, setMode] = useState<'login' | 'register' | 'recover'>('login');
  const [code, setCode] = useState('');
  const [info, setInfo] = useState('');
  const [codeSent, setCodeSent] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [show, setShow] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [providers, setProviders] = useState<HealthOut['providers'] | null>(null);

  useEffect(() => { void session.api.health().then((h) => setProviders(h.providers)).catch(() => setProviders(null)); }, [session]);

  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setError('');
    try {
      if (mode === 'login') await session.login(email.trim(), password);
      else if (mode === 'register') await session.register(email.trim(), password, name.trim());
      else if (!codeSent) { await session.api.recoverRequest(email.trim()); setCodeSent(true); setInfo('Si el correo está registrado, te enviamos un código. Si tu administrador te lo entregó, escríbelo aquí.'); }
      else { await session.api.recoverConfirm({ email: email.trim(), code: code.trim(), password }); setInfo('Listo: ya puedes ingresar con tu nueva contraseña. Se cerraron las sesiones anteriores, también en teléfonos perdidos.'); setMode('login'); setCode(''); setPassword(''); setCodeSent(false); }
    } catch (err) { setError(messageFor(err, 'No se pudo completar el ingreso.')); } finally { setBusy(false); }
  };
  const google = async () => {
    if (!googleIdToken) return;
    setBusy(true); setError('');
    try { await session.loginGoogle(await googleIdToken()); } catch (err) { setError(messageFor(err, 'No se pudo ingresar con Google.')); } finally { setBusy(false); }
  };

  return (
    <main className="ui-welcome">
      <div className="ui-welcome__hero"><span className="brand brand--big"><b>S</b>Steps</span><h1>Tu día en terreno, organizado.</h1><p>Tus tareas de campo en un solo lugar: colaciones, movilización y jornadas de maquinaria.</p></div>
      <form className="ui-welcome__panel" onSubmit={submit}>
        {notice && <Banner tone="warn">{notice}</Banner>}
        <div className="ui-seg" role="group" aria-label="Acceso">
          <Button aria-pressed={mode === 'login'} onClick={() => setMode('login')}>Ingresar</Button>
          <Button aria-pressed={mode === 'register'} onClick={() => setMode('register')}>Crear cuenta</Button>
          <Button aria-pressed={mode === 'recover'} onClick={() => { setMode('recover'); setInfo(''); setError(''); }}>Recuperar</Button>
        </div>
        {mode === 'register' && <Field label="Nombre"><input autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} required /></Field>}
        <Field label="Correo"><input type="email" autoComplete="email" autoCapitalize="none" value={email} onChange={(e) => setEmail(e.target.value)} required /></Field>
        {mode === 'recover' && codeSent && <Field label="Código de recuperación"><input value={code} onChange={(e) => setCode(e.target.value)} autoCapitalize="none" autoComplete="one-time-code" required /></Field>}
        {(mode !== 'recover' || codeSent) && <Field label={mode === 'recover' ? 'Contraseña nueva' : 'Contraseña'} hint={mode !== 'login' ? 'Mínimo 10 caracteres.' : undefined}>
          <span className="pw"><input type={show ? 'text' : 'password'} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} value={password} onChange={(e) => setPassword(e.target.value)} required />
            <Button variant="quiet" onClick={() => setShow((s) => !s)}>{show ? 'Ocultar' : 'Mostrar'}</Button></span>
        </Field>}
        {info && <Banner tone="ok">{info}</Banner>}
        {error && <Banner tone="bad">{error}</Banner>}
        <button className="ui-btn ui-btn--primary" disabled={busy || !email || (mode !== 'recover' && !password) || (mode === 'register' && !name) || (mode === 'recover' && codeSent && (!code || !password))}>{busy ? 'Un momento…' : mode === 'login' ? 'Ingresar' : mode === 'register' ? 'Crear cuenta' : codeSent ? 'Cambiar contraseña' : 'Enviar código'}</button>
        {providers?.google && googleIdToken && <Button onClick={() => void google()} disabled={busy}>Continuar con Google</Button>}
        <small className="muted center">Crear una cuenta no te da acceso a ninguna empresa: tu administrador te invitará o aprobará tu solicitud.</small>
      </form>
    </main>
  );
}
