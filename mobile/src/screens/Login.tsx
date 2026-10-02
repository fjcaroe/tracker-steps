import { useState, type FormEvent } from 'react';
import { login, type User } from '../lib/api';

export default function Login({ onLogin }: { onLogin: (u: User) => void }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [show, setShow] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setError('');
    try { onLogin((await login(username.trim(), password)).user); }
    catch (err) { setError((err as Error).message || 'No se pudo iniciar sesión.'); }
    finally { setBusy(false); }
  };

  return (
    <main className="login">
      <div className="login__hero"><span className="brand brand--big"><b>S</b>Steps <em>Móvil</em></span><p>Registra tu jornada, tu máquina y tu ruta desde el terreno.</p></div>
      <form className="card login__form" onSubmit={submit}>
        <label>Usuario<input autoComplete="username" autoCapitalize="none" value={username} onChange={(e) => setUsername(e.target.value)} required /></label>
        <label>Contraseña
          <span className="pw"><input type={show ? 'text' : 'password'} autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            <button type="button" className="link" onClick={() => setShow((s) => !s)}>{show ? 'Ocultar' : 'Mostrar'}</button></span>
        </label>
        {error && <p className="error" role="alert">{error}</p>}
        <button className="primary" disabled={busy || !username || !password}>{busy ? 'Ingresando…' : 'Ingresar'}</button>
        <a className="link center" href="/web/login?redirect=/truck/">Entrar con mi cuenta Odoo</a>
      </form>
    </main>
  );
}
